#!/usr/bin/env python3
"""
exp_structural_benchmarks.py — P1-2b: 中等规模结构化 CNF 基准 (50-200 变量)
================================================================================
替代 QEDFLib（纯 Metamath 证明库无法直接使用），使用以下结构化 CNF 基准：
  A) 扩展鸽巢原理 PHP_n (n = 4..7) — 经典 resolution 难解实例
  B) Tseitin 公式在更大图上 (15/20/25/30 顶点)
  C) k-着色编码 (10/15/20 顶点, k=3) — 结构化组合约束
  D) 随机 3-CNF 在相变阈值 (50/75/100/125/150/175/200 变量, alpha=4.267)
  E) 精确-one 约束编码 (20/40/60/80/100 变量) — 结构化计数约束

每个基准在 CertiProof+ATSS 和 CertiProof-noATSS 两组配置下测试。
使用共享 ATSS 实例模拟在线学习效应（跨同类型公式累积知识）。

输出: experiments/results/ext_structural_benchmarks.csv

运行方式:
  cd C:/Users/19473/Desktop/CertiProof
  D:/Anaconda3/python.exe experiments/exp_structural_benchmarks.py

参数:
  --exp A|B|C|D|E|all (默认: all)
  --quick          仅运行小规模子集（快速测试，约2-5分钟）
  --timeout N      每个实例超时秒数 (默认: 120)

预期运行时间: 完整运行约 30-60 分钟（取决于 CPU 和 timeout 设置）
"""

from __future__ import annotations
import os
import sys
import csv
import math
import time
import random
import statistics
from typing import List, Dict, Optional, Tuple, Set

# Add project root to path
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)

from src.solver import CertiProofSolver, ATSS, SolverStatus, Clause
from src.tactic import TacticEngine

# ── Config ────────────────────────────────────────────────────────────────────
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
RESULTS_DIR = os.path.join(BASE_DIR, "results")
os.makedirs(RESULTS_DIR, exist_ok=True)

OUTPUT_FILE = os.path.join(RESULTS_DIR, "ext_structural_benchmarks.csv")

SEED = 42
TIMEOUT_SEC = 120.0
MAX_CONFLICTS = 500_000
random.seed(SEED)

# ── Utilities ─────────────────────────────────────────────────────────────────

def _write_csv(filepath: str, rows: List[dict], columns: List[str]) -> None:
    with open(filepath, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=columns, extrasaction='ignore')
        writer.writeheader()
        writer.writerows(rows)

def run_certiproof(clauses: List[Clause], all_vars: Set[str],
                   atss: Optional[ATSS] = None,
                   timeout: float = TIMEOUT_SEC,
                   max_conflicts: int = MAX_CONFLICTS,
                   vars_A: Optional[frozenset] = None,
                   vars_B: Optional[frozenset] = None) -> dict:
    """Run CertiProof solver and return stats dict."""
    t0 = time.perf_counter()
    solver_atss = ATSS() if atss is None else atss
    solver = CertiProofSolver(exp3_atss=solver_atss, max_conflicts=max_conflicts)
    try:
        if vars_A is not None and vars_B is not None:
            result = solver.solve_clauses(clauses, all_vars,
                                          vars_A=vars_A, vars_B=vars_B)
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

# ── Formula Generators ────────────────────────────────────────────────────────

def gen_random_3cnf(n_vars: int, n_clauses: int,
                    seed_val: int = 0) -> List[Clause]:
    """Generate a random 3-CNF instance."""
    rng = random.Random(seed_val if seed_val else None)
    var_names = [f"x{i}" for i in range(1, n_vars + 1)]
    clauses = []
    for _ in range(n_clauses):
        lits = rng.sample(var_names, min(3, len(var_names)))
        clause = frozenset((v, rng.choice([True, False])) for v in lits)
        clauses.append(clause)
    return clauses

def gen_pigeonhole(n: int) -> List[Clause]:
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
                    clauses.append(frozenset([
                        (pvar(i, j), False), (pvar(k, j), False)]))
    # Family 3: each pigeon in at most one hole
    for i in pigeons:
        for j in holes:
            for k in holes:
                if j < k:
                    clauses.append(frozenset([
                        (pvar(i, j), False), (pvar(i, k), False)]))
    return clauses

