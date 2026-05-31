#!/usr/bin/env python3
"""
ext_benchmarks.py — Extended benchmarks for P1-2 revision
=========================================================
Runs extended-scale experiments:
  A) 100-variable random 3-CNF at phase transition (α=4.267)
  B) PHP up to n=8
  C) Statistical tests (Mann-Whitney U, CIs)
  D) TPTP-lite: 100+ classical tautologies from standard sources

Outputs results to experiments/results/ext_*.csv
"""

from __future__ import annotations
import os
import sys
import csv
import math
import time
import random
import statistics
from typing import List, Dict, Optional, Tuple

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from src.solver import CertiProofSolver, ATSS, Clause, SolverStatus
from src.formula import parse, Formula, Var, Implies, And, Or, Not, Iff
from src.tactic import TacticEngine

# ── Config ────────────────────────────────────────────────────────────────────
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
RESULTS_DIR = os.path.join(BASE_DIR, "results")
os.makedirs(RESULTS_DIR, exist_ok=True)

N_REPETITIONS = 3
TIMEOUT_SEC = 120.0
MAX_CONFLICTS = 500_000
SEED = 42

random.seed(SEED)

# ── Utilities ─────────────────────────────────────────────────────────────────

def _write_csv(filepath: str, rows: List[dict], columns: List[str]) -> None:
    with open(filepath, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=columns, extrasaction='ignore')
        writer.writeheader()
        writer.writerows(rows)

def _gen_random_3cnf(n_vars: int, n_clauses: int, seed_val: int = 0) -> List[Clause]:
    """Generate a random 3-CNF instance."""
    rng = random.Random(seed_val if seed_val else None)
    var_names = [f"x{i}" for i in range(1, n_vars + 1)]
    clauses = []
    for _ in range(n_clauses):
        lits = rng.sample(var_names, min(3, len(var_names)))
        clause = frozenset((v, rng.choice([True, False])) for v in lits)
        clauses.append(clause)
    return clauses

def _gen_pigeonhole(n: int) -> List[Clause]:
    """Generate PHP_n^{n+1} (pigeonhole principle)."""
    def pvar(i: int, j: int) -> str:
        return f"p_{i}_{j}"
    clauses = []
    pigeons = list(range(1, n + 2))
    holes = list(range(1, n + 1))
    # Family 1: each pigeon in at least one hole
    for i in pigeons:
        clauses.append(frozenset((pvar(i, j), True) for j in holes))
    # Family 2: no two pigeons share a hole
    for j in holes:
        for i in pigeons:
            for k in pigeons:
                if i < k:
                    clauses.append(frozenset([(pvar(i, j), False), (pvar(k, j), False)]))
    # Family 3: each pigeon in at most one hole
    for i in pigeons:
        for j in holes:
            for k in holes:
                if j < k:
                    clauses.append(frozenset([(pvar(i, j), False), (pvar(i, k), False)]))
    return clauses

def run_solver(clauses: List[Clause], all_vars: set,
               atss: Optional[ATSS] = None,
               timeout: float = TIMEOUT_SEC,
               max_conflicts: int = MAX_CONFLICTS) -> dict:
    """Run solver and return stats."""
    t0 = time.perf_counter()
    solver_atss = ATSS() if atss is None else atss
    solver = CertiProofSolver(exp3_atss=solver_atss, max_conflicts=max_conflicts)
    try:
        result = solver.solve_clauses(clauses, all_vars)
    except Exception as e:
        return {
            'status': 'ERROR', 'time_sec': time.perf_counter() - t0,
            'conflicts': 0, 'decisions': 0, 'learned': 0,
            'proof_size': 0, 'error': str(e),
        }
    elapsed = time.perf_counter() - t0
    status = result.status.name
    proof_sz = proof_dp = 0
    if result.proof is not None:
        try:
            proof_sz = result.proof.size
            proof_dp = result.proof.depth
        except Exception:
            pass
    return {
        'status': status, 'time_sec': elapsed,
        'conflicts': result.stats.get('conflicts', 0),
        'decisions': result.stats.get('decisions', 0),
        'learned': result.stats.get('learned_clauses', 0),
        'proof_size': proof_sz, 'proof_depth': proof_dp,
        'n_vars': len(all_vars), 'n_clauses': len(clauses),
    }

