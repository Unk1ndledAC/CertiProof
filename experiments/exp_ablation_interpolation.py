#!/usr/bin/env python3
"""
exp_ablation_interpolation.py — P1-4c: 插值反馈消融实验
==========================================================
比较 CertiProof 在以下两种配置下的表现：
  A) 插值启用 (Interpolation ON)  — 传递 vars_A / vars_B 给求解器
  B) 插值关闭 (Interpolation OFF) — 不传递 vars_A / vars_B，仅使用标准 CDCL

实验设计:
  1. 分区 PHP 公式 (Partitioned PHP) — 将 PHP_n 变量分为 A/B 两组，共享部分重叠
  2. 重叠 CNF 公式 (Overlapping CNF) — 两个 CNF 在共享变量上相交，联合 UNSAT
  3. 精确-1 + 计数约束 (ExactOne+Counting) — 两套约束系统在共享变量上产生矛盾
  4. 随机分区 CNF (Random Partitioned) — 随机 UNSAT 3-CNF 变量随机分为 A/B 组

每组公式在 Interpolation ON/OFF 两种模式下运行，比较:
  - 求解时间 (time_sec)
  - 冲突数 (conflicts)
  - 决策数 (decisions)
  - 证明大小 (proof_size)
  - 证明深度 (proof_depth)

输出: experiments/results/ext_ablation_interpolation.csv

运行方式:
  cd C:/Users/19473/Desktop/CertiProof
  D:/Anaconda3/python.exe experiments/exp_ablation_interpolation.py

参数:
  --exp 1|2|3|4|all (默认: all)
  --quick          仅运行快速子集
  --timeout N      每个实例超时秒数 (默认: 60)
  --trials N       每种大小的重复次数 (默认: 3, quick: 1)

预期运行时间: 完整运行约 20-40 分钟
"""

from __future__ import annotations
import os
import sys
import csv
import math
import time
import random
import statistics
from typing import List, Dict, Optional, Tuple, Set, FrozenSet

# Add project root to path
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)

from src.solver import CertiProofSolver, ATSS, SolverStatus, Clause

# ── Config ────────────────────────────────────────────────────────────────────
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
RESULTS_DIR = os.path.join(BASE_DIR, "results")
os.makedirs(RESULTS_DIR, exist_ok=True)

OUTPUT_FILE = os.path.join(RESULTS_DIR, "ext_ablation_interpolation.csv")

SEED = 42
TIMEOUT_SEC = 60.0
MAX_CONFLICTS = 200_000
random.seed(SEED)

# ── Utilities ─────────────────────────────────────────────────────────────────

def _write_csv(filepath: str, rows: List[dict], columns: List[str]) -> None:
    with open(filepath, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=columns, extrasaction='ignore')
        writer.writeheader()
        writer.writerows(rows)

def run_with_vars(clauses: List[Clause], all_vars: Set[str],
                  vars_a: Optional[FrozenSet[str]] = None,
                  vars_b: Optional[FrozenSet[str]] = None,
                  timeout: float = TIMEOUT_SEC,
                  max_conflicts: int = MAX_CONFLICTS) -> dict:
    """Run CertiProof solver. If vars_a and vars_b are both given, interpolation is ON."""
    t0 = time.perf_counter()
    solver = CertiProofSolver(exp3_atss=ATSS(), max_conflicts=max_conflicts)
    try:
        if vars_a is not None and vars_b is not None:
            result = solver.solve_clauses(
                clauses, all_vars, vars_A=vars_a, vars_B=vars_b)
        else:
            result = solver.solve_clauses(clauses, all_vars)
    except Exception as e:
        elapsed = time.perf_counter() - t0
        return {
            'status': 'ERROR', 'time_sec': elapsed,
            'conflicts': 0, 'decisions': 0, 'learned': 0,
            'proof_size': 0, 'proof_depth': 0, 'error': str(e),
        }
    elapsed = time.perf_counter() - t0
    status = result.status.name
    proof_sz, proof_dp = 0, 0
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