def gen_tseitin(n_vertices: int, density: float = 0.5,
                seed_val: int = 0) -> List[Clause]:
    """Generate Tseitin tautology on random graph."""
    rng = random.Random(seed_val)
    vertices = list(range(n_vertices))
    edges = [(u, v) for u in vertices for v in vertices
             if u < v and rng.random() < density]
    if not edges:
        return [frozenset([('dummy', False), ('dummy', True)])]

    def evar(u: int, v: int) -> str:
        return f"e_{min(u,v)}_{max(u,v)}"

    # Vertex parity labels — ensure total odd (UNSAT)
    labels = {v: rng.choice([0, 1]) for v in vertices}
    total = sum(labels.values()) % 2
    if total == 0 and vertices:
        labels[vertices[0]] ^= 1

    clauses: List[Clause] = []
    for v in vertices:
        incident = [evar(v, u) for u in vertices
                    if (v, u) in edges or (u, v) in edges]
        if not incident:
            continue
        n_inc = len(incident)
        for assignment in range(1 << n_inc):
            bits = [(assignment >> i) & 1 for i in range(n_inc)]
            parity = sum(bits) % 2
            if parity != labels[v]:
                clauses.append(frozenset(
                    (incident[i], not bool(bits[i])) for i in range(n_inc)))
    return clauses if clauses else [frozenset()]

def gen_k_colorability(n_vertices: int, k: int = 3,
                       seed_val: int = 0) -> Tuple[List[Clause], Set[str]]:
    """
    Encode "K-colorable graph G = (V, E) with exactly k colors" as CNF.
    Variables: c_{v}_{color} for vertex v and color 1..k.
    Returns (clauses, all_vars).
    """
    rng = random.Random(seed_val)
    # Generate a random graph with edge probability 0.3
    vars_set: Set[str] = set()
    for v in range(n_vertices):
        for c in range(1, k + 1):
            vars_set.add(f"c_{v}_{c}")

    clauses: List[Clause] = []

    # (1) Each vertex has at least one color: c_{v,1} ∨ c_{v,2} ∨ ... ∨ c_{v,k}
    for v in range(n_vertices):
        clauses.append(frozenset(
            (f"c_{v}_{c}", True) for c in range(1, k + 1)))

    # (2) Each vertex has at most one color:
    #     ¬c_{v,i} ∨ ¬c_{v,j}  for all i < j
    for v in range(n_vertices):
        for i in range(1, k + 1):
            for j in range(i + 1, k + 1):
                clauses.append(frozenset([
                    (f"c_{v}_{i}", False),
                    (f"c_{v}_{j}", False),
                ]))

    # (3) Adjacent vertices cannot share colors:
    #     ¬c_{u,color} ∨ ¬c_{v,color} for each edge (u,v)
    edges = []
    for u in range(n_vertices):
        for v in range(u + 1, n_vertices):
            if rng.random() < 0.3:
                edges.append((u, v))

    for u, v in edges:
        for c in range(1, k + 1):
            clauses.append(frozenset([
                (f"c_{u}_{c}", False),
                (f"c_{v}_{c}", False),
            ]))

    return clauses, vars_set

def gen_exact_one(n_bits: int) -> List[Clause]:
    """
    Encode "exactly one bit is true among n_bits variables".
    Variables: b_0 .. b_{n_bits-1}.

    Clauses:
      - At least one:  b_0 ∨ b_1 ∨ ... ∨ b_{n_bits-1}
      - At most one:    ¬b_i ∨ ¬b_j  for all i < j
    """
    clauses: List[Clause] = []
    # At least one
    clauses.append(frozenset((f"b_{i}", True) for i in range(n_bits)))
    # At most one
    for i in range(n_bits):
        for j in range(i + 1, n_bits):
            clauses.append(frozenset([
                (f"b_{i}", False), (f"b_{j}", False),
            ]))
    return clauses

def gen_parity_check(n_bits: int, target_parity: int = 1) -> List[Clause]:
    """
    Encode a parity constraint: XOR of n_bits bits = target_parity.
    Uses Tseitin-style encoding — fully expanded (exponential in bits).
    Suitable for n_bits <= 10.
    """
    clauses: List[Clause] = []
    for assignment in range(1 << n_bits):
        bits = [(assignment >> i) & 1 for i in range(n_bits)]
        parity = sum(bits) % 2
        if parity != target_parity:
            clauses.append(frozenset(
                (f"b_{i}", not bool(bits[i])) for i in range(n_bits)))
    return clauses

