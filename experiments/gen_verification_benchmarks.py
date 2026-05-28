#!/usr/bin/env python3
"""
gen_verification_benchmarks.py — Verification-Relevant Benchmark Generator
===========================================================================
Generates verification-relevant propositional benchmarks for CertiProof.
Uses CDCL decide() for timing + ATSS prove() for tactic learning.
Formulas avoid <-> (iff) to prevent ND proof search blowup.

Tests ATSS online learning: a SINGLE ATSS instance processes ALL
benchmarks sequentially (accumulating tactic preferences), then
results are compared against fresh-ATSS per benchmark (no accumulation).

Benchmark categories:
  1. Chain/transitivity reasoning
  2. Contrapositive reasoning
  3. Resolution patterns
  4. Circuit-like formulas (implication only)
  5. Classical tautologies
  6. Structural formulas

Output: experiments/results/exp_verification_benchmarks.csv

Usage:
    python gen_verification_benchmarks.py
"""

from __future__ import annotations
import os
import sys
import csv
import time
import random
import statistics
import threading
from typing import List, Optional

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from src.tactic import TacticEngine
from src.formula import parse, Formula

# ── Config ────────────────────────────────────────────────────────────────────
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
RESULTS_DIR = os.path.join(BASE_DIR, "results")
os.makedirs(RESULTS_DIR, exist_ok=True)

N_REPETITIONS = 1
MAX_DEPTH = 50
PER_BENCH_TIMEOUT = 10.0  # seconds
SEED = 42

random.seed(SEED)


# ── Benchmark Definitions (no <->, all one-directional) ────────────────────────

VERIFICATION_BENCHMARKS = [
    # Chain Reasoning
    ("Chain_3", "Chain_Reasoning",
     "((a -> b) & (b -> c)) -> (a -> c)"),
    ("Chain_4", "Chain_Reasoning",
     "((a -> b) & (b -> c) & (c -> d)) -> (a -> d)"),
    ("Chain_5", "Chain_Reasoning",
     "((a -> b) & (b -> c) & (c -> d) & (d -> e)) -> (a -> e)"),

    # Contrapositive Reasoning
    ("Contrapositive_1", "Contrapositive",
     "(a -> b) -> (~b -> ~a)"),
    ("Contrapositive_2", "Contrapositive",
     "(~b -> ~a) -> (a -> b)"),
    ("Contrapositive_Chain", "Contrapositive",
     "((a -> b) & (~b -> ~a)) -> ((b -> c) -> (~c -> ~b))"),

    # Resolution Patterns
    ("Resolve_Simple", "Resolution",
     "((a | b) & (~a | c)) -> (b | c)"),
    ("Resolve_Unit", "Resolution",
     "((a | b) & ~a) -> b"),

    # Classical Tautologies
    ("Peirce", "Classical",
     "((a -> b) -> a) -> a"),
    ("Frege_1", "Classical",
     "a -> (b -> a)"),
    ("Frege_2", "Classical",
     "(a -> (b -> c)) -> ((a -> b) -> (a -> c))"),
    ("Dilemma", "Classical",
     "((a -> c) & (b -> c)) -> ((a | b) -> c)"),

    # Structural / BitVector-like
    ("Distrib_Fwd", "Structural",
     "(a & (b | c)) -> ((a & b) | (a & c))"),
    ("Exportation", "Structural",
     "((a & b) -> c) -> (a -> (b -> c))"),
    ("Importation", "Structural",
     "(a -> (b -> c)) -> ((a & b) -> c)"),
]


def _prove_with_timeout(engine: TacticEngine, f: Formula,
                        timeout: float) -> tuple:
    """Attempt prove() with timeout. Returns (elapsed, proof, error)."""
    result = {'elapsed': 0.0, 'proof': None, 'error': None}

    def target():
        t0 = time.perf_counter()
        try:
            result['proof'] = engine.prove(f)
            result['elapsed'] = time.perf_counter() - t0
        except Exception as e:
            result['elapsed'] = time.perf_counter() - t0
            result['error'] = str(e)

    t = threading.Thread(target=target, daemon=True)
    t.start()
    t.join(timeout)

    if t.is_alive():
        return timeout, None, 'TIMEOUT'
    return result['elapsed'], result['proof'], result['error']


def _run_one(fstr: str, engine: TacticEngine,
             n_reps: int = N_REPETITIONS) -> dict:
    """Run one formula through an engine."""
    f = parse(fstr)
    times = []
    proved = 0
    sizes = []
    depths = []

    for _ in range(n_reps):
        elapsed, proof, error = _prove_with_timeout(engine, f, PER_BENCH_TIMEOUT)
        if proof is not None:
            times.append(elapsed)
            proved += 1
            sizes.append(proof.size)
            depths.append(proof.depth)
        elif error == 'TIMEOUT':
            times.append(PER_BENCH_TIMEOUT)

    valid_t = [t for t in times if t > 0]
    return {
        'time_mean_ms': round(statistics.mean(valid_t) * 1000, 3) if valid_t else 0,
        'time_std_ms': round(statistics.stdev(valid_t) * 1000, 3)
        if len(valid_t) > 1 else 0,
        'proof_size': round(statistics.mean(sizes), 1) if sizes else 0,
        'proof_depth': round(statistics.mean(depths), 1) if depths else 0,
        'status': 'PROVED' if proved > 0 else 'TIMEOUT',
        'solve_rate': proved / n_reps,
    }


