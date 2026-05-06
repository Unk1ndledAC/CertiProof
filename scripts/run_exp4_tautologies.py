"""
run_exp4_tautologies.py
========================
EXP-4: Proof Quality (ATSS vs no-ATSS).

Prove 15 classical propositional tautologies with and without
ATSS guidance. Measures proof size, depth, and time.

Usage:
    python scripts/run_exp4_tautologies.py
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from experiments.benchmark_suite import ExperimentRunner

if __name__ == '__main__':
    runner = ExperimentRunner(output_dir=os.path.join(os.path.dirname(__file__), '..', 'experiments'))
    runner.exp_proof_quality()
    runner.save_results('results.csv')
