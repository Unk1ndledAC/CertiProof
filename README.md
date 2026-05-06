# NeuroProof

**A Hybrid Propositional Proof System with Adaptive Tactic Synthesis and Certified Proof Checking**

NeuroProof is a hybrid propositional proof system that combines natural deduction, sequent calculus, and resolution with three novel rules: ADAPTIVE_CUT, LEMMA_REUSE, and INTERPOLANT. It features ATSS (Adaptive Tactic Synthesis System), an online bandit-style learning component that guides proof search without pre-training, and an optional GNN-based tactic selector.

## Key Features

- **Hybrid proof calculus**: Natural deduction + sequent calculus + resolution rules
- **Novel rules**: ADAPTIVE_CUT (learned cut formula selection), LEMMA_REUSE (proof DAG edge reuse), INTERPOLANT (Craig interpolation via CDCL)
- **ATSS**: Online tactic synthesis with zero pre-training (EMA updates, cosine similarity ranking)
- **GNN ATSS**: Optional graph neural network for structure-aware tactic selection (GIN encoder, GPU-accelerated)
- **Certified checking**: Dual Python/Rocq verification chain following the de Bruijn criterion
- **DAG proof compression**: Proof size reduction of s - Omega(log s)
- **CDCL solver**: Full CDCL with 1-UIP conflict analysis, VSIDS, Luby restarts, clause deletion, phase saving

## Project Structure

```
NeuroProof/
├── src/                          # Core library (pure Python, no dependencies)
│   ├── __init__.py               # Public API exports
│   ├── formula.py                # Formula AST, parser, NNF/CNF transformations
│   ├── proof.py                  # Proof steps, ProofBuilder, Rule enum
│   ├── kernel.py                 # Trusted verification kernel (TCB, 287 lines)
│   ├── solver.py                 # CDCL solver + ATSS + Craig interpolation
│   ├── tactic.py                 # Tactic engine (9 tactics, GNN integration)
│   ├── tseitin.py                # Tseitin linear-size CNF encoding
│   └── atss_gnn.py               # GNN-based tactic selection (optional, GPU)
├── experiments/
│   ├── __init__.py
│   ├── benchmark_suite.py        # Full benchmark suite (9 experiments)
│   ├── plot_results.py           # Publication-quality plot generation (8 figures)
│   ├── results.csv               # Experiment output data
│   └── figures/                  # Generated plots (PDF)
├── scripts/
│   ├── run_exp1_phase_transition.py
│   ├── run_exp2_pigeonhole.py
│   ├── run_exp3_tseitin.py
│   ├── run_exp4_tautologies.py
│   ├── run_exp5_atss_learning.py
│   └── run_all_experiments.py
├── coq/
│   └── NeuroProof.v              # Rocq/Coq formalisation (soundness + ADAPTIVE_CUT)
├── verify_installation.py        # Quick smoke test (no dependencies)
├── EXPERIMENTS.md                # Detailed experiment reproduction guide
├── requirements.txt              # Python dependencies
├── LICENSE                       # MIT License
└── README.md
```

## Requirements

- **Python**: 3.10+ (tested on 3.12.4)
- **Core library**: No external dependencies (pure Python standard library)
- **Optional**: `matplotlib`, `numpy`, `pandas`, `python-sat` for experiments
- **Optional**: `torch`, `torch_geometric` for GNN ATSS (GPU recommended)
- **Optional**: Rocq/Coq 8.19+ for formal verification

## Quick Start

### 1. Verify Installation

```bash
cd NeuroProof
python verify_installation.py
```

Expected output: `All tests passed! NeuroProof is correctly installed.` (under 10s, no dependencies needed)

### 2. Run Experiments

Run individual experiments:

```bash
# EXP-4: Classical tautology proofs (fastest, ~1 second)
python experiments/benchmark_suite.py --exp 4

# EXP-2: Pigeonhole Principle (~2 minutes)
python experiments/benchmark_suite.py --exp 2

# EXP-5: ATSS online learning (~30 seconds)
python experiments/benchmark_suite.py --exp 5

# Run multiple experiments
python experiments/benchmark_suite.py --exp 2,4,5
```