def _run_cdcl(fstr: str) -> dict:
    """Run CDCL decide() for baseline timing (instant for these formulas)."""
    from src.tactic import decide
    from src.solver import CertiProofSolver
    f = parse(fstr)
    t0 = time.perf_counter()
    result = decide(f)
    elapsed = time.perf_counter() - t0
    n_v = len(f.variables())
    return {
        'benchmark': fstr[:30], 'category': 'CDCL_baseline',
        'n_vars': n_v,
        'solver': 'CDCL (decide)',
        'time_ms': round(elapsed * 1000, 3),
        'time_std_ms': 0,
        'proof_size': 0,
        'proof_depth': 0,
        'status': f'VALID' if result.name == 'SAT' else 'INVALID',
        'solve_rate': 1.0,
    }


def main():
    print("=" * 70)
    print("Verification-Relevant Benchmark Suite (P2-1)")
    print("=" * 70)
    print(f"Benchmarks: {len(VERIFICATION_BENCHMARKS)}")
    print(f"Timeout per benchmark: {PER_BENCH_TIMEOUT}s")
    print()

    # ── Phase 1: ATSS with accumulated learning ────────────────────────────────
    print("[Phase 1] ATSS with accumulated learning across all benchmarks")
    print("-" * 50)
    engine_atss = TacticEngine(max_depth=MAX_DEPTH)
    rows_atss = []

    for name, category, fstr in VERIFICATION_BENCHMARKS:
        n_v = len(parse(fstr).variables())
        print(f"  [{name}] ({category}, {n_v}v)...", end=" ", flush=True)
        stats = _run_one(fstr, engine_atss)
        rows_atss.append({
            'benchmark': name, 'category': category, 'n_vars': n_v,
            'solver': 'ATSS (accumulated)',
            'time_ms': stats['time_mean_ms'],
            'time_std_ms': stats['time_std_ms'],
            'proof_size': stats['proof_size'],
            'proof_depth': stats['proof_depth'],
            'status': stats['status'],
            'solve_rate': stats['solve_rate'],
        })
        print(f"t={stats['time_mean_ms']:.2f}ms sz={stats['proof_size']:.0f} "
              f"dp={stats['proof_depth']:.0f} {stats['status']}")

    # ── Phase 2: noATSS (fresh engine per benchmark) ───────────────────────────
    print("\n[Phase 2] noATSS (fresh engine per benchmark, no cross-learning)")
    print("-" * 50)
    rows_no = []

    for name, category, fstr in VERIFICATION_BENCHMARKS:
        n_v = len(parse(fstr).variables())
        engine = TacticEngine(max_depth=MAX_DEPTH)
        print(f"  [{name}] ({category}, {n_v}v)...", end=" ", flush=True)
        stats = _run_one(fstr, engine)
        rows_no.append({
            'benchmark': name, 'category': category, 'n_vars': n_v,
            'solver': 'noATSS (fresh)',
            'time_ms': stats['time_mean_ms'],
            'time_std_ms': stats['time_std_ms'],
            'proof_size': stats['proof_size'],
            'proof_depth': stats['proof_depth'],
            'status': stats['status'],
            'solve_rate': stats['solve_rate'],
        })
        print(f"t={stats['time_mean_ms']:.2f}ms sz={stats['proof_size']:.0f} "
              f"dp={stats['proof_depth']:.0f} {stats['status']}")

    # ── Write CSV ──────────────────────────────────────────────────────────────
    all_rows = rows_atss + rows_no
    columns = ['benchmark', 'category', 'n_vars', 'solver', 'time_ms',
               'time_std_ms', 'proof_size', 'proof_depth', 'status', 'solve_rate']
    path = os.path.join(RESULTS_DIR, 'exp_verification_benchmarks.csv')
    with open(path, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=columns, extrasaction='ignore')
        writer.writeheader()
        writer.writerows(all_rows)

    print(f"\n[OK] Written {len(all_rows)} rows to {path}")

    # ── Summary ────────────────────────────────────────────────────────────────
    n = len(VERIFICATION_BENCHMARKS)
    atss_proved = sum(1 for r in rows_atss if r['status'] == 'PROVED')
    no_proved = sum(1 for r in rows_no if r['status'] == 'PROVED')
    atss_times = [r['time_ms'] for r in rows_atss if r['status'] == 'PROVED']
    no_times = [r['time_ms'] for r in rows_no if r['status'] == 'PROVED']
    atss_time = statistics.mean(atss_times) if atss_times else 0
    no_time = statistics.mean(no_times) if no_times else 0

    print(f"\nSummary:")
    print(f"  ATSS (accumulated): {atss_proved}/{n} proved, "
          f"avg {atss_time:.2f}ms")
    print(f"  noATSS (fresh):     {no_proved}/{n} proved, "
          f"avg {no_time:.2f}ms")
    if atss_time > 0 and no_time > 0:
        print(f"  Speedup: {no_time / atss_time:.2f}x")
    else:
        print(f"  Speedup: N/A (not enough data)")

    # ── CDCL baseline for all benchmarks ───────────────────────────────────────
    print(f"\n[CDCL Baseline] (for reference)")
    print("-" * 50)
    for name, category, fstr in VERIFICATION_BENCHMARKS:
        r = _run_cdcl(fstr)
        print(f"  [{name}] t={r['time_ms']:.2f}ms {r['status']}")

    print("Done.")


if __name__ == '__main__':
    main()