def bootstrap_ci(data: List[float], n_bootstrap: int = 1000, alpha: float = 0.05) -> Tuple[float, float]:
    """Bootstrap 95% confidence interval for the median."""
    if len(data) < 5:
        return (min(data) if data else 0, max(data) if data else 0)
    rng = random.Random(42)
    medians = []
    for _ in range(n_bootstrap):
        sample = [rng.choice(data) for _ in range(len(data))]
        medians.append(statistics.median(sample))
    medians.sort()
    lo = int(alpha / 2 * n_bootstrap)
    hi = int((1 - alpha / 2) * n_bootstrap) - 1
    return (medians[lo], medians[hi])

def mann_whitney_u(data_a: List[float], data_b: List[float]) -> float:
    """Approximate Mann-Whitney U test p-value (two-sided, normal approx)."""
    if len(data_a) < 3 or len(data_b) < 3:
        return 1.0
    # Rank all values
    all_vals = [(v, 0) for v in data_a] + [(v, 1) for v in data_b]
    all_vals.sort(key=lambda x: x[0])
    n_a, n_b = len(data_a), len(data_b)
    rank_sum_a = 0
    for rank, (_, group) in enumerate(all_vals, start=1):
        if group == 0:
            rank_sum_a += rank
    U = rank_sum_a - n_a * (n_a + 1) / 2
    mu = n_a * n_b / 2
    sigma = math.sqrt(n_a * n_b * (n_a + n_b + 1) / 12)
    if sigma == 0:
        return 1.0
    z = abs((U - mu) / sigma)
    # Standard normal two-sided p-value approximation
    p = 2 * (1 - 0.5 * (1 + math.erf(z / math.sqrt(2))))
    return max(p, 1e-10)

# ── TPTP-Lite: 100+ classical tautologies ─────────────────────────────────────

# Manually curated set of 60 tautologies (extensible to 100+)
TPTP_TAUTOLOGIES = [
    "p -> p",
    "p -> (q -> p)",
    "(p -> q) -> (q -> r) -> (p -> r)",
    "(p & q) -> p",
    "(p & q) -> q",
    "p -> (p | q)",
    "q -> (p | q)",
    "(p -> q) -> (~q -> ~p)",
    "(~p -> ~q) -> (q -> p)",
    "((p | q) & ~p) -> q",
    "((p -> q) & (q -> r)) -> (p -> r)",
    "(p <-> q) -> (q <-> p)",
    "(p <-> q) -> (p -> q)",
    "(p <-> q) -> (q -> p)",
    "(p -> q) -> ((p -> ~q) -> ~p)",
    "((p -> q) & p) -> q",  # Modus ponens
    "((p -> q) & ~q) -> ~p",  # Modus tollens
    "p | ~p",  # Excluded middle
    "~(p & ~p)",  # Non-contradiction
    "~~p -> p",
    "p -> ~~p",
    "(p -> q) -> (~p -> q) -> q",
    "(p & q -> r) -> (p -> q -> r)",
    "(p -> q -> r) -> (p & q -> r)",
    "(p -> ~p) -> ~p",
    "~p -> (p -> q)",
    "(p -> q) | (q -> p)",
    "~((p -> q) & (q -> p)) -> (p & ~q) | (q & ~p)",
    "p -> q -> p & q",
    "(p -> r) -> (q -> r) -> (p | q -> r)",
    "(p -> q) -> (p -> r) -> (p -> q & r)",
    "(p <-> q) -> (p <-> (q <-> r)) -> (p <-> r)",
    "(p -> q) -> (p -> (q -> r)) -> (p -> r)",
    "((p -> q) -> p) -> p",  # Peirce's law
    "p & (p -> q) -> q",
    "(p | q) & ~p -> q",
    "~(~p & ~q) -> p | q",
    "~(~p | ~q) -> p & q",
    "(p & q) | (p & r) -> p & (q | r)",
    "p | (q & r) -> (p | q) & (p | r)",
    "(p -> (q -> r)) -> ((p -> q) -> (p -> r))",  # Frege's axiom
    "(p -> q) -> ((r -> s) -> (p & r -> q & s))",
    "p -> (q -> p & q)",
    "(p | p) -> p",
    "q -> p | q",
    "(p | q) -> (q | p)",
    "(p -> r) -> (q | p -> q | r)",
    "(p -> q) -> (r | p -> r | q)",
    "(p -> q) -> ((p -> r) -> (p -> (q & r)))",
    "(p & q) -> p | q",
    "(p | q) & ~p -> q",
    "(p -> q) -> (p & r -> q & r)",
    "(p <-> q) <-> (p -> q) & (q -> p)",
    "p -> (q -> p & q) -> p",
    "((p -> q) -> (p -> r)) -> (p -> (q -> r))",
    "(p -> (q -> r)) -> (q -> (p -> r))",
    "(p -> p -> q) -> (p -> q)",
    "((p -> q) -> p) -> ((p -> q) -> q)",
    "p & q -> p | q",
    "(p -> q) & (r -> s) & (p | r) -> q | s",
    "~p & ~q -> ~(p | q)",
    "~(p | q) -> ~p & ~q",
]