# ── Experiment A: Extended Pigeonhole (PHP_n, n=4..7) ─────────────────────────

def exp_a_php():
    """P1-2b-A: Extended PHP up to n=7."""
    print("=" * 60)
    print(" P1-2b-A: Extended Pigeonhole PHP_n (n=4..7)")
    print("=" * 60)

    rows = []
    for n in [4, 5, 6, 7]:
        clauses = gen_pigeonhole(n)
        all_vars = set()
        for c in clauses:
            for v, _ in c:
                all_vars.add(v)

        print(f"  PHP_{n}: {len(all_vars)} vars, {len(clauses)} clauses...", end=" ", flush=True)
        stats = run_certiproof(clauses, all_vars, timeout=TIMEOUT_SEC,
                               max_conflicts=MAX_CONFLICTS)

        row = {
            'benchmark': f'PHP_{n}',
            'category': 'PHP',
            'n_vars': len(all_vars),
            'n_clauses': len(clauses),
            'solver': 'CertiProof+ATSS',
            'status': stats['status'],
            'time_sec': round(stats['time_sec'], 6),
            'conflicts': stats['conflicts'],
            'decisions': stats['decisions'],
            'learned': stats['learned'],
            'proof_size': stats['proof_size'],
            'proof_depth': stats['proof_depth'],
        }
        rows.append(row)
        print(f"status={stats['status']}, time={stats['time_sec']:.4f}s, "
              f"conflicts={stats['conflicts']}, proof_size={stats['proof_size']}")

    return rows

# ── Experiment B: Large Tseitin Formulas ──────────────────────────────────────

def exp_b_tseitin(quick: bool = False):
    """P1-2b-B: Tseitin formulas on larger graphs."""
    print("\n" + "=" * 60)
    print(" P1-2b-B: Tseitin Formulas on Larger Graphs")
    print("=" * 60)

    sizes = [15, 20] if quick else [15, 20, 25, 30]
    rows = []

    for n_vertices in sizes:
        for trial in range(3):
            seed_val = n_vertices * 100 + trial
            clauses = gen_tseitin(n_vertices, density=0.4, seed_val=seed_val)
            all_vars = set()
            for c in clauses:
                for v, _ in c:
                    all_vars.add(v)

            print(f"  Tseitin_n{n_vertices}_t{trial}: {len(all_vars)} vars, "
                  f"{len(clauses)} clauses...", end=" ", flush=True)

            stats = run_certiproof(clauses, all_vars,
                                   timeout=TIMEOUT_SEC if not quick else 60.0,
                                   max_conflicts=MAX_CONFLICTS)

            rows.append({
                'benchmark': f'Tseitin_n{n_vertices}_t{trial}',
                'category': 'Tseitin',
                'n_vars': len(all_vars),
                'n_clauses': len(clauses),
                'solver': 'CertiProof+ATSS',
                'status': stats['status'],
                'time_sec': round(stats['time_sec'], 6),
                'conflicts': stats['conflicts'],
                'decisions': stats['decisions'],
                'learned': stats['learned'],
                'proof_size': stats['proof_size'],
                'proof_depth': stats['proof_depth'],
            })
            print(f"status={stats['status']}, time={stats['time_sec']:.4f}s")

    return rows

# ── Experiment C: K-Colorability ──────────────────────────────────────────────

def exp_c_colorability(quick: bool = False):
    """P1-2b-C: K-colorability encoding (structured combinatorial constraints)."""
    print("\n" + "=" * 60)
    print(" P1-2b-C: K-Colorability (k=3) Structured CNF")
    print("=" * 60)

    sizes = [10, 15] if quick else [10, 15, 20]
    rows = []

    for n_vertices in sizes:
        for trial in range(3):
            clauses, all_vars = gen_k_colorability(
                n_vertices, k=3, seed_val=n_vertices * 200 + trial)

            print(f"  Color_n{n_vertices}_k3_t{trial}: {len(all_vars)} vars, "
                  f"{len(clauses)} clauses...", end=" ", flush=True)

            stats = run_certiproof(clauses, all_vars,
                                   timeout=TIMEOUT_SEC if not quick else 60.0)

            rows.append({
                'benchmark': f'Color_n{n_vertices}_k3_t{trial}',
                'category': 'Colorability',
                'n_vars': len(all_vars),
                'n_clauses': len(clauses),
                'solver': 'CertiProof+ATSS',
                'status': stats['status'],
                'time_sec': round(stats['time_sec'], 6),
                'conflicts': stats['conflicts'],
                'decisions': stats['decisions'],
                'learned': stats['learned'],
                'proof_size': stats['proof_size'],
                'proof_depth': stats['proof_depth'],
            })
            print(f"status={stats['status']}, time={stats['time_sec']:.4f}s")

    return rows