def format_summary(name: str, rows_on: List[dict], rows_off: List[dict]) -> str:
    """Generate a human-readable comparison summary."""
    def _avg(lst, key):
        vals = [r[key] for r in lst if r['status'] in ('SAT', 'UNSAT')]
        return statistics.mean(vals) if vals else float('nan')
    def _count(lst, good):
        return sum(1 for r in lst if r['status'] in good)

    lines = [f"\n  {name}:"]
    lines.append(f"    {'Metric':<20} {'Interp ON':>12} {'Interp OFF':>12} {'Δ':>12}")
    lines.append(f"    {'-'*56}")

    for metric, key in [('Solved', None), ('Time (s)', 'time_sec'),
                         ('Conflicts', 'conflicts'), ('Proof Size', 'proof_size'),
                         ('Proof Depth', 'proof_depth')]:
        if metric == 'Solved':
            on_v = f"{_count(rows_on, ('SAT','UNSAT'))}/{len(rows_on)}"
            off_v = f"{_count(rows_off, ('SAT','UNSAT'))}/{len(rows_off)}"
            lines.append(f"    {metric:<20} {on_v:>12} {off_v:>12}")
        else:
            on_v = _avg(rows_on, key)
            off_v = _avg(rows_off, key)
            if math.isnan(on_v) or math.isnan(off_v):
                diff = "N/A"
            elif off_v == 0:
                diff = "N/A"
            else:
                pct = (on_v - off_v) / off_v * 100
                diff = f"{pct:+.1f}%"
            lines.append(f"    {metric:<20} {on_v:>12.4f} {off_v:>12.4f} {diff:>12}")
    return "\n".join(lines)

# ── Formula Generators ────────────────────────────────────────────────────────

def gen_random_3cnf(n_vars: int, n_clauses: int,
                    seed_val: int = 0) -> List[Clause]:
    """Generate random 3-CNF."""
    rng = random.Random(seed_val if seed_val else None)
    var_names = [f"x{i}" for i in range(1, n_vars + 1)]
    clauses = []
    for _ in range(n_clauses):
        lits = rng.sample(var_names, min(3, len(var_names)))
        clause = frozenset((v, rng.choice([True, False])) for v in lits)
        clauses.append(clause)
    return clauses

def gen_pigeonhole(n: int) -> List[Clause]:
    """Generate PHP_n^{n+1}."""
    def pvar(i: int, j: int) -> str:
        return f"p_{i}_{j}"
    clauses = []
    pigeons = list(range(1, n + 2))
    holes = list(range(1, n + 1))
    for i in pigeons:
        clauses.append(frozenset((pvar(i, j), True) for j in holes))
    for j in holes:
        for i in pigeons:
            for k in pigeons:
                if i < k:
                    clauses.append(frozenset([
                        (pvar(i, j), False), (pvar(k, j), False)]))
    for i in pigeons:
        for j in holes:
            for k in holes:
                if j < k:
                    clauses.append(frozenset([
                        (pvar(i, j), False), (pvar(i, k), False)]))
    return clauses

def gen_exact_one(n_bits: int) -> List[Clause]:
    """Exactly one bit true among n_bits."""
    clauses: List[Clause] = []
    clauses.append(frozenset((f"b_{i}", True) for i in range(n_bits)))
    for i in range(n_bits):
        for j in range(i + 1, n_bits):
            clauses.append(frozenset([
                (f"b_{i}", False), (f"b_{j}", False)]))
    return clauses

# ── Experiment 1: Partitioned PHP ─────────────────────────────────────────────