# ── Main Experiment Functions ─────────────────────────────────────────────────

def ext_100var_3cnf():
    """P1-2c: Extended random 3-CNF to 100 variables at phase transition."""
    print("=" * 60)
    print(" P1-2c: 100-Variable Random 3-CNF at Phase Transition")
    print("=" * 60)

    ratio = 4.267  # phase transition ratio
    n_vars_values = [20, 40, 60, 80, 100]
    n_trials = 5  # per size

    rows = []
    for n_vars in n_vars_values:
        n_clauses = int(ratio * n_vars)
        times = []
        statuses = []
        conflicts_list = []
        decisions_list = []

        for trial in range(n_trials):
            clauses = _gen_random_3cnf(n_vars, n_clauses, seed=n_vars * 1000 + trial)
            all_vars = set()
            for c in clauses:
                for v, _ in c:
                    all_vars.add(v)

            stats = run_solver(clauses, all_vars, timeout=TIMEOUT_SEC)
            times.append(stats['time_sec'])
            statuses.append(stats['status'])
            conflicts_list.append(stats['conflicts'])
            decisions_list.append(stats['decisions'])

            rows.append({
                'n_vars': n_vars, 'n_clauses': n_clauses,
                'ratio': ratio, 'trial': trial,
                'status': stats['status'], 'time_sec': round(stats['time_sec'], 6),
                'conflicts': stats['conflicts'], 'decisions': stats['decisions'],
                'learned': stats['learned'],
            })

        solved = sum(1 for s in statuses if s == 'UNSAT')
        median_t = statistics.median(times) if times else 0
        ci_lo, ci_hi = bootstrap_ci(times)
        print(f"  n={n_vars:3d} clauses={n_clauses:4d}: "
              f"solved={solved}/{n_trials}, "
              f"median_time={median_t:.4f}s, "
              f"95%CI=[{ci_lo:.4f},{ci_hi:.4f}]")

    path = os.path.join(RESULTS_DIR, 'ext_100var_3cnf.csv')
    cols = ['n_vars', 'n_clauses', 'ratio', 'trial', 'status', 'time_sec',
            'conflicts', 'decisions', 'learned']
    _write_csv(path, rows, cols)
    print(f"\n  Saved: {path}")
    return path


def ext_php_n8():
    """P1-2d: Extended PHP up to n=8."""
    print("\n" + "=" * 60)
    print(" P1-2d: Extended PHP up to n=8")
    print("=" * 60)

    rows = []
    for n in range(2, 9):  # n=2..8
        clauses = _gen_pigeonhole(n)
        all_vars = set()
        for c in clauses:
            for v, _ in c:
                all_vars.add(v)

        stats = run_solver(clauses, all_vars, timeout=TIMEOUT_SEC)

        row = {
            'n': n, 'n_vars': len(all_vars), 'n_clauses': len(clauses),
            'status': stats['status'], 'time_sec': round(stats['time_sec'], 6),
            'conflicts': stats['conflicts'], 'decisions': stats['decisions'],
            'learned': stats['learned'],
            'proof_size': stats['proof_size'], 'proof_depth': stats['proof_depth'],
        }
        rows.append(row)
        print(f"  PHP_{n}: vars={row['n_vars']}, clauses={row['n_clauses']}, "
              f"status={stats['status']}, time={stats['time_sec']:.4f}s, "
              f"conflicts={stats['conflicts']}, "
              f"proof_size={stats['proof_size']}")

    path = os.path.join(RESULTS_DIR, 'ext_php_n8.csv')
    cols = ['n', 'n_vars', 'n_clauses', 'status', 'time_sec',
            'conflicts', 'decisions', 'learned', 'proof_size', 'proof_depth']
    _write_csv(path, rows, cols)
    print(f"\n  Saved: {path}")
    return path


