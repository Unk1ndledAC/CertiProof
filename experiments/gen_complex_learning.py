#!/usr/bin/env python3
"""
gen_complex_learning.py — Complex Formula ATSS Learning Curve Experiment (P2-2)
===============================================================================
Extends the ATSS learning experiment beyond simple tautologies to
structurally complex propositional formulas. Tests whether ATSS's
online learning generalizes across diverse proof strategies.

A single ATSS instance runs through all formulas epoch after epoch,
accumulating tactic weights. The baseline is a fresh ATSS per epoch
(no cross-epoch or cross-formula learning).

Formula categories: implication chains, contrapositive, dilemma,
distributivity, resolution patterns, classical tautologies.
NO <-> (iff) formulas — these cause ND proof search blowup.

Output: experiments/results/exp_complex_learning.csv

Usage:
    python gen_complex_learning.py
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
from src.solver import ATSS
from src.formula import parse, Formula

# ── Config ────────────────────────────────────────────────────────────────────
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
RESULTS_DIR = os.path.join(BASE_DIR, "results")
os.makedirs(RESULTS_DIR, exist_ok=True)

N_EPOCHS = 5
MAX_DEPTH = 50
PER_FORMULA_TIMEOUT = 10.0  # seconds
SEED = 42

random.seed(SEED)


# ── Complex Formula Set (NO <->, all implication/conjunction/disjunction) ──────

COMPLEX_FORMULAS = [
    # Implication chains (longer = harder for ND)
    ("Impl_Chain_5", "Implication",
     "((a -> b) & (b -> c) & (c -> d) & (d -> e)) -> (a -> e)"),
    ("Impl_Chain_6", "Implication",
     "((a -> b) & (b -> c) & (c -> d) & (d -> e) & (e -> f)) -> (a -> f)"),

    # Hypothetical syllogism nested
    ("HypSyl_Nested", "Implication",
     "((a -> (b -> c)) & (a -> b)) -> (a -> c)"),

    # Contrapositive reasoning
    ("Contrapos_Chain", "Contrapositive",
     "((a -> b) & (b -> c)) -> (~c -> ~a)"),

    # Dilemma (n-way)
    ("Dilemma_3way", "Dilemma",
     "((a | b | c) & (a -> d) & (b -> d) & (c -> d)) -> d"),

    # Distributivity (one direction)
    ("Distrib_Fwd", "Distributivity",
     "(a & (b | c)) -> ((a & b) | (a & c))"),
    ("Distrib_Back", "Distributivity",
     "((a & b) | (a & c)) -> (a & (b | c))"),

    # Resolution patterns
    ("Resolution_Chain", "Resolution",
     "((a | b) & (~a | c) & (~b | d)) -> (c | d)"),
    ("Resolve_Unit_Chain", "Resolution",
     "((a | b) & ~a & ((b | c) & ~b)) -> c"),

    # Classical tautologies
    ("Peirce", "Classical",
     "((a -> b) -> a) -> a"),
    ("Reductio", "Classical",
     "((a -> b) & (a -> ~b)) -> ~a"),

    # Structural / Frege
    ("Frege_2", "Structural",
     "(a -> (b -> c)) -> ((a -> b) -> (a -> c))"),
    ("Exportation_Fwd", "Structural",
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


def _run_formulas(formula_strs: List[str], atss: ATSS) -> dict:
    """Run all formulas through TacticEngine with given ATSS (once each)."""
    times = []
    proved_count = 0
    sizes = []
    depths = []

    for fstr in formula_strs:
        f = parse(fstr)
        engine = TacticEngine(atss=atss, max_depth=MAX_DEPTH)
        elapsed, proof, error = _prove_with_timeout(
            engine, f, PER_FORMULA_TIMEOUT)
        if proof is not None:
            times.append(elapsed)
            proved_count += 1
            sizes.append(proof.size)
            depths.append(proof.depth)

    return {
        'solve_rate': proved_count / len(formula_strs),
        'time_mean_ms': round(statistics.mean(times) * 1000, 3) if times else 0,
        'time_std_ms': round(statistics.stdev(times) * 1000, 3)
        if len(times) > 1 else 0,
        'proof_size_mean': round(statistics.mean(sizes), 1) if sizes else 0,
        'proof_depth_mean': round(statistics.mean(depths), 1) if depths else 0,
        'n_proved': proved_count,
        'n_total': len(formula_strs),
    }


def main():
    print("=" * 70)
    print("Complex Formula ATSS Learning Curve (P2-2)")
    print("=" * 70)
    print(f"Formulas: {len(COMPLEX_FORMULAS)}")
    print(f"Epochs: {N_EPOCHS}")
    print(f"Timeout per formula: {PER_FORMULA_TIMEOUT}s")
    print()

    formula_strs = [f[2] for f in COMPLEX_FORMULAS]
    rows = []

    # ── ATSS with accumulated learning ─────────────────────────────────────────
    atss = ATSS()
    print("[ATSS Learning]")
    for epoch in range(1, N_EPOCHS + 1):
        print(f"  Epoch {epoch}/{N_EPOCHS}...", end=" ", flush=True)
        t0 = time.perf_counter()
        stats = _run_formulas(formula_strs, atss)
        elapsed = time.perf_counter() - t0
        rows.append({
            'epoch': epoch,
            'mode': 'ATSS',
            'solve_rate': round(stats['solve_rate'], 4),
            'time_ms': stats['time_mean_ms'],
            'time_std_ms': stats['time_std_ms'],
            'proof_size': stats['proof_size_mean'],
            'proof_depth': stats['proof_depth_mean'],
            'n_proved': stats['n_proved'],
            'n_total': stats['n_total'],
        })
        print(f"rate={stats['solve_rate']:.3f} "
              f"proved={stats['n_proved']}/{stats['n_total']} "
              f"epoch_time={elapsed:.1f}s")

    # ── Baseline: fresh ATSS per epoch (no cross-learning) ─────────────────────
    print("\n[Baseline: fresh ATSS per epoch]")
    for epoch in range(1, N_EPOCHS + 1):
        fresh_atss = ATSS()
        print(f"  Epoch {epoch}/{N_EPOCHS}...", end=" ", flush=True)
        t0 = time.perf_counter()
        stats = _run_formulas(formula_strs, fresh_atss)
        elapsed = time.perf_counter() - t0
        rows.append({
            'epoch': epoch,
            'mode': 'noATSS',
            'solve_rate': round(stats['solve_rate'], 4),
            'time_ms': stats['time_mean_ms'],
            'time_std_ms': stats['time_std_ms'],
            'proof_size': stats['proof_size_mean'],
            'proof_depth': stats['proof_depth_mean'],
            'n_proved': stats['n_proved'],
            'n_total': stats['n_total'],
        })
        print(f"rate={stats['solve_rate']:.3f} "
              f"proved={stats['n_proved']}/{stats['n_total']} "
              f"epoch_time={elapsed:.1f}s")

    # ── Write CSV ──────────────────────────────────────────────────────────────
    columns = ['epoch', 'mode', 'solve_rate', 'time_ms', 'time_std_ms',
               'proof_size', 'proof_depth', 'n_proved', 'n_total']
    path = os.path.join(RESULTS_DIR, 'exp_complex_learning.csv')
    with open(path, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=columns, extrasaction='ignore')
        writer.writeheader()
        writer.writerows(rows)

    print(f"\n[OK] Written {len(rows)} rows to {path}")

    # ── Summary ────────────────────────────────────────────────────────────────
    atss_rows = [r for r in rows if r['mode'] == 'ATSS']
    no_rows = [r for r in rows if r['mode'] == 'noATSS']
    if atss_rows and no_rows:
        print(f"\nLearning improvement (epoch 1 vs epoch {N_EPOCHS}):")
        print(f"  ATSS:    {atss_rows[0]['solve_rate']:.3f} "
              f"-> {atss_rows[-1]['solve_rate']:.3f}")
        print(f"  noATSS:  {no_rows[0]['solve_rate']:.3f} "
              f"-> {no_rows[-1]['solve_rate']:.3f}")
    print("Done.")


if __name__ == '__main__':
    main()