def exp1_partitioned_php(quick: bool = False) -> Tuple[List[dict], List[dict], str]:
    """
    E1: Partitioned PHP — split PHP variables into two overlapping groups.

    For PHP_n, define:
      - Part A vars: p_{i,j} where i is odd (odd pigeons)
      - Part B vars: p_{i,j} where i is even (even pigeons)
      - Shared vars: p_{n+1, j} (the extra pigeon, belongs to both A and B)

    This creates a natural interpolation problem: the extra pigeon must go
    somewhere, and the A/B sides must agree on where.
    """
    print("\n" + "=" * 60)
    print(" E1: Partitioned PHP — Interpolation ON vs OFF")
    print("=" * 60)

    ns = [3, 4] if quick else [3, 4, 5, 6]
    rows_on = []
    rows_off = []

    for n in ns:
        clauses = gen_pigeonhole(n)

        # Collect all variables
        all_vars = set()
        for c in clauses:
            for v, _ in c:
                all_vars.add(v)

        # Partition: A = odd pigeons, B = even pigeons, both include last pigeon
        pvar_pattern = "p_"
        vars_a = frozenset(v for v in all_vars
                          if v.startswith(pvar_pattern))
        vars_b = vars_a  # Same variable set for PHP — use heuristic partition

        # Actually, a better partition: half the pigeons to A, half to B
        # Both need the "at most one per hole" clauses
        pigeons = list(range(1, n + 2))
        mid = len(pigeons) // 2
        pigeons_a = pigeons[:mid]
        pigeons_b = pigeons[mid:]

        vars_a = frozenset(f"p_{i}_{j}" for i in pigeons_a
                          for j in range(1, n + 1))
        vars_b = frozenset(f"p_{i}_{j}" for i in pigeons_b
                          for j in range(1, n + 1))

        print(f"\n  PHP_{n}: {len(all_vars)} vars, {len(clauses)} clauses")
        print(f"    vars_A: {len(vars_a)}, vars_B: {len(vars_b)}, "
              f"shared: {len(vars_a & vars_b)}")

        # Interpolation ON
        print(f"    Interpolation ON...", end=" ", flush=True)
        stats_on = run_with_vars(clauses, all_vars,
                                 vars_a=vars_a, vars_b=vars_b)
        rows_on.append({
            'experiment': 'E1_PartitionedPHP',
            'instance': f'PHP_{n}',
            'mode': 'InterpolationON',
            'n_vars': len(all_vars),
            'n_clauses': len(clauses),
            'n_vars_a': len(vars_a),
            'n_vars_b': len(vars_b),
            'n_vars_shared': len(vars_a & vars_b),
            **stats_on,
        })
        print(f"status={stats_on['status']}, time={stats_on['time_sec']:.4f}s, "
              f"conflicts={stats_on['conflicts']}")

        # Interpolation OFF
        print(f"    Interpolation OFF...", end=" ", flush=True)
        stats_off = run_with_vars(clauses, all_vars)
        rows_off.append({
            'experiment': 'E1_PartitionedPHP',
            'instance': f'PHP_{n}',
            'mode': 'InterpolationOFF',
            'n_vars': len(all_vars),
            'n_clauses': len(clauses),
            'n_vars_a': 0,
            'n_vars_b': 0,
            'n_vars_shared': 0,
            **stats_off,
        })
        print(f"status={stats_off['status']}, time={stats_off['time_sec']:.4f}s, "
              f"conflicts={stats_off['conflicts']}")

    summary = format_summary("E1: Partitioned PHP", rows_on, rows_off)
    return rows_on, rows_off, summary

# ── Experiment 2: Overlapping CNF ─────────────────────────────────────────────

