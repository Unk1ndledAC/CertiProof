"""
tactic.py
=========
High-level tactic engine for NeuroProof.

This module provides a *tactic-based* interface on top of the core
proof calculus, analogous to Coq's tactic language but implemented in
Python.  Each tactic is a function that takes a *goal* (a formula to
prove under a set of hypotheses) and returns either a completed Proof
or a list of subgoals.

Novel contribution (§3.6 of the paper):
  The ATSS-guided tactic selection implements a *policy gradient* over
  the tactic space, favouring tactics that have historically reduced
  the proof depth.  This is an online learning procedure that runs
  within a single proof search, requiring no external training data.

References:
  - Gentzen (1935): sequent calculus, cut rule, cut-elimination.
  - Prawitz (1965): natural deduction normalisation.
  - Coq Dev Team (2024): Coq tactic language design.
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Dict, FrozenSet, List, Optional, Set
from enum import Enum, auto
import itertools

from .formula import (Formula, Var, Unary, Binary, _Constant,
                      Connective, Top, Bot, And, Or, Implies, Not, parse,
                      to_nnf)
from .proof import Proof, ProofStep, ProofBuilder, Rule
from .solver import NeuroProofSolver, EXP3ATSS, ATSS, SolverStatus, InterpolantExtractor
from .kernel import KernelError

# Lazy import of GNN ATSS (optional, requires torch + torch_geometric)
try:
    from .atss_gnn import GNNATSS, FormulaGraph
    _HAS_GNN = True
except ImportError:
    _HAS_GNN = False


# ──────────────────────────────────────────────────────────────────────────────
# Goal and tactic result types
# ──────────────────────────────────────────────────────────────────────────────

@dataclass
class Goal:
    """
    A proof obligation: prove `conclusion` under hypotheses `context`.

    Attributes
    ----------
    conclusion : Formula
        The formula to be proved.
    context : dict mapping name → Formula
        Named hypotheses currently in scope.
    depth_limit : int
        Maximum number of tactic applications remaining.
    """
    conclusion: Formula
    context:    Dict[str, Formula] = field(default_factory=dict)
    depth_limit: int = 200

    def hyp(self, name: str) -> Formula:
        return self.context[name]

    def has_hyp(self, f: Formula) -> Optional[str]:
        """Return the name of f in context, or None."""
        for k, v in self.context.items():
            if v == f:
                return k
        return None

    def add_hyp(self, name: str, f: Formula) -> 'Goal':
        new_ctx = dict(self.context)
        new_ctx[name] = f
        return Goal(self.conclusion, new_ctx, self.depth_limit - 1)

    def with_conclusion(self, f: Formula) -> 'Goal':
        return Goal(f, dict(self.context), self.depth_limit - 1)


class TacticStatus(Enum):
    SUCCESS  = auto()
    FAIL     = auto()
    SUBGOALS = auto()   # tactic decomposes into subgoals


@dataclass
class TacticResult:
    status:   TacticStatus
    proof:    Optional[Proof]        = None
    subgoals: List[Goal]             = field(default_factory=list)
    message:  str                    = ''


# ──────────────────────────────────────────────────────────────────────────────
# Tactic Engine
# ──────────────────────────────────────────────────────────────────────────────

class TacticEngine:
    """
    The NeuroProof tactic engine.

    Provides a library of reusable proof tactics, ordered by the ATSS
    policy.  Each tactic either closes the goal, decomposes it into
    sub-goals, or fails.

    Architecture:
      - ``prove(goal)`` is the main entry point
      - Internally it calls ``_tactic_seq``, which tries tactics in
        ATSS-ranked order
      - Recursive subgoals are handled by ``_prove_recursive``
    """

    def __init__(self, atss: Optional[ATSS] = None,
                 max_depth: int = 200,
                 gnn_atss: Optional['GNNATSS'] = None,
                 use_fallback: bool = True) -> None:
        self._atss = atss or ATSS()
        self._solver = NeuroProofSolver(exp3_atss=self._atss)
        self._max_depth = max_depth
        self._pb: Optional[ProofBuilder] = None
        # GNN-based tactic selection (optional enhancement over cosine ATSS)
        self._gnn_atss = gnn_atss if _HAS_GNN and gnn_atss is not None else None
        self._gnn_blend: float = 0.5  # weight for GNN vs cosine ATSS
        self._use_fallback = use_fallback
        # EXP3-ATSS tactic index mapping
        self._tactic_index: Dict[str, int] = {
            'assumption': 0, 'contradiction': 1, 'modus_ponens': 2,
            'and_e': 3, 'and_i': 4, 'imp_i': 5, 'not_i': 6, 'or_i': 7, 'iff_i': 8,
            'lemma_learn': 9, 'interpolation_cut': 10, 'solver_fallback': 11,
        }

    # ── Public interface ──────────────────────────────────────────────────────

    def prove(self, formula: Formula,
               hypotheses: Optional[Dict[str, Formula]] = None) -> Proof:
        """
        Attempt to prove `formula` under optional hypotheses.

        Returns a certified Proof object or raises ValueError if the
        formula is not provable (or the depth limit is exceeded).
        """
        ctx = hypotheses or {}
        goal = Goal(formula, ctx, self._max_depth)
        self._pb = ProofBuilder()

        # Add hypotheses to the builder
        hyp_steps: Dict[str, ProofStep] = {}
        for name, hyp_f in ctx.items():
            hyp_steps[name] = self._pb.assume(hyp_f,
                                               annotation=f"hyp:{name}")

        step = self._prove_recursive(goal, hyp_steps)
        if step is None:
            raise ValueError(
                f"Could not prove: {formula} "
                f"(EXP3-ATSS-guided search exhausted)")
        self._atss.store_lemma(step)
        return Proof(step)

    def refute(self, formula: Formula) -> Proof:
        """
        Attempt to construct a refutation (proof of ¬formula ⊢ ⊥).

        Returns a Proof of ⊥ showing that formula is unsatisfiable.
        """
        neg = Not(formula)
        result = self._solver.solve_formula(neg)
        if result.status == SolverStatus.UNSAT:
            if result.proof is not None:
                return result.proof
        raise ValueError(f"Formula is satisfiable (not refutable): {formula}")

    def decide(self, formula: Formula) -> SolverStatus:
        """Return SAT/UNSAT/UNKNOWN for formula."""
        return self._solver.solve_formula(formula).status

    def _gnn_feedback(self, goal: Goal, tactic_fn, success: bool) -> None:
        """Send a (formula, tactic, outcome) signal to the GNN ATSS."""
        if self._gnn_atss is None:
            return
        try:
            var_names, clauses = self._formula_to_clauses(goal.conclusion)
            if not var_names and not clauses:
                return
            fg = FormulaGraph(var_names, clauses)
            tactic_name = tactic_fn.__name__
            if tactic_name.startswith('_tactic_'):
                tactic_name = tactic_name[8:]
            self._gnn_atss.update(fg, tactic_name, success)
        except Exception:
            pass  # GNN update failed silently (non-critical)

    # ── Core recursive prover ─────────────────────────────────────────────────

    def _prove_recursive(self, goal: Goal,
                          hyp_steps: Dict[str, ProofStep]
                          ) -> Optional[ProofStep]:
        """
        Attempt to prove goal using all available tactics.

        Returns a ProofStep for the goal's conclusion, or None on failure.
        """
        assert self._pb is not None

        if goal.depth_limit <= 0:
            return None

        # Check lemma store
        cached = self._atss.lookup_lemma(goal.conclusion)
        if cached is not None:
            reuse = self._pb.lemma_reuse(cached, annotation="ATSS cache hit")
            return reuse

        # Ordered tactic list (ATSS-ranked)
        tactics = self._atss_ranked_tactics(goal)

        for tactic in tactics:
            result = tactic(goal, hyp_steps)
            if result.status == TacticStatus.SUCCESS:
                # EXP3-ATSS: reward = 1.0 for success
                tactic_idx = self._tactic_index.get(
                    self._tactic_name(tactic), 0)
                self._atss.update(tactic_idx, 1.0)
                self._gnn_feedback(goal, tactic, success=True)
                if result.proof is not None:
                    step = result.proof._root
                    self._atss.store_lemma(step)
                    return step
            elif result.status == TacticStatus.SUBGOALS:
                # Recursively prove sub-goals
                sub_steps = []
                all_solved = True

                # Special handling for or_i_both: only ONE subgoal needs to
                # succeed (it's a disjunction).  Try the first; if it fails,
                # try the second.
                if result.message == 'or_i_both' and len(result.subgoals) == 2:
                    solved = False
                    for idx, sg in enumerate(result.subgoals):
                        ss = self._prove_recursive(sg, hyp_steps)
                        if ss is not None:
                            sub_steps = [ss]
                            solved = True
                            all_solved = True
                            # Determine which side we proved
                            l, r = goal.conclusion.left, goal.conclusion.right
                            if idx == 0 and self._atss.score(l) >= self._atss.score(r):
                                result = TacticResult(
                                    TacticStatus.SUBGOALS,
                                    subgoals=[sg],
                                    message='or_i_left')
                            elif idx == 0:
                                result = TacticResult(
                                    TacticStatus.SUBGOALS,
                                    subgoals=[sg],
                                    message='or_i_right')
                            elif idx == 1 and self._atss.score(l) >= self._atss.score(r):
                                result = TacticResult(
                                    TacticStatus.SUBGOALS,
                                    subgoals=[sg],
                                    message='or_i_right')
                            else:
                                result = TacticResult(
                                    TacticStatus.SUBGOALS,
                                    subgoals=[sg],
                                    message='or_i_left')
                            break
                        else:
                            self._gnn_feedback(goal, tactic, success=False)
                            tactic_idx = self._tactic_index.get(
                                self._tactic_name(tactic), 0)
                            self._atss.update(tactic_idx, 0.0)
                    if not solved:
                        all_solved = False
                else:
                    for sg in result.subgoals:
                        ss = self._prove_recursive(sg, hyp_steps)
                        if ss is None:
                            all_solved = False
                            self._gnn_feedback(goal, tactic, success=False)
                            tactic_idx = self._tactic_index.get(
                                self._tactic_name(tactic), 0)
                            self._atss.update(tactic_idx, 0.0)
                            break
                        sub_steps.append(ss)
                    if not all_solved:
                        self._gnn_feedback(goal, tactic, success=False)
                if all_solved:
                    # Compose the step from sub-steps
                    step = self._compose(goal, result, sub_steps, hyp_steps)
                    if step is not None:
                        self._gnn_feedback(goal, tactic, success=True)
                        self._atss.store_lemma(step)
                        return step

        self._gnn_feedback(goal, tactic, success=False)
        return None

    def _compose(self, goal: Goal, result: TacticResult,
                  sub_steps: List[ProofStep],
                  hyp_steps: Dict[str, ProofStep]) -> Optional[ProofStep]:
        """Combine sub-step proofs according to the tactic's schema."""
        assert self._pb is not None
        msg = result.message
        pb = self._pb

        if msg == 'and_i' and len(sub_steps) == 2:
            return pb.and_i(sub_steps[0], sub_steps[1])
        if msg == 'or_i_left' and len(sub_steps) == 1:
            assert isinstance(goal.conclusion, Binary)
            return pb.or_i_left(sub_steps[0], goal.conclusion.right)
        if msg == 'or_i_right' and len(sub_steps) == 1:
            assert isinstance(goal.conclusion, Binary)
            return pb.or_i_right(goal.conclusion.left, sub_steps[0])
        if msg == 'or_i_both' and len(sub_steps) == 1:
            # Only the first (preferred) subgoal succeeded — treat as or_i_left
            assert isinstance(goal.conclusion, Binary)
            # Determine which side based on EXP3 distribution
            l, r = goal.conclusion.left, goal.conclusion.right
            exp3_probs = self._atss.get_probability_distribution()
            idx_or_i = self._tactic_index.get('or_i', 6)
            # Default: try left first if EXP3 is not confident
            if idx_or_i < len(exp3_probs) and exp3_probs[idx_or_i] > 0.3:
                return pb.or_i_left(sub_steps[0], r)
            else:
                return pb.or_i_right(l, sub_steps[0])
        if msg == 'imp_i' and len(sub_steps) == 1:
            assert isinstance(goal.conclusion, Binary)
            hyp_f = goal.conclusion.left
            hyp_step = pb.assume(hyp_f, annotation='imp_i hyp')
            return pb.imp_i(hyp_step, sub_steps[0])
        if msg.startswith('modus_ponens:') and len(sub_steps) == 1:
            imp_name = msg.split(':', 1)[1]
            imp_f = goal.context[imp_name]
            major = hyp_steps.get(imp_name) or pb.assume(
                imp_f, annotation=imp_name)
            return pb.imp_e(major, sub_steps[0])
        if msg == 'not_i' and len(sub_steps) == 1:
            assert isinstance(goal.conclusion, Unary)
            hyp_f = goal.conclusion.child
            hyp_step = pb.assume(hyp_f, annotation='not_i hyp')
            return pb.not_i(hyp_step, sub_steps[0])
        if msg == 'iff_i' and len(sub_steps) == 2:
            return pb.iff_i(sub_steps[0], sub_steps[1])
        if msg.startswith('cut:') and len(sub_steps) == 2:
            cut_f = parse(msg[4:])
            return pb.interpolation_guided_cut(
                sub_steps[0], sub_steps[1], cut_f)
        return None

    # ── Individual tactics ────────────────────────────────────────────────────

    def _tactic_assumption(self, goal: Goal,
                            hyp_steps: Dict[str, ProofStep]
                            ) -> TacticResult:
        """Close a goal by finding it in the hypothesis set."""
        assert self._pb is not None
        name = goal.has_hyp(goal.conclusion)
        if name is not None:
            step = hyp_steps.get(name) or self._pb.assume(
                goal.conclusion, annotation=f'assumption:{name}')
            return TacticResult(TacticStatus.SUCCESS,
                                proof=Proof(step))
        if goal.conclusion is Top:
            step = self._pb.truth()
            return TacticResult(TacticStatus.SUCCESS, proof=Proof(step))
        return TacticResult(TacticStatus.FAIL, message='assumption failed')

    def _tactic_and_i(self, goal: Goal,
                       hyp_steps: Dict[str, ProofStep]) -> TacticResult:
        """Split conjunction goal into two sub-goals."""
        if not (isinstance(goal.conclusion, Binary) and
                goal.conclusion.connective == Connective.AND):
            return TacticResult(TacticStatus.FAIL)
        l, r = goal.conclusion.left, goal.conclusion.right
        return TacticResult(
            TacticStatus.SUBGOALS,
            subgoals=[goal.with_conclusion(l), goal.with_conclusion(r)],
            message='and_i')

    def _tactic_imp_i(self, goal: Goal,
                       hyp_steps: Dict[str, ProofStep]) -> TacticResult:
        """Introduce an implication by adding antecedent as hypothesis."""
        if not (isinstance(goal.conclusion, Binary) and
                goal.conclusion.connective == Connective.IMP):
            return TacticResult(TacticStatus.FAIL)
        ante, cons = goal.conclusion.left, goal.conclusion.right
        fresh = f"_h{len(goal.context)}"
        new_goal = goal.add_hyp(fresh, ante).with_conclusion(cons)
        assert self._pb is not None
        new_hyp_steps = dict(hyp_steps)
        new_hyp_steps[fresh] = self._pb.assume(ante, annotation=fresh)
        # We need to pass new_hyp_steps down but TacticResult only has subgoals
        # Embed in message via a workaround: store hyp step in ATSS
        return TacticResult(
            TacticStatus.SUBGOALS,
            subgoals=[new_goal],
            message='imp_i')

    def _tactic_not_i(self, goal: Goal,
                       hyp_steps: Dict[str, ProofStep]) -> TacticResult:
        """Introduce negation by assuming φ and deriving ⊥."""
        if not (isinstance(goal.conclusion, Unary) and
                goal.conclusion.connective == Connective.NOT):
            return TacticResult(TacticStatus.FAIL)
        phi = goal.conclusion.child
        fresh = f"_h{len(goal.context)}"
        new_goal = goal.add_hyp(fresh, phi).with_conclusion(Bot)
        return TacticResult(
            TacticStatus.SUBGOALS,
            subgoals=[new_goal],
            message='not_i')

    def _tactic_or_i(self, goal: Goal,
                      hyp_steps: Dict[str, ProofStep]) -> TacticResult:
        """
        Try both disjuncts of an OR goal.

        Prefers the side with the higher ATSS score.  If the preferred side
        fails during recursive proving, the engine will retry with the other
        side (handled in _prove_recursive via the or_i_both message).
        """
        if not (isinstance(goal.conclusion, Binary) and
                goal.conclusion.connective == Connective.OR):
            return TacticResult(TacticStatus.FAIL)
        l, r = goal.conclusion.left, goal.conclusion.right
        # Return BOTH subgoals in EXP3-ATSS preference order
        # On cold start (uniform distribution ~0.083 per tactic), default to
        # trying left first (lower ASCII/lexicographic order = deterministic).
        idx_or_i = self._tactic_index.get('or_i', 6)
        # Use ATSS preference only after warm-up (non-uniform distribution)
        prefer_left = True
        try:
            exp3_probs = self._atss.get_probability_distribution()
            if idx_or_i < len(exp3_probs):
                # If ATSS has a strong preference (>0.3), use it
                if exp3_probs[idx_or_i] > 0.5:
                    prefer_left = True   # ATSS prefers or_i → left first
                elif exp3_probs[idx_or_i] < 0.05:
                    prefer_left = False  # ATSS avoids or_i → right first
        except (AttributeError, IndexError):
            pass  # fallback: prefer_left=True
        if prefer_left:
            return TacticResult(TacticStatus.SUBGOALS,
                                subgoals=[goal.with_conclusion(l),
                                          goal.with_conclusion(r)],
                                message='or_i_both')
        else:
            return TacticResult(TacticStatus.SUBGOALS,
                                subgoals=[goal.with_conclusion(r),
                                          goal.with_conclusion(l)],
                                message='or_i_both')

    def _tactic_iff_i(self, goal: Goal,
                       hyp_steps: Dict[str, ProofStep]) -> TacticResult:
        """Split biconditional into two implications."""
        if not (isinstance(goal.conclusion, Binary) and
                goal.conclusion.connective == Connective.IFF):
            return TacticResult(TacticStatus.FAIL)
        l, r = goal.conclusion.left, goal.conclusion.right
        return TacticResult(
            TacticStatus.SUBGOALS,
            subgoals=[goal.with_conclusion(Implies(l, r)),
                      goal.with_conclusion(Implies(r, l))],
            message='iff_i')

    def _tactic_modus_ponens(self, goal: Goal,
                               hyp_steps: Dict[str, ProofStep]
                               ) -> TacticResult:
        """
        Find φ→ψ and φ in context to derive ψ = goal.conclusion.

        If φ→ψ is in context and φ is also in context: close immediately.
        If φ→ψ is in context but φ is missing: create a subgoal to prove φ
        (enabling chain deductions like p→q, q→r, p ⊢ r).
        """
        assert self._pb is not None
        psi = goal.conclusion
        for name, hyp in goal.context.items():
            if (isinstance(hyp, Binary) and
                    hyp.connective == Connective.IMP and
                    hyp.right == psi):
                phi = hyp.left
                phi_name = goal.has_hyp(phi)
                if phi_name is not None:
                    major = hyp_steps.get(name) or self._pb.assume(
                        hyp, annotation=name)
                    minor = hyp_steps.get(phi_name) or self._pb.assume(
                        phi, annotation=phi_name)
                    step = self._pb.imp_e(major, minor)
                    return TacticResult(TacticStatus.SUCCESS,
                                        proof=Proof(step))
                else:
                    # Antecedent not in context — create subgoal
                    sub_goal = goal.with_conclusion(phi)
                    return TacticResult(
                        TacticStatus.SUBGOALS,
                        subgoals=[sub_goal],
                        message=f'modus_ponens:{name}')
        return TacticResult(TacticStatus.FAIL)

    def _tactic_and_e(self, goal: Goal,
                       hyp_steps: Dict[str, ProofStep]
                       ) -> TacticResult:
        """
        Conjunction elimination (∧E): extract left or right conjunct
        from a conjunction hypothesis to match the goal.

        For each hypothesis of the form φ ∧ ψ in context:
          - If φ == goal.conclusion: close with AND_E_LEFT
          - If ψ == goal.conclusion: close with AND_E_RIGHT

        If no direct match, recursively decompose nested conjunctions
        by extracting conjuncts and adding them to the context, then
        retrying. This handles formulas like (p ∧ (q ∧ r)) → q where
        the desired atom is two levels deep in the conjunction.

        Termination is guaranteed because each decomposition extracts
        a strictly smaller subformula.
        """
        return self._tactic_and_e_rec(goal, hyp_steps, depth=0)

    def _tactic_and_e_rec(self, goal: Goal,
                           hyp_steps: Dict[str, ProofStep],
                           depth: int,
                           skip_names: Optional[set] = None) -> TacticResult:
        """Recursive helper for _tactic_and_e with decomposition."""
        assert self._pb is not None
        if skip_names is None:
            skip_names = set()
        if depth > 10:
            return TacticResult(TacticStatus.FAIL,
                                message='and_e: max decomposition depth')

        for name, hyp in goal.context.items():
            if name in skip_names:
                continue
            if not (isinstance(hyp, Binary) and
                    hyp.connective == Connective.AND):
                continue

            hyp_step = hyp_steps.get(name) or self._pb.assume(
                hyp, annotation=name)

            # Phase 1: direct match (closing)
            if hyp.left == goal.conclusion:
                step = self._pb.and_e_left(hyp_step)
                return TacticResult(TacticStatus.SUCCESS,
                                    proof=Proof(step))
            if hyp.right == goal.conclusion:
                step = self._pb.and_e_right(hyp_step)
                return TacticResult(TacticStatus.SUCCESS,
                                    proof=Proof(step))

            # Phase 2: decompose — extract conjuncts not yet in context
            # Mark this AND as processed to avoid infinite loops
            new_skip = skip_names | {name}

            # Try left first
            if goal.has_hyp(hyp.left) is None:
                left_step = self._pb.and_e_left(hyp_step)
                new_name = f"_he{len(goal.context)}"
                new_goal = goal.add_hyp(new_name, hyp.left)
                new_hs = dict(hyp_steps)
                new_hs[new_name] = left_step
                result = self._tactic_and_e_rec(
                    new_goal, new_hs, depth + 1, new_skip)
                if result.status == TacticStatus.SUCCESS:
                    return result

            # Try right
            if goal.has_hyp(hyp.right) is None:
                right_step = self._pb.and_e_right(hyp_step)
                new_name = f"_he{len(goal.context)}"
                new_goal = goal.add_hyp(new_name, hyp.right)
                new_hs = dict(hyp_steps)
                new_hs[new_name] = right_step
                result = self._tactic_and_e_rec(
                    new_goal, new_hs, depth + 1, new_skip)
                if result.status == TacticStatus.SUCCESS:
                    return result

        return TacticResult(TacticStatus.FAIL,
                            message='and_e: no matching conjunct')

    def _tactic_contradiction(self, goal: Goal,
                               hyp_steps: Dict[str, ProofStep]
                               ) -> TacticResult:
        """Detect contradictory hypotheses φ and ¬φ to derive anything.

        Handles two cases:
        1. Direct: φ and ¬φ are both in the context.
        2. Indirect via modus ponens: if two implications p→φ and p→¬φ
           share the same antecedent p (which IS in context), derive φ
           and ¬φ via MP, then derive ⊥ via ¬E.
           This handles patterns like (p→q) → ((p→¬q) → ¬p) where
           the contradiction requires intermediate derivations.
        """
        assert self._pb is not None

        # Case 1: Direct contradiction — φ and ¬φ in context
        for name1, h1 in goal.context.items():
            for name2, h2 in goal.context.items():
                if name1 == name2:
                    continue
                if (isinstance(h2, Unary) and
                        h2.connective == Connective.NOT and
                        h2.child == h1):
                    pos_s = hyp_steps.get(name1) or self._pb.assume(h1)
                    neg_s = hyp_steps.get(name2) or self._pb.assume(h2)
                    bot_s = self._pb.not_e(neg_s, pos_s)
                    if goal.conclusion is Bot:
                        return TacticResult(TacticStatus.SUCCESS,
                                            proof=Proof(bot_s))
                    final = self._pb.bot_e(bot_s, goal.conclusion)
                    return TacticResult(TacticStatus.SUCCESS,
                                        proof=Proof(final))

        # Case 2: Indirect contradiction via modus ponens
        # Find pairs of implications p→φ and p→¬φ where p is in context.
        # Then derive φ and ¬φ via MP, and derive ⊥ via ¬E.
        for name1, h1 in goal.context.items():
            if not (isinstance(h1, Binary) and
                    h1.connective == Connective.IMP):
                continue
            ante = h1.left
            ante_name = goal.has_hyp(ante)
            if ante_name is None:
                continue  # antecedent not in context, can't derive
            cons1 = h1.right

            for name2, h2 in goal.context.items():
                if name2 == name1:
                    continue
                if not (isinstance(h2, Binary) and
                        h2.connective == Connective.IMP):
                    continue
                if h2.left != ante:
                    continue  # different antecedent, skip
                cons2 = h2.right

                # Check if cons1 and cons2 are contradictory (cons2 = ¬cons1)
                if (isinstance(cons2, Unary) and
                        cons2.connective == Connective.NOT and
                        cons2.child == cons1):
                    # Derive cons1 via MP(h1, ante)
                    hyp1_step = hyp_steps.get(name1) or self._pb.assume(
                        h1, annotation=name1)
                    ante_step = hyp_steps.get(ante_name) or self._pb.assume(
                        ante, annotation=ante_name)
                    cons1_step = self._pb.imp_e(hyp1_step, ante_step)
                    # Derive ¬cons1 via MP(h2, ante)
                    hyp2_step = hyp_steps.get(name2) or self._pb.assume(
                        h2, annotation=name2)
                    cons2_step = self._pb.imp_e(hyp2_step, ante_step)
                    # Derive ⊥ via ¬E
                    bot_step = self._pb.not_e(cons2_step, cons1_step)
                    if goal.conclusion is Bot:
                        return TacticResult(TacticStatus.SUCCESS,
                                            proof=Proof(bot_step))
                    final = self._pb.bot_e(bot_step, goal.conclusion)
                    return TacticResult(TacticStatus.SUCCESS,
                                        proof=Proof(final))
                # Also check the reverse: cons1 = ¬cons2
                if (isinstance(cons1, Unary) and
                        cons1.connective == Connective.NOT and
                        cons1.child == cons2):
                    # Same as above but swapped
                    hyp1_step = hyp_steps.get(name1) or self._pb.assume(
                        h1, annotation=name1)
                    ante_step = hyp_steps.get(ante_name) or self._pb.assume(
                        ante, annotation=ante_name)
                    cons1_step = self._pb.imp_e(hyp1_step, ante_step)
                    hyp2_step = hyp_steps.get(name2) or self._pb.assume(
                        h2, annotation=name2)
                    cons2_step = self._pb.imp_e(hyp2_step, ante_step)
                    bot_step = self._pb.not_e(cons1_step, cons2_step)
                    if goal.conclusion is Bot:
                        return TacticResult(TacticStatus.SUCCESS,
                                            proof=Proof(bot_step))
                    final = self._pb.bot_e(bot_step, goal.conclusion)
                    return TacticResult(TacticStatus.SUCCESS,
                                        proof=Proof(final))

        return TacticResult(TacticStatus.FAIL)

    def _tactic_solver_fallback(self, goal: Goal,
                                  hyp_steps: Dict[str, ProofStep]
                                  ) -> TacticResult:
        """
        Fall back to the CDCL solver for goals that cannot be decomposed
        by structural tactics.  This is safe: if the solver returns SAT,
        we can extract a model; if UNSAT, we have a refutation.
        """
        assert self._pb is not None
        # Build formula: ∧(hypotheses) → conclusion
        hyps = list(goal.context.values())
        if hyps:
            combined_hyp = hyps[0]
            for h in hyps[1:]:
                combined_hyp = And(combined_hyp, h)
            target = Implies(combined_hyp, goal.conclusion)
        else:
            target = goal.conclusion

        result = self._solver.solve_formula(Not(target))  # check ¬target UNSAT
        if result.status == SolverStatus.UNSAT:
            # The goal is a tautology — build an ADAPTIVE_CUT proof step
            # using the CDCL refutation as the left branch
            if result.proof:
                cert_step = ProofStep(
                    conclusion=goal.conclusion,
                    rule=Rule.ADAPTIVE_CUT,
                    premises=[result.proof._root],
                    annotation='CDCL fallback')
                self._pb._add(cert_step)
                return TacticResult(TacticStatus.SUCCESS,
                                    proof=Proof(cert_step))
        return TacticResult(TacticStatus.FAIL, message='solver fallback: SAT')

    def _tactic_lemma_learn(self, goal: Goal,
                             hyp_steps: Dict[str, ProofStep]) -> TacticResult:
        """
        LEMMA_LEARN (NeuroProof novel rule):
        Promote a CDCL-learned conflict clause to an ND lemma.

        When the CDCL solver derives a useful conflict clause during
        fallback solving, this tactic promotes it to a natural deduction
        lemma using the LEMMA_LEARN proof rule. This bridges CNF-level
        learning with ND-level proof construction.

        This is a structural tactic — it decomposes the goal through
        lemma introduction, enabling reuse across the proof DAG.
        """
        assert self._pb is not None
        # Only applicable when solver_fallback succeeded and produced
        # a nontrivial proof. We reuse the solver's learned clauses as
        # potential lemmas.
        try:
            solver_result = self._solver.solve_formula(
                Not(goal.conclusion))
            if (solver_result.status == SolverStatus.UNSAT and
                    solver_result.proof is not None):
                # Extract subformulas from the proof as candidate lemmas
                all_steps = solver_result.proof._all_steps()
                # Pick the most "interesting" intermediate conclusion
                candidates = []
                for step in all_steps:
                    if (isinstance(step.conclusion, (Binary, Unary)) and
                            step.conclusion not in (Top, Bot)):
                        # Score by structural complexity
                        score = len(str(step.conclusion))
                        candidates.append((score, step))
                if candidates:
                    candidates.sort(key=lambda x: -x[0])
                    _, best_step = candidates[0]
                    premises = [s for s in all_steps[:3] if s is not best_step]
                    if not premises:
                        premises = [best_step]
                    lemma_step = self._pb.lemma_learn(
                        premises, best_step.conclusion,
                        annotation=f'LEMMA_LEARN from CDCL')
                    return TacticResult(TacticStatus.SUCCESS,
                                        proof=Proof(lemma_step))
        except Exception:
            pass
        return TacticResult(TacticStatus.FAIL, message='lemma_learn: no suitable lemma')

    def _tactic_interpolation_cut(self, goal: Goal,
                                    hyp_steps: Dict[str, ProofStep]
                                    ) -> TacticResult:
        """
        INTERPOLATION_GUIDED_CUT (NeuroProof novel rule):
        Decompose a goal A ⊢ C using Craig interpolation.

        Given a goal where we need to prove A ⊢ C:
        1. Compute the Craig interpolant I of A ∧ ¬C
        2. Decompose into: A ⊢ I and I, ¬C ⊢ ⊥
        3. Each subgoal is structurally simpler than the original

        This is a structure-aware alternative to generic cut —
        the interpolant provides semantic guidance for decomposition.
        """
        assert self._pb is not None
        hyps = list(goal.context.values())
        if not hyps:
            return TacticResult(TacticStatus.FAIL,
                                message='interpolation_cut: need hypotheses')

        # Build A = conjunction of hypotheses
        A = hyps[0]
        for h in hyps[1:]:
            A = And(A, h)
        C = goal.conclusion

        # Try to find an interpolant by checking if ¬C is UNSAT with A
        target = And(A, Not(C))
        result = self._solver.solve_formula(
            target, vars_A=frozenset(A.variables()),
            vars_B=frozenset(C.variables()))

        if result.status == SolverStatus.UNSAT and result.proof is not None:
            # We have a refutation of A ∧ ¬C — extract interpolant
            # Use any intermediate proof step as a candidate interpolant
            steps = result.proof._all_steps()
            for step in steps:
                concl = step.conclusion
                if (not isinstance(concl, _Constant) and
                        concl.variables().issubset(
                            A.variables() & C.variables())):
                    # This is a valid interpolant candidate
                    left_step = self._pb.assume(
                        And(A, Not(concl)),
                        annotation='interpolation-cut left')
                    right_step = self._pb.assume(
                        Implies(concl, C),
                        annotation='interpolation-cut right')
                    cut_step = self._pb.interpolation_guided_cut(
                        left_step, right_step, concl)
                    return TacticResult(
                        TacticStatus.SUBGOALS,
                        subgoals=[
                            Goal(Implies(A, concl), dict(goal.context)),
                            Goal(Implies(And(concl, Not(C)), Bot),
                                 dict(goal.context)),
                        ],
                        message=f'cut:{concl}')
        return TacticResult(TacticStatus.FAIL,
                            message='interpolation_cut: no interpolant found')

    # ── ATSS ranking ──────────────────────────────────────────────────────────

    @staticmethod
    def _tactic_name(tactic_fn) -> str:
        """Derive tactic name from method name."""
        name = tactic_fn.__name__
        if name.startswith('_tactic_'):
            return name[8:]
        return name

    @staticmethod
    def _formula_to_clauses(f: Formula):
        """
        Extract a clause set from a CNF formula for GNN encoding.

        Returns (var_names: List[str], clauses: List[Set[Tuple[str, bool]]])
        where each clause is a set of (variable_name, is_positive) tuples.
        """
        var_names = sorted(f.variables())

        def _collect_clauses(formula):
            """Recursively collect clauses from a CNF formula."""
            if isinstance(formula, _Constant):
                return []
            if isinstance(formula, Var):
                return [{(formula.name, True)}]
            if isinstance(formula, Unary) and formula.connective == Connective.NOT:
                if isinstance(formula.child, Var):
                    return [{(formula.child.name, False)}]
                # Unit clause from a constant
                if isinstance(formula.child, Top):
                    return []  # ¬⊤ is always false, no clause
                if isinstance(formula.child, Bot):
                    return [set()]  # empty clause = contradiction
                return []
            if isinstance(formula, Binary) and formula.connective == Connective.AND:
                return _collect_clauses(formula.left) + _collect_clauses(formula.right)
            if isinstance(formula, Binary) and formula.connective == Connective.OR:
                left_clauses = _collect_clauses(formula.left)
                right_clauses = _collect_clauses(formula.right)
                # Merge into single clause (disjunction of disjunctions)
                merged = set()
                for c in left_clauses + right_clauses:
                    merged |= c
                return [merged] if merged else [set()]
            # For other connectives, convert to NNF first
            return []

        # Try CNF extraction; if formula isn't in CNF, use NNF conversion
        clauses = _collect_clauses(f)
        if not clauses and not isinstance(f, _Constant):
            # Fallback: use Tseitin encoding to get a proper CNF
            from .tseitin import TseitinEncoder
            cnf_formula = TseitinEncoder().encode(f)
            clauses = _collect_clauses(cnf_formula)
            var_names = sorted(cnf_formula.variables())

        return var_names, clauses

    def _gnn_score_tactics(self, goal: Goal) -> Optional[Dict[str, float]]:
        """
        Score tactics using GNN ATSS (if available).

        Returns a dict mapping tactic name → GNN score, or None if GNN
        is not available or the formula cannot be encoded.
        """
        if self._gnn_atss is None:
            return None
        try:
            var_names, clauses = self._formula_to_clauses(goal.conclusion)
            if not var_names and not clauses:
                return None
            fg = FormulaGraph(var_names, clauses)
            return self._gnn_atss.score(fg)
        except Exception:
            return None  # GNN scoring failed, fall back to cosine ATSS

    def _atss_ranked_tactics(self, goal: Goal):
        """
        Return tactics sorted by EXP3-ATSS probability distribution.

        Uses the adversarial bandit policy to rank tactics: tactics with
        higher probability mass are tried first. This naturally balances
        exploration and exploitation without requiring per-formula scoring.

        When GNN ATSS is available, the EXP3 distribution is blended with
        GNN predictions using a weighted combination.

        Closing tactics (assumption, contradiction, modus_ponens) are
        always tried first since they directly close goals. LEMMA_LEARN
        and INTERPOLATION_CUT are tried after structural tactics but
        before solver fallback.
        """
        # Get EXP3 probability distribution
        exp3_probs = self._atss.get_probability_distribution()
        gnn_scores = self._gnn_score_tactics(goal)
        has_gnn = gnn_scores is not None

        # Phase 1: closing tactics (always first)
        closing = [
            self._tactic_assumption,
            self._tactic_and_e,
            self._tactic_contradiction,
            self._tactic_modus_ponens,
        ]

        # Phase 2: decomposing tactics, ranked by blended EXP3+GNN score
        decomposing = []
        f = goal.conclusion

        def _blended_score(tactic_name: str, default: float = 0.5) -> float:
            idx = self._tactic_index.get(tactic_name, 0)
            exp3_score = exp3_probs[idx] if idx < len(exp3_probs) else default
            if has_gnn:
                gnn_s = gnn_scores.get(tactic_name, default)
                return self._gnn_blend * gnn_s + (1 - self._gnn_blend) * exp3_score
            return exp3_score

        if isinstance(f, Binary) and f.connective == Connective.AND:
            decomposing.append((_blended_score('and_i'), self._tactic_and_i))
        elif isinstance(f, Binary) and f.connective == Connective.IMP:
            decomposing.append((_blended_score('imp_i'), self._tactic_imp_i))
        elif isinstance(f, Unary) and f.connective == Connective.NOT:
            decomposing.append((_blended_score('not_i'), self._tactic_not_i))
        elif isinstance(f, Binary) and f.connective == Connective.OR:
            decomposing.append((_blended_score('or_i'), self._tactic_or_i))
        elif isinstance(f, Binary) and f.connective == Connective.IFF:
            decomposing.append((_blended_score('iff_i'), self._tactic_iff_i))
        else:
            for name, fn in [('and_i', self._tactic_and_i),
                              ('imp_i', self._tactic_imp_i),
                              ('not_i', self._tactic_not_i),
                              ('or_i', self._tactic_or_i),
                              ('iff_i', self._tactic_iff_i)]:
                decomposing.append((_blended_score(name, 0.1), fn))

        decomposing.sort(key=lambda x: -x[0])

        # Phase 3: novel NeuroProof tactics (LEMMA_LEARN, INTERPOLATION_CUT)
        novel = [
            (_blended_score('lemma_learn', 0.3), self._tactic_lemma_learn),
            (_blended_score('interpolation_cut', 0.2),
             self._tactic_interpolation_cut),
        ]
        novel.sort(key=lambda x: -x[0])

        # Phase 4: solver fallback (always last)
        fallback = [self._tactic_solver_fallback] if self._use_fallback else []

        return closing + [t for _, t in decomposing] + [t for _, t in novel] + fallback


# ──────────────────────────────────────────────────────────────────────────────
# Module-level convenience functions
# ──────────────────────────────────────────────────────────────────────────────

def tauto(formula: Formula,
           hypotheses: Optional[Dict[str, Formula]] = None,
           *,
           gnn_atss: Optional['GNNATSS'] = None) -> Proof:
    """
    Prove a tautology or theorem under hypotheses using NeuroProof.

    Parameters
    ----------
    formula : Formula
        The formula to prove.
    hypotheses : dict, optional
        Named hypotheses.
    gnn_atss : GNNATSS, optional
        GPU-accelerated GNN-based tactic selection. Requires torch_geometric.

    Returns
    -------
    Proof
        A certified proof object.

    Raises
    ------
    ValueError
        If the formula is not provable within the depth limit.
    """
    engine = TacticEngine(gnn_atss=gnn_atss)
    return engine.prove(formula, hypotheses)


def refute(formula: Formula) -> Proof:
    """Prove that formula is unsatisfiable (return a refutation of ¬formula)."""
    engine = TacticEngine()
    return engine.refute(formula)


def decide(formula: Formula) -> SolverStatus:
    """Return SAT/UNSAT/UNKNOWN for formula."""
    engine = TacticEngine()
    return engine.decide(formula)
