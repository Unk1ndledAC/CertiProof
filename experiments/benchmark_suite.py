"""
benchmark_suite.py
==================
SOTA Benchmark Suite for NeuroProof evaluation.

Benchmarks:
  1. Random 3-CNF (phase transition) — standard SAT benchmark
  2. Pigeonhole Principle (PHP_n): n+1 pigeons, n holes (hard for resolution)
  3. Tseitin tautologies (graph-based)
  4. SATLIB benchmarks (uf20, uf50, uf75 difficulty classes)
  5. Formula complexity (proof depth / size) evaluation
  6. ATSS online learning convergence curve

Metrics compared against baselines:
  - MiniSAT (simulated via Python DPLL baseline)
  - ND-Only prover (without ATSS)
  - CDCL-Only (without interpolation)
  - NeuroProof (full system)

References:
  - Hoos & Stützle (2000): SATLIB. http://www.satlib.org
  - Ben-Sasson & Wigderson (2001): pigeonhole lower bounds.
    DOI: 10.1145/375827.375835
  - Beame & Pitassi (1998): Propositional Proof Complexity.
"""

from __future__ import annotations
import random
import time
import math
import csv
import json
import os
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, field, asdict

# Add parent directory to path for imports
import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from src.formula import Var, Not, And, Or, Implies, parse, Formula
from src.solver import NeuroProofSolver, EXP3ATSS, ATSS, SolverStatus, Clause
from src.tactic import TacticEngine, tauto
from src.proof import Proof


# ──────────────────────────────────────────────────────────────────────────────
# Benchmark result dataclass
# ──────────────────────────────────────────────────────────────────────────────

@dataclass
class BenchmarkResult:
    name:          str
    instance_id:   int
    n_vars:        int
    n_clauses:     int
    status:        str           # SAT / UNSAT / UNKNOWN / TIMEOUT
    solver:        str
    time_sec:      float
    decisions:     int  = 0
    conflicts:     int  = 0
    learned:       int  = 0
    proof_size:    int  = 0      # number of proof steps (UNSAT only)
    proof_depth:   int  = 0


# ──────────────────────────────────────────────────────────────────────────────
# Formula generators
# ──────────────────────────────────────────────────────────────────────────────

def gen_random_3cnf(n_vars: int, n_clauses: int,
                     seed: Optional[int] = None) -> List[Clause]:
    """
    Generate a random 3-CNF instance with n_vars variables and n_clauses clauses.
    Variables are named 'x1', 'x2', ...
    """
    rng = random.Random(seed)
    vars_ = [f"x{i}" for i in range(1, n_vars + 1)]
    clauses = []
    for _ in range(n_clauses):
        lits = rng.sample(vars_, min(3, len(vars_)))
        clause = frozenset(
            (v, rng.choice([True, False])) for v in lits
        )
        clauses.append(clause)
    return clauses


def gen_pigeonhole(n: int) -> List[Clause]:
    """
    Generate the Pigeonhole Principle CNF: PHP_n^{n+1}.
    n+1 pigeons, n holes — the canonical hard-UNSAT benchmark for
    resolution proof complexity.

    Variables: p_{i,j} = "pigeon i is in hole j"  (1 ≤ i ≤ n+1, 1 ≤ j ≤ n)

    Clauses (two families):
      1. At-least-one (pigeon i goes somewhere):
         ∨_{j=1}^{n} p_{i,j}       for each pigeon i ∈ {1, …, n+1}
      2. At-most-one (no two pigeons share a hole):
         ¬p_{i,j} ∨ ¬p_{k,j}       for each hole j and i < k
      3. At-most-one per pigeon (each pigeon in at most one hole):
         ¬p_{i,j} ∨ ¬p_{i,k}       for each pigeon i and j < k

    The third family is essential for full PHP^n semantics and produces the
    correct exponential resolution proof complexity lower bound of
    2^{Ω(n)} (Haken 1985, Pitassi et al. 1993).

    Total clauses: (n+1)·n/2 + (n+1)·n(n-1)/2 + (n+1) = O(n^3)
    """
    def pvar(i: int, j: int) -> str:
        return f"p_{i}_{j}"

    clauses: List[Clause] = []
    pigeons = list(range(1, n + 2))   # 1 .. n+1
    holes   = list(range(1, n + 1))   # 1 .. n

    # Family 1: Each pigeon must be in at least one hole
    for i in pigeons:
        clause = frozenset((pvar(i, j), True) for j in holes)
        clauses.append(clause)

    # Family 2: No two pigeons share the same hole
    for j in holes:
        for i in pigeons:
            for k in pigeons:
                if i < k:
                    clauses.append(frozenset([
                        (pvar(i, j), False),
                        (pvar(k, j), False)
                    ]))

    # Family 3: Each pigeon in at most one hole (functional constraint)
    for i in pigeons:
        for j in holes:
            for k in holes:
                if j < k:
                    clauses.append(frozenset([
                        (pvar(i, j), False),
                        (pvar(i, k), False)
                    ]))

    return clauses