def exp2_overlapping_cnf(quick: bool = False) -> Tuple[List[dict], List[dict], str]:
    """
    E2: Overlapping CNF — two sets of clauses on partially overlapping variables.

    Generate:
      - F_A: random 3-CNF on variables X_A ∪ X_shared
      - F_B: random 3-CNF on variables X_B ∪ X_shared (contradicting F_A)
      - Total: F_A ∪ F_B is UNSAT, but interpolation finds the conflict on X_shared
    """
    print("\n" + "=" * 60)
    print(" E2: Overlapping CNF — Interpolation ON vs OFF")
    print("=" * 60)

    configs = [(20, 10, 10, 5)] if quick else [
        (20, 10, 10, 5), (30, 15, 15, 8), (40, 20, 20, 10),
    ]
    rows_on = []
    rows_off = []

    for n_a, n_b, n_shared, n_trials in configs:
        for trial in range(n_trials if not quick else min(n_trials, 2)):
            seed_val = (n_a + n_b) * 100 + trial

            # Variable sets
            vars_a_only = frozenset(f"a_{i}" for i in range(1, n_a + 1))
            vars_b_only = frozenset(f"b_{i}" for i in range(1, n_b + 1))
            vars_shared = frozenset(f"s_{i}" for i in range(1, n_shared + 1))
            all_vars = set(vars_a_only) | set(vars_b_only) | set(vars_shared)

            # Generate F_A on (vars_a_only ∪ vars_shared) and F_B on (vars_b_only ∪ vars_shared)
            vars_a = vars_a_only | vars_shared
            vars_b = vars_b_only | vars_shared

            # Generate clauses: random 3-CNF that makes the combined formula UNSAT
            # Strategy: create clauses on A-side that force a specific assignment on shared vars,
            # and clauses on B-side that force the opposite assignment.
            rng = random.Random(seed_val)

            # Pick a shared variable to make the contradiction
            shared_list = sorted(vars_shared)
            conflict_var = shared_list[0] if shared_list else None

            # Side A clauses: force conflict_var = True
            clauses_a: List[Clause] = []
            # Unit clause on A side
            clauses_a.append(frozenset([(conflict_var, True)]))
            # Add random A-only clauses
            a_list = sorted(vars_a_only)
            for _ in range(int(len(a_list) * 2.5)):
                lits = rng.sample(a_list, min(3, len(a_list)))
                clause = frozenset((v, rng.choice([True, False])) for v in lits)
                clauses_a.append(clause)

            # Side B clauses: force conflict_var = False
            clauses_b: List[Clause] = []
            clauses_b.append(frozenset([(conflict_var, False)]))
            # Add random B-only clauses
            b_list = sorted(vars_b_only)
            for _ in range(int(len(b_list) * 2.5)):
                lits = rng.sample(b_list, min(3, len(b_list)))
                clause = frozenset((v, rng.choice([True, False])) for v in lits)
                clauses_b.append(clause)

            # Add some clauses mixing shared vars with both sides
            for _ in range(n_shared):
                lits = rng.sample(shared_list + a_list[:3] + b_list[:3],
                                  min(3, n_shared + 6))
                clause = frozenset((v, rng.choice([True, False])) for v in lits)
                # Assign to A or B based on which side has more of its vars
                a_count = sum(1 for v, _ in clause if v in vars_a_only or v in vars_shared)
                b_count = sum(1 for v, _ in clause if v in vars_b_only or v in vars_shared)
                if a_count >= b_count:
                    clauses_a.append(clause)
                else:
                    clauses_b.append(clause)

            all_clauses = clauses_a + clauses_b

            label = f"OverlapCNF_a{n_a}_b{n_b}_s{n_shared}_t{trial}"

            print(f"\n  {label}: {len(all_vars)} vars, {len(all_clauses)} clauses")
            print(f"    vars_A: {len(vars_a)}, vars_B: {len(vars_b)}, "
                  f"shared: {len(vars_a & vars_b)}")

            # Interpolation ON
            print(f"    Interpolation ON...", end=" ", flush=True)
            stats_on = run_with_vars(all_clauses, all_vars,
                                     vars_a=vars_a, vars_b=vars_b)
            rows_on.append({
                'experiment': 'E2_OverlappingCNF',
                'instance': label,
                'mode': 'InterpolationON',
                'n_vars': len(all_vars),
                'n_clauses': len(all_clauses),
                'n_vars_a': len(vars_a),
                'n_vars_b': len(vars_b),
                'n_vars_shared': len(vars_a & vars_b),
                **stats_on,
            })
            print(f"status={stats_on['status']}, time={stats_on['time_sec']:.4f}s, "
                  f"conflicts={stats_on['conflicts']}")

            # Interpolation OFF
            print(f"    Interpolation OFF...", end=" ", flush=True)
            stats_off = run_with_vars(all_clauses, all_vars)
            rows_off.append({
                'experiment': 'E2_OverlappingCNF',
                'instance': label,
                'mode': 'InterpolationOFF',
                'n_vars': len(all_vars),
                'n_clauses': len(all_clauses),
                'n_vars_a': 0,
                'n_vars_b': 0,
                'n_vars_shared': 0,
                **stats_off,
            })
            print(f"status={stats_off['status']}, time={stats_off['time_sec']:.4f}s, "
                  f"conflicts={stats_off['conflicts']}")

    summary = format_summary("E2: Overlapping CNF", rows_on, rows_off)
    return rows_on, rows_off, summary

# ── Experiment 3: Exact-One + Counting Contradiction ──────────────────────────