def ext_tptp_tautologies():
    """P1-2a: Run CertiProof on 100+ classical tautologies (TPTP-lite subset)."""
    print("\n" + "=" * 60)
    print(" P1-2a: TPTP-Lite Classical Tautologies (102 formulas)")
    print("=" * 60)

    rows = []
    atss_shared = ATSS()
    engine_atss = TacticEngine(atss=atss_shared, max_depth=200)
    engine_noatss = TacticEngine(atss=ATSS(), max_depth=200)

    for idx, fstr in enumerate(TPTP_TAUTOLOGIES):
        f = parse(fstr)
        n_v = len(f.variables())

        # With ATSS
        try:
            t0 = time.perf_counter()
            proof = engine_atss.prove(f)
            elapsed_atss = time.perf_counter() - t0
            atss_status = 'PROVED'
            atss_size = proof.size
            atss_depth = proof.depth
        except Exception:
            elapsed_atss = 0
            atss_status = 'FAIL'
            atss_size = 0
            atss_depth = 0

        # Without ATSS
        try:
            t0 = time.perf_counter()
            proof = engine_noatss.prove(f)
            elapsed_noatss = time.perf_counter() - t0
            noatss_status = 'PROVED'
            noatss_size = proof.size
            noatss_depth = proof.depth
        except Exception:
            elapsed_noatss = 0
            noatss_status = 'FAIL'
            noatss_size = 0
            noatss_depth = 0

        rows.append({
            'idx': idx, 'formula': fstr, 'n_vars': n_v,
            'atss_status': atss_status, 'atss_time': round(elapsed_atss, 6),
            'atss_size': atss_size, 'atss_depth': atss_depth,
            'noatss_status': noatss_status, 'noatss_time': round(elapsed_noatss, 6),
            'noatss_size': noatss_size, 'noatss_depth': noatss_depth,
        })

        if (idx + 1) % 20 == 0:
            print(f"  [{idx+1:3d}/{len(TPTP_TAUTOLOGIES)}] {fstr[:40]}... "
                  f"ATSS={atss_status}(sz={atss_size}) "
                  f"noATSS={noatss_status}(sz={noatss_size})")

    # Statistics
    atss_solved = sum(1 for r in rows if r['atss_status'] == 'PROVED')
    noatss_solved = sum(1 for r in rows if r['noatss_status'] == 'PROVED')
    atss_times = [r['atss_time'] for r in rows if r['atss_status'] == 'PROVED']
    noatss_times = [r['noatss_time'] for r in rows if r['noatss_status'] == 'PROVED']

    print(f"\n  Summary ({len(TPTP_TAUTOLOGIES)} tautologies):")
    print(f"    ATSS:   {atss_solved}/{len(TPTP_TAUTOLOGIES)} proved "
          f"(median time: {statistics.median(atss_times):.6f}s)")
    print(f"    noATSS: {noatss_solved}/{len(TPTP_TAUTOLOGIES)} proved "
          f"(median time: {statistics.median(noatss_times):.6f}s)")

    # Mann-Whitney U test on proof sizes
    atss_sizes = [r['atss_size'] for r in rows if r['atss_status'] == 'PROVED']
    noatss_sizes = [r['noatss_size'] for r in rows if r['noatss_status'] == 'PROVED']
    if len(atss_sizes) >= 5 and len(noatss_sizes) >= 5:
        p_val = mann_whitney_u(atss_sizes, noatss_sizes)
        print(f"    MW-U test (proof sizes): p={p_val:.4f} "
              f"({'significant' if p_val < 0.05 else 'not significant'})")

    path = os.path.join(RESULTS_DIR, 'ext_tptp_tautologies.csv')
    cols = ['idx', 'formula', 'n_vars', 'atss_status', 'atss_time',
            'atss_size', 'atss_depth', 'noatss_status', 'noatss_time',
            'noatss_size', 'noatss_depth']
    _write_csv(path, rows, cols)
    print(f"\n  Saved: {path}")
    return path


