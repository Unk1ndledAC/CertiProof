# NeuroProof Experiment Reproduction Guide
# =======================================
# This document describes all 9 experiments in the NeuroProof
# benchmark suite, including exact commands, expected behavior,
# and approximate runtimes.

## Table of Contents
1. [Quick Verification](#quick-verification)
2. [Environment Setup](#environment-setup)
3. [Experiment Overview](#experiment-overview)
4. [Running Individual Experiments](#running-individual-experiments)
5. [Running All Experiments](#running-all-experiments)
6. [Generating Plots](#generating-plots)
7. [Expected Results](#expected-results)
8. [Troubleshooting](#troubleshooting)


## Quick Verification

Before running experiments, verify the installation:

```bash
cd NeuroProof
python verify_installation.py
```

Expected: "All tests passed! NeuroProof is correctly installed." (under 10s)


## Environment Setup

### Core (required, no external dependencies)

```bash
python -c "from src import tauto, parse; p = tauto(parse('p -> p')); print(f'OK: size={p.size}')"
```

### Experiments (optional dependencies)

```bash
pip install -r requirements.txt
```

### GNN ATSS (EXP-9 only, requires GPU)

```bash
pip install torch torch_geometric
```


## Experiment Overview

| # | Name | Description | Solvers | Est. Runtime |
|---|------|-------------|---------|-------------|
| 1 | Phase Transition | Random 3-CNF sweep, ratio 2.0-6.0 | NP, DPLL, Glucose4 | ~5-15 min |
| 2 | Pigeonhole | PHP_n for n=2..6 (hard UNSAT) | NP, DPLL, Glucose4 | ~2 min |
| 3 | Tseitin | Graph-based Tseitin tautologies | NP, Glucose4 | ~2 min |
| 4 | Proof Quality | 15 classical tautologies | NP+ATSS, NP-noATSS | ~1 sec |
| 5 | ATSS Learning | Online learning convergence | NP+ATSS | ~30 sec |
| 6 | Ablation | Isolate CDCL vs ATSS contribution | NP, DPLL, Glucose4 | ~5 min |
| 7 | Scalability | n_vars sweep at phase transition | NP, DPLL, Glucose4 | ~5 min |
| 8 | SOTA Comparison | PHP + random 3-CNF vs baselines | NP, DPLL, Glucose4 | ~3 min |
| 9 | GNN ATSS | GNN vs cosine tactic selection | Cosine, GNN, Blended | ~2 min (GPU) |

### Solver Abbreviations
- **NP** = NeuroProof (CDCL + ATSS)
- **DPLL** = DPLL-Baseline (no learning, no ATSS)
- **Glucose4** = PySAT Glucose4 (SOTA CDCL solver)

### Runtime Notes
- Runtimes are approximate and vary significantly with CPU speed and load
- EXP-1 and EXP-7 are the most time-consuming (many instances)
- EXP-4 is nearly instantaneous (15 small formulas)
- EXP-9 requires a CUDA-capable GPU for practical runtimes


## Running Individual Experiments

### Method 1: Via benchmark_suite.py (Recommended)

```bash
cd NeuroProof
python experiments/benchmark_suite.py --exp 4       # Run EXP-4 only
python experiments/benchmark_suite.py --exp 2,4,5    # Run EXP-2, 4, 5
python experiments/benchmark_suite.py --exp 1-3      # Run EXP-1, 2, 3
python experiments/benchmark_suite.py --exp all      # Run all 9 experiments
```

### Method 2: Via Python API

```python
import sys
sys.path.insert(0, '.')
from experiments.benchmark_suite import ExperimentRunner

runner = ExperimentRunner(output_dir='experiments')

# Run individual experiments
runner.exp_proof_quality()          # EXP-4 (~1 sec)
runner.exp_pigeonhole(max_n=6)      # EXP-2 (~2 min)
runner.exp_atss_learning_curve()    # EXP-5 (~30 sec)
runner.exp_random_3cnf()            # EXP-1 (~5-15 min)
runner.exp_tseitin()                # EXP-3 (~2 min)
runner.exp_ablation()               # EXP-6 (~5 min)
runner.exp_scalability()            # EXP-7 (~5 min)
runner.exp_sota_comparison()        # EXP-8 (~3 min)
runner.exp_gnn_atss()               # EXP-9 (~2 min, requires GPU)

# Save results
runner.save_results('results.csv')
```

### Experiment Details

#### EXP-1: Random 3-CNF Phase Transition
- Variables: n=20, clause ratio alpha=2.0 to 6.0 (step 0.2)
- Trials: 10 per ratio, 21 ratios
- Total instances: 21 x 10 x 3 solvers = 630
- Measures: SAT fraction, solve time vs ratio
- Expected: phase transition around alpha=4.27

#### EXP-2: Pigeonhole Principle
- PHP_n for n=2 to n=6
- 3 solvers x 5 instances = 15 runs
- Expected: DPLL solves all quickly; NeuroProof may report UNKNOWN
  (PHP requires exponential-resolution proofs)

#### EXP-3: Tseitin Tautologies
- Graph sizes: n=5, 8, 10, 12, 15
- 10 trials per size x 2 solvers = 100 runs
- Measures: solve time vs graph size

#### EXP-4: Proof Quality (ATSS vs no-ATSS)
- 15 classical propositional tautologies
- 2 configurations: NeuroProof+ATSS vs NeuroProof-noATSS
- Measures: proof size, proof depth, time

#### EXP-5: ATSS Online Learning Curve
- 100 random provable formulas in 5 epochs of 20
- Measures: solve rate per epoch (demonstrates online learning)

#### EXP-6: Ablation Study
- Part A: Easy 3-CNF (ratio=2.0, n=20), 10 trials
- Part B: Hard 3-CNF (ratio=6.0, n=20), 5 trials
- Part C: Phase transition (ratio=4.3, n=20), 5 trials
- 3 solvers x 20 instances = 60 runs

#### EXP-7: Scalability Sweep
- n_vars = 10, 15, 20, 25, 30, 35, 40
- 3 instances per size x 3 solvers = 63 runs
- Measures: solve time scaling at phase transition ratio

#### EXP-8: SOTA Comparison
- Part A: PHP_2 to PHP_5
- Part B: Random 3-CNF at ratios 2.0, 3.0, 4.0, 5.0 (n=20, 5 trials each)
- 3 solvers, ~27 total runs

#### EXP-9: GNN ATSS vs Cosine ATSS
- 50 random provable formulas
- 3 configurations: Cosine-ATSS, GNN-ATSS, Blended-ATSS
- Requires: torch, torch_geometric, CUDA GPU (optional but recommended)
- Falls back gracefully if GPU unavailable


## Running All Experiments

```bash
cd NeuroProof
python experiments/benchmark_suite.py --exp all
```

This runs EXP-1 through EXP-9 sequentially and saves results to
`experiments/results.csv`.

**Estimated total runtime**: ~25-40 minutes (CPU-bound)

To run only the fast experiments (for quick verification):
```bash
python experiments/benchmark_suite.py --exp 2,4,5
```

Estimated: ~2-3 minutes.


## Generating Plots

```bash
cd NeuroProof
pip install matplotlib numpy pandas
python experiments/plot_results.py
```

This generates 8 publication-quality PDF figures in `experiments/figures/`:
1. `fig1_phase_transition.pdf` - Phase transition + solve time
2. `fig2_pigeonhole.pdf` - PHP solve time and rate
3. `fig3_proof_quality.pdf` - Tautology proof quality table
4. `fig4_atss_learning.pdf` - ATSS learning convergence
5. `fig5_ablation.pdf` - Ablation study results
6. `fig6_scalability.pdf` - Scalability sweep
7. `fig7_sota_comparison.pdf` - SOTA comparison
8. `fig8_tseitin.pdf` - Tseitin performance

Each figure generator checks for the corresponding data in `results.csv`
and prints `[SKIP]` if data is unavailable.


## Expected Results

### EXP-2 (Pigeonhole Principle)
- DPLL-Baseline: UNSAT for all PHP_n (microseconds to seconds)
- Glucose4: UNSAT for all PHP_n (milliseconds)
- NeuroProof: UNKNOWN for PHP_n >= 3 (timeout at 50k conflicts)
  This is expected — PHP requires exponential resolution proofs

### EXP-4 (Proof Quality)
- Both ATSS and no-ATSS should PROVE all 15 tautologies
- ATSS should produce proofs of equal or smaller size

### EXP-5 (ATSS Learning)
- Solve rate should be high from the start (simple formulas)
- May show slight improvement across epochs

### EXP-9 (GNN ATSS)
- All three configurations should achieve high success rates
- GNN overhead adds ~1-10ms per formula (GPU training)
- Blended should match or exceed Cosine-only


## Troubleshooting

### Import Error: No module named 'src'
Make sure you're running from the project root:
```bash
cd NeuroProof
python experiments/benchmark_suite.py --exp 4
```

### PySAT not installed (Glucose4 shows UNAVAILABLE)
```bash
pip install python-sat
```
Glucose4 is optional; experiments still run with DPLL baseline.

### GPU not available for EXP-9
EXP-9 will skip automatically if torch/torch_geometric are not installed.
The script prints a message and returns without error.

### Results CSV is empty or incomplete
Each experiment appends to the results list. Make sure you call
`runner.save_results()` or use the CLI (which saves automatically).

### Memory issues on EXP-1
Reduce `n_vars` or `n_trials` in the `run_all` method of
`ExperimentRunner` in `benchmark_suite.py`.


## File Output

After running all experiments, the following files are produced:

```
experiments/
  results.csv        # All benchmark results (CSV format)
  figures/
    fig1_phase_transition.pdf
    fig2_pigeonhole.pdf
    fig3_proof_quality.pdf
    fig4_atss_learning.pdf
    fig5_ablation.pdf
    fig6_scalability.pdf
    fig7_sota_comparison.pdf
    fig8_tseitin.pdf
```

The `results.csv` columns are:
- `name`: experiment/instance identifier
- `instance_id`: trial number
- `n_vars`: number of variables
- `n_clauses`: number of clauses
- `status`: SAT / UNSAT / UNKNOWN / PROVED / FAIL
- `solver`: solver name
- `time_sec`: wall-clock time in seconds
- `decisions`: number of decisions
- `conflicts`: number of conflicts
- `learned`: number of learned clauses
- `proof_size`: number of proof steps
- `proof_depth`: maximum proof depth