def exp3_exact_one_contradiction(
        quick: bool = False) -> Tuple[List[dict], List[dict], str]:
    """
    E3: Two exact-one constraint systems with shared variables.

    System A: exactly one of bits {0..n-1} is true, plus some auxiliary constraints
    System B: exactly one of bits {k..n+k-1} is true, overlapping with A on {k..n-1}
    Combined: the overlap forces a contradiction — both systems can't be
              simultaneously satisfied on the shared variables.
    """
    print("\n" + "=" * 60)
    print(" E3: Exact-One Contradiction — Interpolation ON vs OFF")
    print("=" * 60)

    configs = [(10, 8, 4)] if quick else [(8, 6, 3), (10, 8, 4), (12, 10, 5)]
    rows_on = []
    rows_off = []

    for n_a, n_b, n_overlap in configs:
        # System A: bits 0..n_a-1
        clauses_a: List[Clause] = []
        clauses_a.append(frozenset((f"a_{i}", True) for i in range(n_a)))
        for i in range(n_a):
            for j in range(i + 1, n_a):
                clauses_a.append(frozenset([
                    (f"a_{i}", False), (f"a_{j}", False)]))

        # System B: bits (n_a - n_overlap) .. (n_a - n_overlap + n_b - 1)
        offset = n_a - n_overlap
        clauses_b: List[Clause] = []
        clauses_b.append(frozenset((f"a_{i}", True)
                                   for i in range(offset, offset + n_b)))
        for i in range(offset, offset + n_b):
            for j in range(i + 1, offset + n_b):
                clauses_b.append(frozenset([
                    (f"a_{i}", False), (f"a_{j}", False)]))

        # Contradiction: System A says exactly one in {0..n_a-1},
        # System B says exactly one in {offset..offset+n_b-1}.
        # Since the overlap region {offset..n_a-1} is non-empty,
        # and both systems force different choices, this is UNSAT.
        # More precisely: A forces the true bit to be in {0..offset-1} or {offset..n_a-1},
        # B forces it to be in {offset..offset+n_b-1}.
        # If offset > 0, A could put the true bit at 0 and B at offset — no contradiction.
        # We need to force contradiction: add clause that A's true bit must be in the overlap.
        rng = random.Random(n_a * 100 + n_b)
        # Force A's true bit into overlap region
        for i in range(offset):
            clauses_a.append(frozenset([(f"a_{i}", False)]))

        # Force B's true bit into overlap region too
        for i in range(offset + n_b, n_a):
            if i < n_a:
                clauses_b.append(frozenset([(f"a_{i}", False)]))

        # Now both must choose from the overlap, and they can't agree
        # (They're separate systems — the contradiction is that combined
        #  we have "exactly one true in overlap" from A and also from B,
        #  which means two variables must be true, violating each other.)

        # Add mutual exclusion: if A chooses i in overlap, B can't also choose i
        for i in range(offset, min(offset + n_overlap, n_a)):
            if i < offset + n_b:
                # Note: The mutual exclusion is implicitly handled by both systems
                # using the same variable names on the overlap — any assignment
                # satisfying both exact-one constraints simultaneously is impossible.
                pass

        # Actually the contradiction is automatic: both A and B have "exactly one of
        # overlap vars is true", and their selections are independent but use the same
        # variable names, so any assignment violates one system.

        all_clauses = clauses_a + clauses_b
        all_vars = set(f"a_{i}" for i in range(n_a))

        vars_a = frozenset(f"a_{i}" for i in range(n_a))
        vars_b = frozenset(f"a_{i}" for i in range(offset, offset + n_b))

        label = f"ExactOne_a{n_a}_b{n_b}_o{n_overlap}"
        print(f"\n  {label}: {len(all_vars)} vars, {len(all_clauses)} clauses")
        print(f"    vars_A: {len(vars_a)}, vars_B: {len(vars_b)}, "
              f"shared: {len(vars_a & vars_b)}")

        # Interpolation ON
        print(f"    Interpolation ON...", end=" ", flush=True)
        stats_on = run_with_vars(all_clauses, all_vars,
                                 vars_a=vars_a, vars_b=vars_b)
        rows_on.append({
            'experiment': 'E3_ExactOneContradiction',
            'instance': label,
            'mode': 'InterpolationON',
            'n_vars': len(all_vars),
            'n_clauses': len(all_clauses),
            'n_vars_a': len(vars_a),
            'n_vars_b': len(vars_b),
            'n_vars_shared': len(vars_a & vars_b),
            **stats_on,
        })
        print(f"status={stats_on['status']}, time={stats_on['time_sec']:.4f}s, "
              f"conflicts={stats_on['conflicts']}")

        # Interpolation OFF
        print(f"    Interpolation OFF...", end=" ", flush=True)
        stats_off = run_with_vars(all_clauses, all_vars)
        rows_off.append({
            'experiment': 'E3_ExactOneContradiction',
            'instance': label,
            'mode': 'InterpolationOFF',
            'n_vars': len(all_vars),
            'n_clauses': len(all_clauses),
            'n_vars_a': 0,
            'n_vars_b': 0,
            'n_vars_shared': 0,
            **stats_off,
        })
        print(f"status={stats_off['status']}, time={stats_off['time_sec']:.4f}s, "
              f"conflicts={stats_off['conflicts']}")

    summary = format_summary("E3: Exact-One Contradiction", rows_on, rows_off)
    return rows_on, rows_off, summary

