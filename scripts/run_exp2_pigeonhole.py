"""
run_exp2_pigeonhole.py
=======================
EXP-2: Pigeonhole Principle PHP_n.

Evaluate NeuroProof, DPLL-Baseline, and Glucose4 on PHP_n
for n=2 to 6. These are hard UNSAT instances that require
exponential-size resolution proofs.

Usage:
    python scripts/run_exp2_pigeonhole.py
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from experiments.benchmark_suite import ExperimentRunner

if __name__ == '__main__':
    runner = ExperimentRunner(output_dir=os.path.join(os.path.dirname(__file__), '..', 'experiments'))
    runner.exp_pigeonhole(max_n=6)
    runner.save_results('results.csv')