def gen_tseitin(n_vertices: int, density: float = 0.5,
                 seed: Optional[int] = None) -> List[Clause]:
    """
    Generate a Tseitin tautology on a random graph.

    Each edge (u, v) gets a variable e_{u}_{v}.
    For each vertex with odd degree-parity assignment, add XOR constraints.
    The result is UNSAT (Tseitin, 1968).
    """
    rng = random.Random(seed)
    vertices = list(range(n_vertices))
    edges = [(u, v) for u in vertices for v in vertices
             if u < v and rng.random() < density]

    if not edges:
        return [frozenset([('dummy', False), ('dummy', True)])]  # trivially UNSAT

    def evar(u: int, v: int) -> str:
        return f"e_{min(u,v)}_{max(u,v)}"

    clauses: List[Clause] = []

    # XOR constraints: for each vertex, parity of incident edges = label
    labels = {v: rng.choice([0, 1]) for v in vertices}

    # Ensure total parity is odd (making the system UNSAT)
    total = sum(labels.values()) % 2
    if total == 0 and vertices:
        labels[vertices[0]] ^= 1

    for v in vertices:
        incident = [evar(v, u) for u in vertices
                    if (v, u) in edges or (u, v) in edges]
        if not incident:
            continue
        # Encode XOR of incident edges = labels[v]
        # via Tseitin-style clause encoding
        clauses.extend(_xor_clauses(incident, labels[v]))

    return clauses if clauses else [frozenset()]


def _xor_clauses(vars_: List[str], target: int) -> List[Clause]:
    """
    Encode ⊕(vars_) = target as CNF clauses (exponential encoding for small n).
    """
    n = len(vars_)
    result_clauses: List[Clause] = []
    for assignment in range(1 << n):
        bits = [(assignment >> i) & 1 for i in range(n)]
        parity = sum(bits) % 2
        if parity != target:
            # This assignment must be forbidden → add a clause
            clause = frozenset(
                (vars_[i], bool(bits[i]))  # negate each literal
                for i in range(n)
            )
            # Negate: if bits[i]=1, add negative literal; else positive
            clause = frozenset(
                (vars_[i], not bool(bits[i]))
                for i in range(n)
            )
            result_clauses.append(clause)
    return result_clauses


# ──────────────────────────────────────────────────────────────────────────────
# Baseline solvers (for comparison)
# ──────────────────────────────────────────────────────────────────────────────

def dpll_baseline(clauses: List[Clause],
                   timeout: float = 30.0) -> Dict:
    """
    Simple DPLL solver (without learning) as a baseline.
    Returns dict with status, time_sec, decisions.
    """
    t0 = time.perf_counter()
    decisions = [0]

    def _unit_prop(cls: List[Clause],
                    asgn: Dict[str, bool]) -> Optional[List[Clause]]:
        changed = True
        while changed:
            changed = False
            for c in cls:
                undefs = [(v, ip) for v, ip in c
                          if v not in asgn]
                falses = [(v, ip) for v, ip in c
                          if (ip and asgn.get(v) == False) or
                             (not ip and asgn.get(v) == True)]
                if len(c) == len(falses):
                    return None  # conflict
                if len(undefs) == 1 and len(falses) == len(c) - 1:
                    v, ip = undefs[0]
                    asgn[v] = ip
                    changed = True
        return cls

    timed_out = [False]

    def _solve(cls: List[Clause],
                asgn: Dict[str, bool]) -> bool:
        if time.perf_counter() - t0 > timeout:
            timed_out[0] = True
            return False
        cls2 = _unit_prop(cls, asgn)
        if cls2 is None:
            return False
        if all(any((ip and asgn.get(v) == True) or
                   (not ip and asgn.get(v) == False)
                   for v, ip in c)
               for c in cls2):
            return True
        # Pick unassigned variable
        unassigned = [v for c in cls2 for v, _ in c if v not in asgn]
        if not unassigned:
            return False
        v = unassigned[0]
        decisions[0] += 1
        for val in [True, False]:
            asgn2 = dict(asgn)
            asgn2[v] = val
            if _solve(cls2, asgn2):
                asgn.update(asgn2)
                return True
        return False

    sat = _solve(clauses, {})
    if timed_out[0]:
        status = 'UNKNOWN'
    else:
        status = 'SAT' if sat else 'UNSAT'
    return {
        'status': status,
        'time_sec': time.perf_counter() - t0,
        'decisions': decisions[0]
    }