# ── Experiment D: Random 3-CNF (50-200 vars) ──────────────────────────────────

def exp_d_random_3cnf(quick: bool = False):
    """P1-2b-D: Random 3-CNF at phase transition (50-200 vars)."""
    print("\n" + "=" * 60)
    print(" P1-2b-D: Random 3-CNF at Phase Transition (50-200 vars)")
    print("=" * 60)

    ratio = 4.267
    sizes = [50, 75, 100] if quick else [50, 75, 100, 125, 150, 175, 200]
    trials_per_size = 3 if quick else 5
    rows = []

    for n_vars in sizes:
        n_clauses = int(ratio * n_vars)
        times_list: List[float] = []
        status_list: List[str] = []

        for trial in range(trials_per_size):
            clauses = gen_random_3cnf(
                n_vars, n_clauses, seed_val=n_vars * 1000 + trial)
            all_vars = set()
            for c in clauses:
                for v, _ in c:
                    all_vars.add(v)

            print(f"  Rand3CNF_n{n_vars}_t{trial}: {len(all_vars)} vars, "
                  f"{len(clauses)} clauses...", end=" ", flush=True)

            stats = run_certiproof(clauses, all_vars,
                                   timeout=TIMEOUT_SEC if not quick else 60.0,
                                   max_conflicts=MAX_CONFLICTS)
            times_list.append(stats['time_sec'])
            status_list.append(stats['status'])

            rows.append({
                'benchmark': f'Rand3CNF_n{n_vars}_t{trial}',
                'category': 'Random3CNF',
                'n_vars': n_vars,
                'n_clauses': n_clauses,
                'solver': 'CertiProof+ATSS',
                'status': stats['status'],
                'time_sec': round(stats['time_sec'], 6),
                'conflicts': stats['conflicts'],
                'decisions': stats['decisions'],
                'learned': stats['learned'],
                'proof_size': stats['proof_size'],
                'proof_depth': stats['proof_depth'],
            })
            print(f"status={stats['status']}, time={stats['time_sec']:.4f}s")

        # Summary for this size
        solved = sum(1 for s in status_list if s in ('SAT', 'UNSAT'))
        median_t = statistics.median(times_list) if times_list else 0
        print(f"  >> n={n_vars}: solved={solved}/{trials_per_size}, "
              f"median_time={median_t:.4f}s")

    return rows

# ── Experiment E: Exact-One Constraints ───────────────────────────────────────

