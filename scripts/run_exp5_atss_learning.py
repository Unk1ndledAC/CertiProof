"""
run_exp5_atss_learning.py
==========================
EXP-5: ATSS Online Learning Curve.

Demonstrate that ATSS improves over time on a stream of
random provable formulas.

Usage:
    python scripts/run_exp5_atss_learning.py
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from experiments.benchmark_suite import ExperimentRunner

if __name__ == '__main__':
    runner = ExperimentRunner(output_dir=os.path.join(os.path.dirname(__file__), '..', 'experiments'))
    runner.exp_atss_learning_curve(n_problems=100)
    runner.save_results('results.csv')
