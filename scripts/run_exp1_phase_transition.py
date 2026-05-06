"""
run_exp1_phase_transition.py
==============================
EXP-1: Random 3-CNF Phase Transition.

Sweep clause-to-variable ratio from 2.0 to 6.0 around the
phase transition (~4.27 for 3-CNF). Compares NeuroProof,
DPLL-Baseline, and Glucose4.

Usage:
    python scripts/run_exp1_phase_transition.py
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from experiments.benchmark_suite import ExperimentRunner

if __name__ == '__main__':
    runner = ExperimentRunner(output_dir=os.path.join(os.path.dirname(__file__), '..', 'experiments'))
    runner.exp_random_3cnf(n_vars=20, n_trials=10)
    runner.save_results('results.csv')
