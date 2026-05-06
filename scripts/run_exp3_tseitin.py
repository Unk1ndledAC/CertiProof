"""
run_exp3_tseitin.py
===================
EXP-3: Tseitin Tautologies.

Evaluate on graph-based Tseitin encodings of varying sizes.

Usage:
    python scripts/run_exp3_tseitin.py
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from experiments.benchmark_suite import ExperimentRunner

if __name__ == '__main__':
    runner = ExperimentRunner(output_dir=os.path.join(os.path.dirname(__file__), '..', 'experiments'))
    runner.exp_tseitin(n_trials=10)
    runner.save_results('results.csv')