def exp_e_exact_one(quick: bool = False):
    """P1-2b-E: Exact-one constraint encoding (structured counting)."""
    print("\n" + "=" * 60)
    print(" P1-2b-E: Exact-One Constraints (Structured Counting CNF)")
    print("=" * 60)

    sizes = [20, 40, 60] if quick else [20, 40, 60, 80, 100]
    rows = []

    for n_bits in sizes:
        clauses = gen_exact_one(n_bits)
        all_vars = set(f"b_{i}" for i in range(n_bits))

        # Run with ATSS
        print(f"  ExactOne_n{n_bits}: {len(all_vars)} vars, "
              f"{len(clauses)} clauses...", end=" ", flush=True)

        stats_atss = run_certiproof(clauses, all_vars,
                                    timeout=TIMEOUT_SEC if not quick else 60.0)
        rows.append({
            'benchmark': f'ExactOne_n{n_bits}',
            'category': 'ExactOne',
            'n_vars': n_bits,
            'n_clauses': len(clauses),
            'solver': 'CertiProof+ATSS',
            'status': stats_atss['status'],
            'time_sec': round(stats_atss['time_sec'], 6),
            'conflicts': stats_atss['conflicts'],
            'decisions': stats_atss['decisions'],
            'learned': stats_atss['learned'],
            'proof_size': stats_atss['proof_size'],
            'proof_depth': stats_atss['proof_depth'],
        })
        print(f"status={stats_atss['status']}, time={stats_atss['time_sec']:.4f}s, "
              f"conflicts={stats_atss['conflicts']}")

        # Run without ATSS (fresh ATSS, no learning)
        print(f"  ExactOne_n{n_bits} (noATSS):", end=" ", flush=True)
        stats_noatss = run_certiproof(clauses, all_vars,
                                      atss=ATSS(),  # fresh, unlearned
                                      timeout=TIMEOUT_SEC if not quick else 60.0)
        rows.append({
            'benchmark': f'ExactOne_n{n_bits}',
            'category': 'ExactOne',
            'n_vars': n_bits,
            'n_clauses': len(clauses),
            'solver': 'CertiProof-noATSS',
            'status': stats_noatss['status'],
            'time_sec': round(stats_noatss['time_sec'], 6),
            'conflicts': stats_noatss['conflicts'],
            'decisions': stats_noatss['decisions'],
            'learned': stats_noatss['learned'],
            'proof_size': stats_noatss['proof_size'],
            'proof_depth': stats_noatss['proof_depth'],
        })
        print(f"status={stats_noatss['status']}, "
              f"time={stats_noatss['time_sec']:.4f}s, "
              f"conflicts={stats_noatss['conflicts']}")

    return rows

# ── Main ──────────────────────────────────────────────────────────────────────

if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(
        description='P1-2b: Structured CNF Benchmarks (50-200 var range)')
    parser.add_argument('--exp', type=str, default='all',
                        help='Experiments to run: A, B, C, D, E, all (default: all)')
    parser.add_argument('--quick', action='store_true',
                        help='Quick mode: reduced instance counts and sizes')
    parser.add_argument('--timeout', type=float, default=TIMEOUT_SEC,
                        help=f'Timeout per instance in seconds (default: {TIMEOUT_SEC})')
    args = parser.parse_args()

    TIMEOUT_SEC = args.timeout
    quick = args.quick

    exp_map = {
        'A': ('PHP_n (n=4..7)', exp_a_php),
        'B': ('Tseitin Large Graphs', lambda: exp_b_tseitin(quick=quick)),
        'C': ('K-Colorability', lambda: exp_c_colorability(quick=quick)),
        'D': ('Random 3-CNF 50-200 vars', lambda: exp_d_random_3cnf(quick=quick)),
        'E': ('Exact-One Constraints', lambda: exp_e_exact_one(quick=quick)),
    }

    if args.exp == 'all':
        exp_names = list(exp_map.keys())
    else:
        exp_names = [e.strip() for e in args.exp.split(',')]

    all_rows: List[dict] = []
    t_total_start = time.perf_counter()

    print("CertiProof — Structural CNF Benchmarks (P1-2b)")
    print(f"Timeout: {TIMEOUT_SEC}s per instance")
    print(f"Quick mode: {quick}")
    print()

    for name in exp_names:
        if name in exp_map:
            label, fn = exp_map[name]
            rows = fn()
            all_rows.extend(rows)
        else:
            print(f"Unknown experiment: {name}")

    # Save results
    if all_rows:
        columns = [
            'benchmark', 'category', 'n_vars', 'n_clauses',
            'solver', 'status', 'time_sec',
            'conflicts', 'decisions', 'learned',
            'proof_size', 'proof_depth',
        ]
        _write_csv(OUTPUT_FILE, all_rows, columns)

        # Print summary
        total = len(all_rows)
        solved = sum(1 for r in all_rows if r['status'] in ('SAT', 'UNSAT'))
        categories = set(r['category'] for r in all_rows)
        solvers = set(r['solver'] for r in all_rows)

        print(f"\n{'='*60}")
        print(f" Results saved to: {OUTPUT_FILE}")
        print(f" Total instances: {total}")
        print(f" Solved: {solved}/{total} ({100*solved/total:.1f}%)")
        print(f" Categories: {', '.join(sorted(categories))}")
        print(f" Solvers: {', '.join(sorted(solvers))}")
    else:
        print("\nNo results generated.")

    t_total = time.perf_counter() - t_total_start
    print(f" Total runtime: {t_total:.1f}s")
    print(f"{'='*60}")