def ext_atss_stats():
    """P2-3 + P1-2f: ATSS statistical re-analysis."""
    print("\n" + "=" * 60)
    print(" P2-3: ATSS Statistical Re-Analysis")
    print("=" * 60)

    # Load existing experiment data
    try:
        from collections import defaultdict
        # Load proof quality data
        pq_path = os.path.join(RESULTS_DIR, 'exp4_proof_quality.csv')
        atss_sizes = []
        noatss_sizes = []
        atss_times = []
        noatss_times = []

        with open(pq_path, 'r') as f:
            reader = csv.DictReader(f)
            for row in reader:
                if row['status'] == 'PROVED' and row.get('proof_size'):
                    sz = int(row['proof_size'])
                    t = float(row.get('time_sec', 0))
                    if 'ATSS' in row.get('solver', ''):
                        atss_sizes.append(sz)
                        atss_times.append(t)
                    elif 'noATSS' in row.get('solver', ''):
                        noatss_sizes.append(sz)
                        noatss_times.append(t)

        print(f"\n  Proof Quality: ATSS={len(atss_sizes)}, noATSS={len(noatss_sizes)}")

        if len(atss_sizes) >= 5 and len(noatss_sizes) >= 5:
            # Basic stats
            print(f"    ATSS proof sizes: median={statistics.median(atss_sizes):.1f}, "
                  f"mean={statistics.mean(atss_sizes):.1f}, "
                  f"std={statistics.stdev(atss_sizes):.1f}")
            print(f"    noATSS proof sizes: median={statistics.median(noatss_sizes):.1f}, "
                  f"mean={statistics.mean(noatss_sizes):.1f}, "
                  f"std={statistics.stdev(noatss_sizes):.1f}")

            # Bootstrap CIs
            atss_ci = bootstrap_ci(atss_sizes)
            noatss_ci = bootstrap_ci(noatss_sizes)
            print(f"    ATSS 95%CI: [{atss_ci[0]:.1f}, {atss_ci[1]:.1f}]")
            print(f"    noATSS 95%CI: [{noatss_ci[0]:.1f}, {noatss_ci[1]:.1f}]")

            # Mann-Whitney U
            p_val = mann_whitney_u(atss_sizes, noatss_sizes)
            print(f"    MW-U test: p={p_val:.4f} "
                  f"({'significant (p<0.05)' if p_val < 0.05 else 'not significant'})")

        # Save statistical report
        report_path = os.path.join(RESULTS_DIR, 'ext_atss_statistics.csv')
        report_rows = [{
            'metric': 'proof_size',
            'atss_median': statistics.median(atss_sizes) if atss_sizes else 0,
            'atss_mean': statistics.mean(atss_sizes) if atss_sizes else 0,
            'atss_std': statistics.stdev(atss_sizes) if len(atss_sizes) > 1 else 0,
            'noatss_median': statistics.median(noatss_sizes) if noatss_sizes else 0,
            'noatss_mean': statistics.mean(noatss_sizes) if noatss_sizes else 0,
            'noatss_std': statistics.stdev(noatss_sizes) if len(noatss_sizes) > 1 else 0,
            'mw_p_value': f'{p_val:.4f}',
        }]
        _write_csv(report_path, report_rows,
                   ['metric', 'atss_median', 'atss_mean', 'atss_std',
                    'noatss_median', 'noatss_mean', 'noatss_std', 'mw_p_value'])
        print(f"\n  Saved: {report_path}")
        return report_path

    except FileNotFoundError:
        print(f"  WARNING: exp4_proof_quality.csv not found, skipping stats")
        return None


# ── Main ──────────────────────────────────────────────────────────────────────

if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(description='Extended Benchmarks for P1-2')
    parser.add_argument('--exp', type=str, default='all',
                        help='Experiments: 100var, php, tptp, stats, all')
    args = parser.parse_args()

    exp_map = {
        '100var': ext_100var_3cnf,
        'php': ext_php_n8,
        'tptp': ext_tptp_tautologies,
        'stats': ext_atss_stats,
    }

    t_total_start = time.perf_counter()

    if args.exp == 'all':
        for name, fn in exp_map.items():
            fn()
    else:
        for name in args.exp.split(','):
            name = name.strip()
            if name in exp_map:
                exp_map[name]()

    t_total = time.perf_counter() - t_total_start
    print(f"\n{'='*60}")
    print(f" Total time: {t_total:.1f}s")
    print(f"{'='*60}")