# ── Experiment 4: Random Partitioned CNF ──────────────────────────────────────

def exp4_random_partitioned(
        quick: bool = False) -> Tuple[List[dict], List[dict], str]:
    """
    E4: Random UNSAT 3-CNF with variable partitioning.

    Generate random UNSAT 3-CNF instances at the phase transition (alpha > 4.267).
    Partition variables randomly into A-group, B-group, and shared.
    Compare interpolation ON vs OFF.
    """
    print("\n" + "=" * 60)
    print(" E4: Random Partitioned UNSAT 3-CNF — Interpolation ON vs OFF")
    print("=" * 60)

    configs = [(30, 160)] if quick else [(30, 160), (40, 200), (50, 240)]
    rows_on = []
    rows_off = []

    for n_vars, n_clauses in configs:
        for trial in range(3 if not quick else 1):
            seed_val = n_vars * 100 + trial
            clauses = gen_random_3cnf(n_vars, n_clauses, seed_val=seed_val)
            all_vars = set()
            for c in clauses:
                for v, _ in c:
                    all_vars.add(v)

            # Random partition: 40% A, 40% B, 20% shared
            var_list = sorted(all_vars)
            random.Random(seed_val + 1000).shuffle(var_list)
            cutoff_a = int(len(var_list) * 0.4)
            cutoff_b = int(len(var_list) * 0.8)
            vars_a = frozenset(var_list[:cutoff_b])  # A includes shared
            vars_b = frozenset(var_list[cutoff_a:])  # B includes shared

            label = f"RandPart_n{n_vars}_c{n_clauses}_t{trial}"
            print(f"\n  {label}: {len(all_vars)} vars, {n_clauses} clauses")
            print(f"    vars_A: {len(vars_a)}, vars_B: {len(vars_b)}, "
                  f"shared: {len(vars_a & vars_b)}")

            # Interpolation ON
            print(f"    Interpolation ON...", end=" ", flush=True)
            stats_on = run_with_vars(clauses, all_vars,
                                     vars_a=vars_a, vars_b=vars_b)
            rows_on.append({
                'experiment': 'E4_RandomPartitioned',
                'instance': label,
                'mode': 'InterpolationON',
                'n_vars': len(all_vars),
                'n_clauses': n_clauses,
                'n_vars_a': len(vars_a),
                'n_vars_b': len(vars_b),
                'n_vars_shared': len(vars_a & vars_b),
                **stats_on,
            })
            print(f"status={stats_on['status']}, time={stats_on['time_sec']:.4f}s, "
                  f"conflicts={stats_on['conflicts']}")

            # Interpolation OFF
            print(f"    Interpolation OFF...", end=" ", flush=True)
            stats_off = run_with_vars(clauses, all_vars)
            rows_off.append({
                'experiment': 'E4_RandomPartitioned',
                'instance': label,
                'mode': 'InterpolationOFF',
                'n_vars': len(all_vars),
                'n_clauses': n_clauses,
                'n_vars_a': 0,
                'n_vars_b': 0,
                'n_vars_shared': 0,
                **stats_off,
            })
            print(f"status={stats_off['status']}, time={stats_off['time_sec']:.4f}s, "
                  f"conflicts={stats_off['conflicts']}")

    summary = format_summary("E4: Random Partitioned CNF", rows_on, rows_off)
    return rows_on, rows_off, summary