Run all experiments:

```bash
python experiments/benchmark_suite.py --exp all
```

Results are saved to `experiments/results.csv`.

See [EXPERIMENTS.md](EXPERIMENTS.md) for detailed documentation of all 9 experiments.

### 3. Generate Plots (optional)

```bash
pip install matplotlib numpy pandas
python experiments/plot_results.py
```

Plots are saved to `experiments/figures/`.

### 4. Rocq Formal Verification (optional)

```bash
cd coq
coqc NeuroProof.v
```

## Public API

```python
from src import Var, Not, And, Or, Implies, parse, tauto, decide, NeuroProofSolver

# Parse and prove a tautology
f = parse("(p -> q) -> ((not q) -> (not p))")  # contrapositive
proof = tauto(f)
print(f"Proof size: {proof.size}, depth: {proof.depth}, verified: {proof.check()}")

# SAT solving
result = decide(parse("p | q"))
print(f"Status: {result}")  # SAT

# CDCL solving via clause interface
from src.solver import NeuroProofSolver, Clause
solver = NeuroProofSolver(max_conflicts=10000)
clauses = [
    frozenset([('x1', True), ('x2', True)]),
    frozenset([('x1', False), ('x2', True)]),
    frozenset([('x1', True), ('x2', False)]),
]
result = solver.solve_clauses(clauses, {'x1', 'x2'})
print(f"Status: {result.status}")
```

## Architecture

### Trusted Computing Base (TCB)

The verification kernel (`kernel.py`, 287 lines) is intentionally minimal:
- Each proof step is verified by pattern-matching against the rule definition
- All other modules (ATSS, interpolation, tactic engine, GNN) produce `ProofStep` objects that pass through the kernel
- A bug in untrusted components cannot produce a false proof that passes verification

### ATSS (Adaptive Tactic Synthesis System)

- Maintains a tactic embedding table: formula hash -> (success_count, attempt_count)
- Updates via exponential moving average (decay=0.95)
- Cut formula selection by maximizing cosine similarity (sparse bag-of-subformulas)
- Learns online during proof search, no pre-training required

### GNN ATSS (optional)

- 3-layer GIN (Graph Isomorphism Network) on bipartite variable-clause graphs
- Online learning with experience replay buffer (size 64)
- Blended scoring: 50% GNN + 50% cosine ATSS
- Trained on GPU with Adam optimizer (lr=1e-3)

### CDCL Solver

- Standard CDCL with 1-UIP conflict analysis and clause learning
- ATSS-enriched VSIDS heuristic for variable selection
- Luby restart sequence, phase saving, clause deletion
- Craig interpolant extraction via Pudlak's algorithm
- Proof logging via `ProofStep` DAG construction

## Experiments

| # | Name | Description | Est. Time |
|---|------|-------------|----------|
| 1 | Phase Transition | Random 3-CNF, ratio 2.0-6.0 | ~5-15 min |
| 2 | Pigeonhole | PHP_n (n=2..6), hard UNSAT | ~2 min |
| 3 | Tseitin | Graph-based Tseitin tautologies | ~2 min |
| 4 | Proof Quality | 15 classical tautologies | ~1 sec |
| 5 | ATSS Learning | Online learning convergence | ~30 sec |
| 6 | Ablation | CDCL vs ATSS contribution | ~5 min |
| 7 | Scalability | n_vars sweep at phase transition | ~5 min |
| 8 | SOTA Comparison | PHP + 3-CNF vs baselines | ~3 min |
| 9 | GNN ATSS | GNN vs cosine tactic selection | ~2 min (GPU) |

See [EXPERIMENTS.md](EXPERIMENTS.md) for full reproduction instructions.

## Citation

```bibtex
@article{qu2026neuroproof,
  title={NeuroProof: A Hybrid Propositional Proof System with Adaptive Tactic Synthesis and Certified Proof Checking},
  author={Qu, Guanheng and Zhang, Chunxiao and Liu, Jiangming},
  journal={},
  year={2026}
}
```