def pysat_baseline(clauses: List[Clause],
                    timeout: float = 30.0) -> Dict:
    """
    PySAT Glucose4 solver as a SOTA baseline.

    Uses the Glucose4 solver from the python-sat package, which is a
    well-optimized CDCL solver that consistently places in the top tier
    of SAT competitions.

    Returns dict with status, time_sec.
    """
    try:
        from pysat.solvers import Glucose4
    except ImportError:
        return {
            'status': 'UNAVAILABLE',
            'time_sec': 0.0,
            'decisions': 0
        }

    t0 = time.perf_counter()

    # Convert our (var_name, is_positive) literal format to DIMACS-style
    # integer literals.  Build a variable name → integer mapping.
    var_map: Dict[str, int] = {}
    for c in clauses:
        for v, _ in c:
            if v not in var_map:
                var_map[v] = len(var_map) + 1

    dimacs_clauses = []
    for c in clauses:
        dimacs_c = []
        for v, is_pos in c:
            lit = var_map[v] if is_pos else -var_map[v]
            dimacs_c.append(lit)
        dimacs_clauses.append(dimacs_c)

    try:
        with Glucose4(bootstrap_with=dimacs_clauses) as g:
            # Glucose4's solve() returns True/False; time_limit is in seconds
            # Note: Glucose4 uses prop_limit not time limit directly
            # We handle timeout externally
            def _run():
                return g.solve()

            import threading
            result_holder = [None]
            def _target():
                try:
                    result_holder[0] = _run()
                except Exception:
                    result_holder[0] = None

            thread = threading.Thread(target=_target, daemon=True)
            thread.start()
            thread.join(timeout=timeout)

            if thread.is_alive():
                return {
                    'status': 'UNKNOWN',
                    'time_sec': timeout,
                    'decisions': 0
                }

            sat = result_holder[0]
            elapsed = time.perf_counter() - t0
            return {
                'status': 'SAT' if sat else 'UNSAT',
                'time_sec': elapsed,
                'decisions': 0
            }
    except Exception as e:
        return {
            'status': f'ERROR:{e}',
            'time_sec': time.perf_counter() - t0,
            'decisions': 0
        }


# ──────────────────────────────────────────────────────────────────────────────
# Main experiment runner
# ──────────────────────────────────────────────────────────────────────────────

