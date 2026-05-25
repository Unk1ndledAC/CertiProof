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
from .solver import NeuroProofSolver, ATSS, SolverStatus
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
        self._solver = NeuroProofSolver(atss=self._atss)
        self._max_depth = max_depth
        self._pb: Optional[ProofBuilder] = None
        # GNN-based tactic selection (optional enhancement over cosine ATSS)
        self._gnn_atss = gnn_atss if _HAS_GNN and gnn_atss is not None else None
        self._gnn_blend: float = 0.5  # weight for GNN vs cosine ATSS
        self._use_fallback = use_fallback

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
                f"(ATSS-guided search exhausted)")
        self._atss.record_success(formula)
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
                self._atss.record_success(goal.conclusion)
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
                            self._atss.record_failure(sg.conclusion)
                    if not solved:
                        self._gnn_feedback(goal, tactic, success=False)
                        all_solved = False
                else:
                    for sg in result.subgoals:
                        ss = self._prove_recursive(sg, hyp_steps)
                        if ss is None:
                            all_solved = False
                            self._atss.record_failure(sg.conclusion)
                            break
                        sub_steps.append(ss)
                    if not all_solved:
                        self._gnn_feedback(goal, tactic, success=False)
                if all_solved:
                    # Compose the step from sub-steps
                    step = self._compose(goal, result, sub_steps, hyp_steps)
                    if step is not None:
                        self._atss.record_success(goal.conclusion)
                        self._gnn_feedback(goal, tactic, success=True)
                        self._atss.store_lemma(step)
                        return step

        self._atss.record_failure(goal.conclusion)
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
            # Determine which side was first
            l, r = goal.conclusion.left, goal.conclusion.right
            if self._atss.score(l) >= self._atss.score(r):
                return pb.or_i_left(sub_steps[0], r)
            else:
                return pb.or_i_right(l, sub_steps[0])
        if msg == 'imp_i' and len(sub_steps) == 1:
            assert isinstance(goal.conclusion, Binary)
            hyp_f = goal.conclusion.left
            hyp_step = pb.assume(hyp_f, annotation='imp_i hyp')
            return pb.imp_i(hyp_step, sub_steps[0])
        if msg == 'not_i' and len(sub_steps) == 1:
            assert isinstance(goal.conclusion, Unary)
            hyp_f = goal.conclusion.child
            hyp_step = pb.assume(hyp_f, annotation='not_i hyp')
            return pb.not_i(hyp_step, sub_steps[0])
        if msg == 'iff_i' and len(sub_steps) == 2:
            return pb.iff_i(sub_steps[0], sub_steps[1])
        if msg.startswith('cut:') and len(sub_steps) == 2:
            cut_f = parse(msg[4:])
            return pb.adaptive_cut(sub_steps[0], sub_steps[1], cut_f)
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
        # Return BOTH subgoals in ATSS-preferred order
        if self._atss.score(l) >= self._atss.score(r):
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
        return TacticResult(TacticStatus.FAIL)

    def _tactic_contradiction(self, goal: Goal,
                               hyp_steps: Dict[str, ProofStep]
                               ) -> TacticResult:
        """Detect contradictory hypotheses φ and ¬φ to derive anything."""
        assert self._pb is not None
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

    # ── ATSS ranking ──────────────────────────────────────────────────────────

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
        Return tactics sorted by ATSS success prediction for this goal.

        When GNN ATSS is available, the final ranking blends:
          - cosine-similarity ATSS (formula-level success rate)
          - GNN ATSS (structure-level tactic suitability)
        using a weighted combination with weight self._gnn_blend.

        Closing tactics (assumption, contradiction, modus_ponens) are tried
        first since they directly close goals without decomposition.  Then
        decomposing tactics are ranked by the combined score.  Solver
        fallback is always last.
        """
        # Optionally get GNN tactic scores
        gnn_scores = self._gnn_score_tactics(goal)
        has_gnn = gnn_scores is not None

        def _tactic_name(tactic_fn) -> str:
            """Derive tactic name from method name."""
            name = tactic_fn.__name__  # e.g. '_tactic_and_i'
            if name.startswith('_tactic_'):
                return name[8:]  # 'and_i'
            return name

        # Phase 1: closing tactics (always first, in order of cheapness)
        closing = [
            self._tactic_assumption,
            self._tactic_contradiction,
            self._tactic_modus_ponens,
        ]

        # Phase 2: decomposing tactics, ranked by blended score
        decomposing = []
        f = goal.conclusion
        alpha = self._gnn_blend if has_gnn else 0.0  # GNN weight
        beta = 1.0 - alpha  # cosine ATSS weight

        def _blend(cosine_score: float, tactic_name: str) -> float:
            """Combine cosine ATSS score with GNN tactic score."""
            if not has_gnn:
                return cosine_score
            gnn_s = gnn_scores.get(tactic_name, 0.5)
            return alpha * gnn_s + beta * cosine_score

        if isinstance(f, Binary) and f.connective == Connective.AND:
            cs = self._atss.score(f.left) + self._atss.score(f.right)
            decomposing.append((_blend(cs, 'and_i'), self._tactic_and_i))
        elif isinstance(f, Binary) and f.connective == Connective.IMP:
            cs = self._atss.score(f.right)
            decomposing.append((_blend(cs, 'imp_i'), self._tactic_imp_i))
        elif isinstance(f, Unary) and f.connective == Connective.NOT:
            cs = self._atss.score(Bot)
            decomposing.append((_blend(cs, 'not_i'), self._tactic_not_i))
        elif isinstance(f, Binary) and f.connective == Connective.OR:
            cs = max(self._atss.score(f.left), self._atss.score(f.right))
            decomposing.append((_blend(cs, 'or_i'), self._tactic_or_i))
        elif isinstance(f, Binary) and f.connective == Connective.IFF:
            cs = self._atss.score(f.left) + self._atss.score(f.right)
            decomposing.append((_blend(cs, 'iff_i'), self._tactic_iff_i))
        else:
            # Fallback: include all decomposing tactics (they will just fail)
            for name, fn in [('and_i', self._tactic_and_i),
                              ('imp_i', self._tactic_imp_i),
                              ('not_i', self._tactic_not_i),
                              ('or_i', self._tactic_or_i),
                              ('iff_i', self._tactic_iff_i)]:
                decomposing.append((_blend(0.0, name), fn))

        decomposing.sort(key=lambda x: -x[0])

        # Phase 3: solver fallback (always last, unless disabled)
        fallback = [self._tactic_solver_fallback] if self._use_fallback else []

        return closing + [t for _, t in decomposing] + fallback


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