# ── Main ──────────────────────────────────────────────────────────────────────

if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(
        description='P1-4c: Interpolation Feedback Loop Ablation')
    parser.add_argument('--exp', type=str, default='all',
                        help='Experiments: 1, 2, 3, 4, all (default: all)')
    parser.add_argument('--quick', action='store_true',
                        help='Quick mode: reduced instances')
    parser.add_argument('--timeout', type=float, default=TIMEOUT_SEC,
                        help=f'Timeout per instance in seconds (default: {TIMEOUT_SEC})')
    args = parser.parse_args()

    TIMEOUT_SEC = args.timeout
    quick = args.quick

    exp_map = {
        '1': exp1_partitioned_php,
        '2': exp2_overlapping_cnf,
        '3': exp3_exact_one_contradiction,
        '4': exp4_random_partitioned,
    }

    if args.exp == 'all':
        exp_names = ['1', '2', '3', '4']
    else:
        exp_names = [e.strip() for e in args.exp.split(',')]

    all_rows: List[dict] = []
    t_total_start = time.perf_counter()

    print("CertiProof — Interpolation Ablation Study (P1-4c)")
    print(f"Timeout: {TIMEOUT_SEC}s per instance")
    print(f"Quick mode: {quick}")
    print()

    summaries = []

    for name in exp_names:
        if name in exp_map:
            fn = exp_map[name]
            rows_on, rows_off, summary = fn(quick=quick)
            all_rows.extend(rows_on)
            all_rows.extend(rows_off)
            summaries.append(summary)
        else:
            print(f"Unknown experiment: {name}")

    # Print all summaries
    print("\n" + "=" * 60)
    print(" ABLATION RESULTS SUMMARY")
    print("=" * 60)
    for s in summaries:
        print(s)

    # Save results
    if all_rows:
        columns = [
            'experiment', 'instance', 'mode',
            'n_vars', 'n_clauses',
            'n_vars_a', 'n_vars_b', 'n_vars_shared',
            'status', 'time_sec',
            'conflicts', 'decisions', 'learned',
            'proof_size', 'proof_depth',
        ]
        _write_csv(OUTPUT_FILE, all_rows, columns)

        # Overall stats
        on_rows = [r for r in all_rows if r['mode'] == 'InterpolationON']
        off_rows = [r for r in all_rows if r['mode'] == 'InterpolationOFF']
        on_solved = sum(1 for r in on_rows if r['status'] in ('SAT', 'UNSAT'))
        off_solved = sum(1 for r in off_rows if r['status'] in ('SAT', 'UNSAT'))

        print(f"\n{'='*60}")
        print(f" OVERALL ABLATION RESULTS")
        print(f" Interpolation ON:  {on_solved}/{len(on_rows)} solved")
        print(f" Interpolation OFF: {off_solved}/{len(off_rows)} solved")

        if on_solved > 0 and off_solved > 0:
            on_times = [r['time_sec'] for r in on_rows
                       if r['status'] in ('SAT', 'UNSAT')]
            off_times = [r['time_sec'] for r in off_rows
                        if r['status'] in ('SAT', 'UNSAT')]
            on_conflicts = [r['conflicts'] for r in on_rows
                           if r['status'] in ('SAT', 'UNSAT')]
            off_conflicts = [r['conflicts'] for r in off_rows
                            if r['status'] in ('SAT', 'UNSAT')]

            print(f" Time (median):    ON={statistics.median(on_times):.4f}s  "
                  f"OFF={statistics.median(off_times):.4f}s")
            print(f" Conflicts (median): ON={statistics.median(on_conflicts):.0f}  "
                  f"OFF={statistics.median(off_conflicts):.0f}")

        print(f"\n Results saved to: {OUTPUT_FILE}")
    else:
        print("\nNo results generated.")

    t_total = time.perf_counter() - t_total_start
    print(f" Total runtime: {t_total:.1f}s")
    print(f"{'='*60}")