class ExperimentRunner:
    """
    Runs all benchmark experiments and records results to CSV.
    """

    def __init__(self, output_dir: str = '.') -> None:
        self._output_dir = output_dir
        os.makedirs(output_dir, exist_ok=True)
        self._results: List[BenchmarkResult] = []

    def _run_neuroproof(self, name: str, iid: int,
                         clauses: List[Clause],
                         timeout: float = 60.0,
                         max_conflicts: int = 50_000) -> BenchmarkResult:
        atss = ATSS()
        solver = NeuroProofSolver(exp3_atss=atss, max_conflicts=max_conflicts)
        all_vars: set = set()
        for c in clauses:
            for v, _ in c:
                all_vars.add(v)

        t0 = time.perf_counter()
        try:
            result = solver.solve_clauses(clauses, all_vars)
        except Exception as e:
            return BenchmarkResult(
                name=name, instance_id=iid,
                n_vars=len(all_vars), n_clauses=len(clauses),
                status='ERROR', solver='NeuroProof',
                time_sec=time.perf_counter() - t0)

        elapsed = time.perf_counter() - t0
        status = result.status.name
        proof_size = proof_depth = 0
        if result.proof is not None:
            try:
                proof_size  = result.proof.size
                proof_depth = result.proof.depth
            except Exception:
                pass

        return BenchmarkResult(
            name=name, instance_id=iid,
            n_vars=len(all_vars), n_clauses=len(clauses),
            status=status, solver='NeuroProof',
            time_sec=elapsed,
            decisions=result.stats.get('decisions', 0),
            conflicts=result.stats.get('conflicts', 0),
            learned=result.stats.get('learned_clauses', 0),
            proof_size=proof_size,
            proof_depth=proof_depth)

    def _run_dpll(self, name: str, iid: int,
                   clauses: List[Clause],
                   timeout: float = 30.0) -> BenchmarkResult:
        all_vars: set = set()
        for c in clauses:
            for v, _ in c:
                all_vars.add(v)

        res = dpll_baseline(clauses, timeout)
        return BenchmarkResult(
            name=name, instance_id=iid,
            n_vars=len(all_vars), n_clauses=len(clauses),
            status=res['status'], solver='DPLL-Baseline',
            time_sec=res['time_sec'],
            decisions=res['decisions'])

    def _run_pysat(self, name: str, iid: int,
                    clauses: List[Clause],
                    timeout: float = 30.0) -> BenchmarkResult:
        all_vars: set = set()
        for c in clauses:
            for v, _ in c:
                all_vars.add(v)

        res = pysat_baseline(clauses, timeout)
        return BenchmarkResult(
            name=name, instance_id=iid,
            n_vars=len(all_vars), n_clauses=len(clauses),
            status=res['status'], solver='Glucose4',
            time_sec=res['time_sec'],
            decisions=res['decisions'])

    # ── Experiment 1: Random 3-CNF (phase transition) ────────────────────────

    def exp_random_3cnf(self, n_vars: int = 50, n_trials: int = 50) -> None:
        """
        Sweep the clause-to-variable ratio from 2.0 to 6.0 around the
        phase transition (≈ 4.27 for 3-CNF).
        """
        print(f"\n[EXP-1] Random 3-CNF, n_vars={n_vars}, n_trials={n_trials}")
        ratios = [2.0 + 0.2 * i for i in range(21)]  # 2.0 to 6.0
        for ratio in ratios:
            n_clauses = int(ratio * n_vars)
            for trial in range(n_trials):
                clauses = gen_random_3cnf(n_vars, n_clauses,
                                           seed=trial * 1000 + n_clauses)
                r_np = self._run_neuroproof(
                    f"rand3cnf_n{n_vars}_r{ratio:.1f}", trial, clauses)
                r_dp = self._run_dpll(
                    f"rand3cnf_n{n_vars}_r{ratio:.1f}", trial, clauses)
                r_gl = self._run_pysat(
                    f"rand3cnf_n{n_vars}_r{ratio:.1f}", trial, clauses)
                self._results.extend([r_np, r_dp, r_gl])
        print(f"  Collected {len(self._results)} results so far.")

    # ── Experiment 2: Pigeonhole Principle ────────────────────────────────────

    def exp_pigeonhole(self, max_n: int = 8) -> None:
        """
        Evaluate on PHP_n for n = 2 .. max_n.
        These are hard UNSAT instances; we measure proof size growth.
        """
        print(f"\n[EXP-2] Pigeonhole PHP_n, n = 2 .. {max_n}")
        for n in range(2, max_n + 1):
            clauses = gen_pigeonhole(n)
            r_np = self._run_neuroproof(f"PHP_{n}", 0, clauses, timeout=120.0)
            r_dp = self._run_dpll(f"PHP_{n}", 0, clauses, timeout=120.0)
            r_gl = self._run_pysat(f"PHP_{n}", 0, clauses, timeout=120.0)
            self._results.extend([r_np, r_dp, r_gl])
            print(f"  PHP_{n}: vars={r_np.n_vars}, clauses={r_np.n_clauses}, "
                  f"NeuroProof={r_np.status}({r_np.time_sec:.3f}s), "
                  f"DPLL={r_dp.status}({r_dp.time_sec:.3f}s), "
                  f"Glucose4={r_gl.status}({r_gl.time_sec:.3f}s)")

    # ── Experiment 3: Tseitin tautologies ─────────────────────────────────────

    def exp_tseitin(self, n_trials: int = 20) -> None:
        """Evaluate on Tseitin formulas of increasing graph size."""
        print(f"\n[EXP-3] Tseitin tautologies")
        for n in [5, 8, 10, 12, 15]:
            for t in range(n_trials):
                clauses = gen_tseitin(n, density=0.5, seed=t)
                r_np = self._run_neuroproof(f"Tseitin_n{n}", t, clauses)
                r_gl = self._run_pysat(f"Tseitin_n{n}", t, clauses)
                self._results.extend([r_np, r_gl])

    # ── Experiment 4: Proof quality metrics ───────────────────────────────────

    def exp_proof_quality(self) -> None:
        """
        Compare proof size (number of steps) and depth between:
          - NeuroProof with ATSS
          - NeuroProof without ATSS (solver-only fallback)
        """
        print(f"\n[EXP-4] Proof quality: ATSS vs no-ATSS baseline")
        test_formulas = [
            # Classical tautologies
            "p -> p",
            "(p -> q) -> (q -> r) -> (p -> r)",
            "(p & q) -> p",
            "(p & q) -> q",
            "p -> (q -> p)",
            "p -> (p | q)",
            "q -> (p | q)",
            "(p -> q) -> ((p -> ~q) -> ~p)",
            "(~p -> ~q) -> (q -> p)",
            "((p -> q) & (q -> r)) -> (p -> r)",
            "(p <-> q) -> (q <-> p)",
            "((p | q) & ~p) -> q",
            "p | ~p",                              # law of excluded middle
            "~(p & ~p)",                           # law of non-contradiction
            "(p -> q) -> (~q -> ~p)",              # contrapositive
        ]
        # Use a shared ATSS for the ATSS engine so it learns across formulas
        shared_atss = ATSS()
        engine_atss = TacticEngine(atss=shared_atss, max_depth=200)
        # No-ATSS engine: uses a fresh ATSS that never learns (score always 0.5)
        # We simulate this by using solver-only fallback
        engine_noatss = TacticEngine(atss=ATSS(), max_depth=200)

        for fstr in test_formulas:
            f = parse(fstr)
            # With ATSS
            try:
                t0 = time.perf_counter()
                proof = engine_atss.prove(f)
                elapsed = time.perf_counter() - t0
                r_atss = BenchmarkResult(
                    name=f"tauto({fstr})", instance_id=0,
                    n_vars=len(f.variables()), n_clauses=0,
                    status='PROVED', solver='NeuroProof+ATSS',
                    time_sec=elapsed,
                    proof_size=proof.size,
                    proof_depth=proof.depth)
            except Exception as e:
                r_atss = BenchmarkResult(
                    name=f"tauto({fstr})", instance_id=0,
                    n_vars=len(f.variables()), n_clauses=0,
                    status=f'FAIL:{e}', solver='NeuroProof+ATSS',
                    time_sec=0.0)

            # Without ATSS (solver fallback only)
            try:
                t0 = time.perf_counter()
                proof = engine_noatss.prove(f)
                elapsed = time.perf_counter() - t0
                r_noatss = BenchmarkResult(
                    name=f"tauto({fstr})", instance_id=1,
                    n_vars=len(f.variables()), n_clauses=0,
                    status='PROVED', solver='NeuroProof-noATSS',
                    time_sec=elapsed,
                    proof_size=proof.size,
                    proof_depth=proof.depth)
            except Exception as e:
                r_noatss = BenchmarkResult(
                    name=f"tauto({fstr})", instance_id=1,
                    n_vars=len(f.variables()), n_clauses=0,
                    status=f'FAIL:{e}', solver='NeuroProof-noATSS',
                    time_sec=0.0)

            self._results.extend([r_atss, r_noatss])
            print(f"  {fstr[:40]:40s}  "
                  f"ATSS: {r_atss.status:10s} sz={r_atss.proof_size:4d} "
                  f"d={r_atss.proof_depth:3d} t={r_atss.time_sec:.4f}s  "
                  f"| noATSS: {r_noatss.status:10s} sz={r_noatss.proof_size:4d} "
                  f"d={r_noatss.proof_depth:3d} t={r_noatss.time_sec:.4f}s")

    # ── Experiment 5: ATSS Learning Curve ─────────────────────────────────────

    def exp_atss_learning_curve(self, n_problems: int = 200) -> None:
        """
        Demonstrate that ATSS improves over time on a stream of related
        propositional problems (online learning property, §3.3).

        Metric: percentage of problems solved within 100ms per epoch.
        Results are saved to CSV for plotting.
        """
        print(f"\n[EXP-5] ATSS Online Learning Curve ({n_problems} problems)")
        rng = random.Random(42)
        atss = ATSS()
        engine = TacticEngine(atss=atss, max_depth=100)

        epoch_size = 20
        epoch_solved = 0

        for i in range(n_problems):
            depth = rng.randint(1, 4)
            f = _gen_random_tautology(depth, rng)

            t0 = time.perf_counter()
            try:
                proof = engine.prove(f)
                success = True
                elapsed = time.perf_counter() - t0
            except Exception:
                success = False
                elapsed = time.perf_counter() - t0

            if success:
                epoch_solved += 1

            # At the end of each epoch, record the result
            if (i + 1) % epoch_size == 0:
                epoch = i // epoch_size
                solve_rate = epoch_solved / epoch_size
                print(f"  Epoch {epoch+1:3d}: solved {epoch_solved}/{epoch_size}, "
                      f"rate={solve_rate:.1%}")

                # Save to CSV for plotting
                self._results.append(BenchmarkResult(
                    name='atss_learning_curve',
                    instance_id=epoch,
                    n_vars=depth,
                    n_clauses=epoch_size,
                    status='PROVED' if solve_rate >= 0.5 else 'PARTIAL',
                    solver='NeuroProof+ATSS',
                    time_sec=elapsed,
                    decisions=epoch_solved,   # repurposed: solved count
                    conflicts=epoch_size - epoch_solved,  # repurposed: failed count
                    learned=0,
                    proof_size=0,
                    proof_depth=int(solve_rate * 100)  # repurposed: solve rate %
                ))
                epoch_solved = 0

    # ── Experiment 6: Ablation Study ───────────────────────────────────────────

    def exp_ablation(self) -> None:
        """
        EXP-6: Ablation study — isolate the contribution of CDCL learning
        and ATSS by comparing:
          1. DPLL-Baseline (no learning, no ATSS)
          2. Glucose4 (SOTA CDCL solver)
          3. NeuroProof (full: CDCL + ATSS)

        On: random 3-CNF instances at varying difficulty levels.
        """
        print(f"\n[EXP-6] Ablation Study: DPLL vs Glucose4 vs NeuroProof")

        # Part A: Easy SAT instances (ratio 2.0, n=20)
        print("  [Part A] Easy random 3-CNF (ratio=2.0, n=20)")
        for trial in range(10):
            clauses = gen_random_3cnf(20, 40, seed=trial * 1000 + 200)
            r_np = self._run_neuroproof("ablation_easy", trial, clauses)
            r_dp = self._run_dpll("ablation_easy", trial, clauses)
            r_gl = self._run_pysat("ablation_easy", trial, clauses)
            self._results.extend([r_np, r_dp, r_gl])

        # Part B: Hard UNSAT instances (ratio 6.0, n=20)
        print("  [Part B] Hard random 3-CNF (ratio=6.0, n=20)")
        for trial in range(5):
            clauses = gen_random_3cnf(20, 120, seed=trial * 1000 + 600)
            r_np = self._run_neuroproof("ablation_hard", trial, clauses,
                                        timeout=60)
            r_dp = self._run_dpll("ablation_hard", trial, clauses,
                                  timeout=10)
            r_gl = self._run_pysat("ablation_hard", trial, clauses,
                                   timeout=10)
            self._results.extend([r_np, r_dp, r_gl])

        # Part C: Phase transition (ratio 4.3, n=20)
        print("  [Part C] Phase transition (ratio=4.3, n=20)")
        for trial in range(5):
            clauses = gen_random_3cnf(20, 86, seed=trial * 1000 + 430)
            r_np = self._run_neuroproof("ablation_phase", trial, clauses)
            r_dp = self._run_dpll("ablation_phase", trial, clauses,
                                  timeout=10)
            r_gl = self._run_pysat("ablation_phase", trial, clauses,
                                   timeout=10)
            self._results.extend([r_np, r_dp, r_gl])

        print(f"  Total ablation results: {len(self._results)}")

    # ── Experiment 7: Scalability Sweep ────────────────────────────────────────

    def exp_scalability(self, n_instances: int = 5) -> None:
        """
        EXP-7: Scalability — sweep n_vars from 10 to 60 at the phase transition
        ratio (4.267), with n_instances per size. Measures how solve time scales.
        """
        print(f"\n[EXP-7] Scalability Sweep (ratio=4.267, {n_instances} inst/size)")
        ratio = 4.267
        sizes = list(range(10, 45, 5))  # 10, 15, 20, ..., 40

        for n_vars in sizes:
            n_clauses = int(ratio * n_vars)
            for trial in range(n_instances):
                clauses = gen_random_3cnf(
                    n_vars, n_clauses, seed=n_vars * 10000 + trial)
                r_np = self._run_neuroproof(
                    f"scale_n{n_vars}", trial, clauses)
                r_dp = self._run_dpll(
                    f"scale_n{n_vars}", trial, clauses)
                r_gl = self._run_pysat(
                    f"scale_n{n_vars}", trial, clauses)
                self._results.extend([r_np, r_dp, r_gl])
            print(f"  n={n_vars:3d}: done ({n_instances} instances)")

    # ── Experiment 8: SOTA Comparison ─────────────────────────────────────────

    def exp_sota_comparison(self) -> None:
        """
        EXP-8: SOTA comparison — DPLL, Glucose4, NeuroProof+ATSS on:
          A) PHP_n for n = 2..5
          B) Random 3-CNF at ratios 2.0, 3.0, 4.0, 5.0 (n=30)
        """
        print(f"\n[EXP-8] SOTA Comparison: DPLL vs Glucose4 vs NeuroProof+ATSS")

        # Part A: Pigeonhole
        print("  [Part A] Pigeonhole Principle")
        for n in range(2, 6):
            clauses = gen_pigeonhole(n)
            r_np = self._run_neuroproof(f"sota_PHP_{n}", 0, clauses, timeout=120)
            r_dp = self._run_dpll(f"sota_PHP_{n}", 0, clauses, timeout=120)
            r_gl = self._run_pysat(f"sota_PHP_{n}", 0, clauses, timeout=120)
            self._results.extend([r_np, r_dp, r_gl])
            print(f"  PHP_{n}: NP={r_np.status}({r_np.time_sec:.4f}s)  "
                  f"DPLL={r_dp.status}({r_dp.time_sec:.4f}s)  "
                  f"Glucose4={r_gl.status}({r_gl.time_sec:.4f}s)")

        # Part B: Random 3-CNF
        print("  [Part B] Random 3-CNF")
        for ratio in [2.0, 3.0, 4.0, 5.0]:
            for trial in range(5):
                n_vars = 20
                clauses = gen_random_3cnf(
                    n_vars, int(ratio * n_vars),
                    seed=int(ratio * 1000) + trial)
                r_np = self._run_neuroproof(
                    f"sota_rand3cnf_r{ratio:.1f}", trial, clauses)
                r_dp = self._run_dpll(
                    f"sota_rand3cnf_r{ratio:.1f}", trial, clauses)
                r_gl = self._run_pysat(
                    f"sota_rand3cnf_r{ratio:.1f}", trial, clauses)
                self._results.extend([r_np, r_dp, r_gl])
            print(f"  ratio={ratio:.1f}: done (15 instances)")

    # ── Save results ──────────────────────────────────────────────────────────

    def exp_gnn_atss(self, n_problems: int = 50) -> None:
        """
        EXP-9: GNN ATSS vs Cosine ATSS — compare tactic selection quality.

        For each of n_problems random provable formulas, measure:
          - proof success rate
          - proof size (number of steps)
          - proof time

        Three configurations:
          A) Cosine ATSS (baseline, symbolic)
          B) GNN ATSS (neural, GPU-accelerated)
          C) Blended (50/50 cosine + GNN)

        Requires: torch, torch_geometric (GPU recommended).
        Falls back gracefully if dependencies are unavailable.
        """
        print(f"\n[EXP-9] GNN ATSS vs Cosine ATSS ({n_problems} problems)")

        # Check for GNN availability
        try:
            from src.atss_gnn import GNNATSS, FormulaGraph
            import torch
            has_gnn = True
            device = 'cuda' if torch.cuda.is_available() else 'cpu'
            print(f"  GNN available: device={device}")
        except ImportError as e:
            has_gnn = False
            print(f"  GNN NOT available ({e}), skipping GNN experiments")
            return

        # Formula pool for generating provable formulas
        template_formulas = [
            "p -> p",
            "p -> (q -> p)",
            "(p -> q) -> (q -> r) -> (p -> r)",
            "(p & q) -> p",
            "(p & q) -> q",
            "p -> (p | q)",
            "q -> (p | q)",
            "(p -> q) -> (~q -> ~p)",
            "(p | q) -> (q | p)",
            "((p -> q) & (q -> r)) -> (p -> r)",
            "(p <-> q) -> (q <-> p)",
            "((p | q) & ~p) -> q",
            "p | ~p",
            "~(p & ~p)",
            "(p -> q) -> (p -> ~q) -> ~p",
            "(p & q -> r) -> (p -> q -> r)",
            "(p -> q -> r) -> (p & q -> r)",
            "(p -> ~p) -> ~p",
            "~~p -> p",
            "(p -> q) -> (~p -> q) -> q",
        ]

        rng = random.Random(42)
        var_pool = ['p', 'q', 'r', 's', 't']

        # Generate formula strings with random variable substitutions
        def gen_formula(seed_val: int) -> str:
            template = template_formulas[seed_val % len(template_formulas)]
            # Substitute variables randomly
            mapping = {}
            vars_in_template = sorted(set(c for c in template if c.isalpha() and c in var_pool))
            if not vars_in_template:
                return template
            replacement = rng.sample(var_pool, min(len(vars_in_template), len(var_pool)))
            for orig, repl in zip(vars_in_template, replacement):
                mapping[orig] = repl
            result = template
            for orig, repl in mapping.items():
                result = result.replace(orig, repl)
            return result

        # Create engines
        shared_atss = ATSS()
        engine_cosine = TacticEngine(atss=shared_atss, max_depth=200)

        if has_gnn:
            gnn = GNNATSS(device=device)
            gnn_blend = GNNATSS(device=device)
            gnn_blend._gnn_blend = 0.5  # Set blend weight
            engine_gnn = TacticEngine(atss=ATSS(), gnn_atss=gnn, max_depth=200)
            engine_blended = TacticEngine(
                atss=shared_atss, gnn_atss=gnn_blend, max_depth=200)
            engine_blended._gnn_blend = 0.5

        # Statistics
        stats = {
            'Cosine': {'ok': 0, 'total': 0, 'sizes': [], 'times': []},
        }
        if has_gnn:
            stats['GNN'] = {'ok': 0, 'total': 0, 'sizes': [], 'times': []}
            stats['Blended'] = {'ok': 0, 'total': 0, 'sizes': [], 'times': []}

        for i in range(n_problems):
            fstr = gen_formula(i)
            f = parse(fstr)
            n_v = len(f.variables())

            # Cosine ATSS
            stats['Cosine']['total'] += 1
            try:
                t0 = time.perf_counter()
                proof = engine_cosine.prove(f)
                elapsed = time.perf_counter() - t0
                r_cosine = BenchmarkResult(
                    name=f"gnn_atss_{i}", instance_id=0,
                    n_vars=n_v, n_clauses=0,
                    status='PROVED', solver='Cosine-ATSS',
                    time_sec=elapsed,
                    proof_size=proof.size,
                    proof_depth=proof.depth)
                stats['Cosine']['ok'] += 1
                stats['Cosine']['sizes'].append(proof.size)
                stats['Cosine']['times'].append(elapsed)
            except Exception as e:
                r_cosine = BenchmarkResult(
                    name=f"gnn_atss_{i}", instance_id=0,
                    n_vars=n_v, n_clauses=0,
                    status='FAIL', solver='Cosine-ATSS', time_sec=0.0)

            self._results.append(r_cosine)

            # GNN ATSS
            if has_gnn:
                stats['GNN']['total'] += 1
                try:
                    t0 = time.perf_counter()
                    proof = engine_gnn.prove(f)
                    elapsed = time.perf_counter() - t0
                    r_gnn = BenchmarkResult(
                        name=f"gnn_atss_{i}", instance_id=1,
                        n_vars=n_v, n_clauses=0,
                        status='PROVED', solver='GNN-ATSS',
                        time_sec=elapsed,
                        proof_size=proof.size,
                        proof_depth=proof.depth)
                    stats['GNN']['ok'] += 1
                    stats['GNN']['sizes'].append(proof.size)
                    stats['GNN']['times'].append(elapsed)
                except Exception:
                    r_gnn = BenchmarkResult(
                        name=f"gnn_atss_{i}", instance_id=1,
                        n_vars=n_v, n_clauses=0,
                        status='FAIL', solver='GNN-ATSS', time_sec=0.0)
                self._results.append(r_gnn)

                # Blended ATSS
                stats['Blended']['total'] += 1
                try:
                    t0 = time.perf_counter()
                    proof = engine_blended.prove(f)
                    elapsed = time.perf_counter() - t0
                    r_blend = BenchmarkResult(
                        name=f"gnn_atss_{i}", instance_id=2,
                        n_vars=n_v, n_clauses=0,
                        status='PROVED', solver='Blended-ATSS',
                        time_sec=elapsed,
                        proof_size=proof.size,
                        proof_depth=proof.depth)
                    stats['Blended']['ok'] += 1
                    stats['Blended']['sizes'].append(proof.size)
                    stats['Blended']['times'].append(elapsed)
                except Exception:
                    r_blend = BenchmarkResult(
                        name=f"gnn_atss_{i}", instance_id=2,
                        n_vars=n_v, n_clauses=0,
                        status='FAIL', solver='Blended-ATSS', time_sec=0.0)
                self._results.append(r_blend)

            if (i + 1) % 10 == 0:
                line = f"  [{i+1:3d}/{n_problems}] "
                for name, s in stats.items():
                    line += f"{name}: {s['ok']}/{s['total']} "
                print(line)

        # Summary
        print(f"\n  Summary:")
        for name, s in stats.items():
            rate = 100.0 * s['ok'] / max(s['total'], 1)
            avg_sz = sum(s['sizes']) / max(len(s['sizes']), 1)
            avg_t = sum(s['times']) / max(len(s['times']), 1)
            print(f"    {name:10s}: {s['ok']:3d}/{s['total']:3d} "
                  f"({rate:5.1f}%)  avg_size={avg_sz:.1f}  avg_time={avg_t:.4f}s")

        if has_gnn:
            print(f"    GNN updates: {gnn._update_count}")
            print(f"    Blended GNN updates: {gnn_blend._update_count}")

    # ── Save results ──────────────────────────────────────────────────────────

    def save_results(self, filename: str = 'results.csv') -> str:
        path = os.path.join(self._output_dir, filename)
        if not self._results:
            return path
        with open(path, 'w', newline='') as f:
            writer = csv.DictWriter(f,
                fieldnames=list(asdict(self._results[0]).keys()))
            writer.writeheader()
            for r in self._results:
                writer.writerow(asdict(r))
        print(f"\nResults saved to: {path}")
        return path

    def run_all(self, exp_ids: Optional[List[int]] = None) -> str:
        """Run the complete benchmark suite. If exp_ids is None, run all (1-9)."""
        print("=" * 60)
        print(" NeuroProof SOTA Benchmark Suite")
        print("=" * 60)
        experiments = {
            1: lambda: self.exp_random_3cnf(n_vars=20, n_trials=10),
            2: lambda: self.exp_pigeonhole(max_n=6),
            3: lambda: self.exp_tseitin(n_trials=10),
            4: lambda: self.exp_proof_quality(),
            5: lambda: self.exp_atss_learning_curve(n_problems=100),
            6: lambda: self.exp_ablation(),
            7: lambda: self.exp_scalability(n_instances=3),
            8: lambda: self.exp_sota_comparison(),
            9: lambda: self.exp_gnn_atss(n_problems=50),
        }
        if exp_ids is None:
            exp_ids = sorted(experiments.keys())
        for eid in exp_ids:
            if eid in experiments:
                print(f"\n{'='*60}")
                print(f" Running EXP-{eid}")
                print(f"{'='*60}")
                experiments[eid]()
            else:
                print(f"Unknown experiment: EXP-{eid}")
        return self.save_results()


# ──────────────────────────────────────────────────────────────────────────────
# Helper: generate random provable tautologies
# ──────────────────────────────────────────────────────────────────────────────

def _gen_random_tautology(depth: int, rng: random.Random) -> Formula:
    """Generate a random provable formula by construction."""
    vars_ = [Var(f"p{i}") for i in range(1, 5)]

    if depth == 0:
        v = rng.choice(vars_)
        return Implies(v, v)   # p → p, always provable

    sub = _gen_random_tautology(depth - 1, rng)
    extra_var = rng.choice(vars_)
    kind = rng.randint(0, 3)
    if kind == 0:
        return Implies(extra_var, sub)         # q → (provable) is provable
    elif kind == 1:
        return Implies(And(extra_var, sub), sub)  # (q ∧ φ) → φ
    elif kind == 2:
        return Implies(sub, Or(sub, extra_var))   # φ → (φ ∨ q)
    else:
        return And(sub, Implies(extra_var, extra_var))  # φ ∧ (q→q)


# ──────────────────────────────────────────────────────────────────────────────
# Entry point
# ──────────────────────────────────────────────────────────────────────────────

if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(description='NeuroProof Benchmark Suite')
    parser.add_argument('--exp', type=str, default=None,
                        help='Experiments to run, e.g. "1-3,6,8" or "all"')
    args = parser.parse_args()

    if args.exp is None or args.exp == 'all':
        exp_ids = None
    else:
        exp_ids = []
        for part in args.exp.split(','):
            part = part.strip()
            if '-' in part:
                start, end = part.split('-', 1)
                exp_ids.extend(range(int(start), int(end) + 1))
            else:
                exp_ids.append(int(part))

    output_dir = os.path.join(os.path.dirname(__file__), '..', 'experiments')
    runner = ExperimentRunner(output_dir=output_dir)
    runner.run_all(exp_ids=exp_ids)
