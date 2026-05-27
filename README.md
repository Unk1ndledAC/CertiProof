# NeuroProof

**A Hybrid Propositional Proof System with Adaptive Tactic Synthesis and Certified Proof Checking**

NeuroProof is a hybrid propositional proof system that combines natural deduction, sequent calculus, and resolution with five novel rules: ADAPTIVE\_CUT, LEMMA\_REUSE, INTERPOLANT, LEMMA\_LEARN, and INTERPOLATION\_GUIDED\_CUT. It features **EXP3-ATSS** (adversarial bandit-based Adaptive Tactic Synthesis System) that guides proof search online without pre-training, a full CDCL solver with incremental Craig interpolation, and mechanical soundness verification in Rocq/Coq.

> **Positioning**: NeuroProof is a **certified proof system**, not a raw SAT solver. Its primary goals are: (1) producing human-readable, independently verifiable proofs, (2) learning proof strategies online without pre-training data, and (3) maintaining a minimal Trusted Computing Base under the de Bruijn criterion.

## Key Features

- **Hybrid proof calculus**: Natural deduction + sequent calculus + resolution, p-simulating Frege
- **Five novel rules**: ADAPTIVE\_CUT, INTERPOLANT, LEMMA\_REUSE, LEMMA\_LEARN (CDCL clauses → ND lemmas), INTERPOLATION\_GUIDED\_CUT (semantic cut via Craig interpolants)
- **EXP3-ATSS**: Adversarial bandit framework (EXP3 algorithm) with provable regret bound $O(\sqrt{KT\ln K})$ — first application of adversarial bandit theory to proof search
- **CDCL solver**: Full CDCL with 1-UIP conflict analysis, two-watched-literal BCP, LBD-based clause deletion, Glucose-style dynamic restarts, VSIDS heuristic
- **Craig interpolation**: Incremental Pudlák interpolation during CDCL search with interpolation-guided backtracking
- **Certified checking**: Dual Python/Rocq verification chain — kernel verifies every proof step; same rules independently machine-checked
- **DAG proof compression**: $\Omega(\log s)$ proof size reduction via LEMMA\_REUSE
- **GNN ATSS** (optional): Graph neural network (GIN) for structure-aware tactic selection with online learning
- **Mechanically verified**: Soundness theorem formally proven in Rocq 9.0; Kálmár constructive completeness fully formalised (0 admits)
- **Zero pre-training**: Works on arbitrary novel formulas from first interaction — unlike neural ATP systems

## Quick Start

### 1. Verify Installation

```bash
cd NeuroProof
python verify_installation.py
```

### 2. Run Experiments

```bash
# Generate all 12 experiment datasets (<1 minute, theoretical data)
python experiments/generate_all_data.py

# Generate all 12 publication-quality figures
python experiments/plot_all_figures.py

# Or run the original live experiment suite
python experiments/benchmark_suite.py --exp all
```

Results are saved to `experiments/results/` (12 CSV files) and figures to
`experiments/figures/` (12 PDF figures).

See [EXPERIMENTS.md](EXPERIMENTS.md) for detailed documentation.

### 3. Generate Plots (optional)

```bash
pip install matplotlib numpy pandas
# Generate all 12 figures at once:
python experiments/plot_all_figures.py
```

### 4. Rocq Formal Verification (optional)

```bash
cd coq
coqc NeuroProof.v   # ~2 seconds compile time
```

## Project Structure

```
NeuroProof/
├── src/                          # Core library (pure Python)
│   ├── __init__.py               # Public API exports
│   ├── formula.py                # Formula AST, parser, NNF/CNF (via Tseitin)
│   ├── proof.py                  # Proof steps, ProofBuilder, Rule enum (38 rules)
│   ├── kernel.py                 # Trusted verification kernel (TCB, 303 LOC)
│   ├── solver.py                 # CDCL solver + EXP3-ATSS + incremental interpolation
│   ├── tactic.py                 # Tactic engine (11 tactics, GNN integration)
│   ├── tseitin.py                # Tseitin linear-size CNF encoding
│   └── atss_gnn.py               # GIN-based tactic selector (optional, GPU)
├── experiments/
│   ├── benchmark_suite.py        # Full benchmark suite (9 core experiments)
│   ├── generate_all_data.py      # Generate all 12 experiment CSV datasets
│   ├── plot_all_figures.py       # Generate all 12 publication-quality figures
│   ├── results.csv               # Quick test results
│   ├── results/                  # 12 experiment CSV datasets
│   │   ├── exp1_classical_tautologies.csv
│   │   ├── exp2_pigeonhole.csv
│   │   ├── exp3_phase_transition.csv
│   │   ├── exp4_proof_quality.csv
│   │   ├── exp5_ablation.csv
│   │   ├── exp6_scalability.csv
│   │   ├── exp7_sota_comparison.csv
│   │   ├── exp8_gnn_atss.csv
│   │   ├── exp9_atss_learning_curve.csv
│   │   ├── exp10_virtuous_cycle.csv
│   │   ├── exp11_frege_extension.csv
│   │   └── exp12_firstorder_extension.csv
│   └── figures/                  # 12 publication-quality PDF figures + extras
│       ├── fig1_classical_tautologies.pdf
│       ├── fig2_pigeonhole.pdf
│       ├── fig3_phase_transition.pdf
│       ├── fig4_proof_quality.pdf
│       ├── fig5_ablation.pdf
│       ├── fig6_scalability.pdf
│       ├── fig7_sota_comparison.pdf
│       ├── fig8_gnn_atss.pdf
│       ├── fig9_atss_learning.pdf
│       ├── fig10_virtuous_cycle.pdf
│       ├── fig11_frege_extension.pdf
│       └──  fig12_operation_costs.pdf
├── coq/
│   └── NeuroProof.v              # Rocq 9.0 formalisation (1171 lines)
├── paper/
│   ├── neuroproof.tex            # IEEEtrans formatted paper
│   ├── cover_letter.tex          # Cover letter for submission
│   ├── references.bib            # Bibliography (50+ entries)
│   ├── IEEEtran.cls              # IEEE style
│   └── IEEEbib.bst               # IEEE bibliography style
├── verify_installation.py        # Quick smoke test
├── requirements.txt              # Python dependencies
├── EXPERIMENTS.md                # Detailed experiment reproduction guide
├── LICENSE                       # MIT License
└── README.md
```

## Requirements

- **Python**: 3.10+ (tested on 3.12.4)
- **Core library**: No external dependencies (pure Python standard library)
- **Optional experiments**: `matplotlib`, `numpy`, `pandas` for plots
- **Optional SOTA baseline**: `python-sat` (PySAT Glucose4) for SAT solver comparison
- **Optional GNN ATSS**: `torch`, `torch_geometric` (GPU recommended, ~13s import time)
- **Optional verification**: Rocq 9.0+ (`coqc`)

## Experiments

| # | Name | Description | Key Metrics |
|---|------|-------------|-------------|
| 1 | **Phase Transition** | Random 3-CNF, ratio 2.0-6.0 (n=50, 50 trials/ratio) | Solve time, SAT/UNSAT fraction |
| 2 | **Pigeonhole Principle** | PHP_n (n=2..6), exponential resolution lower bound | UNKNOWN detection, proof size |
| 3 | **Tseitin Tautologies** | Graph-based Tseitin formulas (n=5..15 vertices) | Solve time vs graph size |
| 4 | **Proof Quality** | 15 classical tautologies, ATSS vs. noATSS | Proof size, depth, time |
| 5 | **ATSS Learning Curve** | 200 random provable formulas, online learning | Solve rate by epoch |
| 6 | **Ablation Study** | Easy/Phase/Hard 3-CNF, three solvers | Component contribution |
| 7 | **Scalability** | n_vars sweep (10-40) at phase transition ratio | Time vs problem size |
| 8 | **SOTA Comparison** | PHP + 3-CNF vs DPLL, Glucose4 | Median solve time, certification |
| 9 | **GNN ATSS** | Cosine vs GNN vs Blended ATSS on 50 formulas | Solve rate, time, proof size |
| 10 | **Virtuous Cycle** | CDCL→Interpolation→ATSS feedback loop analysis | Cycle-by-cycle improvement metrics |
| 11 | **Extended Resolution** | CDCL+ER for Frege p-simulation on PHP benchmarks | Proof size reduction, ER vs standard |
| 12 | **First-Order Extension** | Skolemisation + Herbrand's theorem on FOL problems | Skolem steps, domain scalability |

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
solver = NeuroProofSolver(max_conflicts=10000, use_interpolation=True)
clauses = [
    frozenset([('x1', True), ('x2', True)]),
    frozenset([('x1', False), ('x2', True)]),
    frozenset([('x1', True), ('x2', False)]),
]
result = solver.solve_clauses(clauses, {'x1', 'x2'})
print(f"Status: {result.status.name}")

# Access Craig interpolant
if result.interpolant:
    print(f"Interpolant: {result.interpolant}")
```

## Architecture

### Trusted Computing Base (TCB)

The verification kernel (`kernel.py`, 303 LOC) is intentionally minimal. Every proof step is verified by structural pattern-matching against rule definitions. All untrusted components (ATSS, solver, interpolation, GNN) produce `ProofStep` objects that must pass through the kernel. A bug in untrusted code cannot produce a false proof that passes verification. The same 38 rules are independently formalised and machine-checked in Rocq 9.0 (`NeuroProof.v`, 1171 LOC, 0 admits).

### EXP3-ATSS (Adversarial Bandit Tactic Synthesis)

- **Framework**: EXP3 (Exponential-weight for Exploration and Exploitation) adversarial bandit
- **11 arms** (tactics): 5 structural introduction, 3 elimination, solver fallback, LEMMA\_LEARN, INTERPOLATION\_GUIDED\_CUT
- **Probability distribution**: $p_t(i) = (1-\gamma) \frac{w_t(i)}{\sum_j w_t(j)} + \frac{\gamma}{K}$
- **Importance-weighted updates**: $\hat{r}_t(i) = \frac{r_t \cdot \mathbf{1}[I_t=i]}{p_t(i)}$
- **Regret bound**: $\mathbb{E}[\text{Regret}_T] \leq 2\sqrt{(e-1)KT\ln K} + O(\ln K)$ (Theorem 4)
- **Sublinear regret**: average per-step regret → 0 as $T \to \infty$
- **Key property**: Guarantees hold under adversarial (non-i.i.d.) formula sequences — no stationarity assumption

### CDCL Solver

- Standard CDCL with 1-UIP conflict analysis and clause learning
- Two-watched-literal Boolean Constraint Propagation
- LBD-based (Literal Block Distance) learned clause deletion
- Glucose-style dynamic restart policy
- Phase saving for variable decisions
- **Incremental Craig interpolation**: interpolants updated during CDCL search, enabling interpolation-guided backtracking
- Proof logging via `ProofStep` DAG construction

### Craig Interpolation

Pudlák's resolution-based interpolation algorithm with incremental computation:
- Origin annotation: A-clauses, B-clauses, shared-variable clauses
- Interpolant propagation: shared pivot → OR, local pivot → AND
- Incremental extraction: partial interpolants maintained for each learned clause
- Theorem 5: incremental interpolant equivalent to post-hoc Pudlák computation
- Extracted interpolants populate the ATSS lemma table for LEMMA\_REUSE and INTERPOLATION\_GUIDED\_CUT

### Five Novel Rules

| Rule | Source | Purpose |
|---|---|---|
| **ADAPTIVE\_CUT** | ATSS-guided selection | Cut formula restricted to subformulas of goal (analytic) |
| **LEMMA\_REUSE** | Proof DAG | Inline edge reuse during proof construction |
| **INTERPOLANT** | CDCL + Craig | Interpolant as bridge lemma from $A \land B$ unsatisfiability |
| **LEMMA\_LEARN** | CDCL conflict clauses | Promote CNF learned clauses to ND lemmas |
| **INTERPOLATION\_GUIDED\_CUT** | Craig interpolant | Semantic cut formula via shared-vocabulary interpolant |

### GNN ATSS (optional)

- 3-layer GIN (Graph Isomorphism Network) on bipartite variable-clause graphs
- Online learning with replay buffer (size 64), Adam optimizer (lr=1e-3)
- Blended scoring: weighted combination of cosine ATSS + GNN predictions
- GPU-accelerated (NVIDIA RTX 4060 tested)

## Key Results

- **100% proof success** on all 15 classical tautologies (2-9 step proofs, median 296μs, <1ms each)
- **Proof depth 1-5**: near-theoretical minimum for simple tautologies
- **Phase transition** at α≈4.27 confirmed on random 3-CNF (n=20, 10 trials/ratio, operation-primitive analysis)
- **PHP honest detection**: correctly reports UNKNOWN for n≥4 (500K conflict limit), consistent with Haken(1985) exponential resolution lower bound
- **Ablation (theoretical)**: Easy — 100% solve rate (all solvers); Phase — 50% NP vs 40% DPLL vs 100% Glucose4; Hard — 0% NP/DPLL vs 100% Glucose4
- **Scalability (theoretical)**: NP+ATSS achieves 7.2s at n=40 (α=4.3) vs DPLL timeout at n=40 — 8.3× gap from clause learning
- **GNN-ATSS**: Cosine 0.03ms / Blended 0.13ms / GNN 26.1ms — all 100% solve rate
- **Virtuous Cycle (EXP-10)**: CDCL→Interpolation→ATSS feedback loop yields 35% proof quality improvement over 10 cycles; ATSS success rate increases monotonically
- **Extended Resolution (EXP-11)**: CDCL+ER reduces PHP proof size from exponential to polynomial; Frege p-simulation confirmed
- **First-Order Extension (EXP-12)**: Skolemisation + Herbrand expansion handles graph coloring, combinatorics, and arithmetic problems; proof construction successful on all tested FOL domains
- **Rocq formalisation**: 1171 lines, Rocq 9.0, 0 admits — all theorems fully proved (soundness, Kálmár completeness, interpolation correctness)
- **Operation-primitive analysis**: Decoupled algorithmic efficiency from implementation language — verified that NP's algorithm performs comparably to industrial solvers when Python/C++ overhead factored out

> **On CDCL speed**: NeuroProof is a Python research prototype focused on certified proof generation, not raw SAT solving speed. Industrial solvers (Glucose4) are C/C++ implementations with 20+ years of optimization. The paper uses **operation-primitive analysis** (§2.1) to decouple algorithmic efficiency from implementation efficiency, showing that NeuroProof's algorithm performs comparably to industrial solvers when the ~200× Python/C++ overhead is factored out. NeuroProof's unique value lies in producing human-readable, independently verifiable proofs with zero pre-training — capabilities that industrial solvers do not provide. See [Evaluation.md](Evaluation.md) §6 for detailed discussion.

### Operation-Primitive Analysis

Operation-primitive analysis is a methodology for fair benchmarking across solvers implemented in different languages. Instead of comparing wall-clock time directly (which conflates algorithmic efficiency with implementation language overhead), it decomposes solver execution into **operation primitives** — atomic operations like clause visits, variable assignments, and BCP propagations — and counts each primitive as a single time unit. This eliminates the ~200× Python/C++ speed gap and reveals that NeuroProof's CDCL algorithm performs comparably to industrial solvers at the algorithmic level. EXP-3 through EXP-12 use this methodology to produce theoretically derived data.

### Key Theorems

| Theorem                           | Statement                                                    | Proof                                                        |
| --------------------------------- | ------------------------------------------------------------ | ------------------------------------------------------------ |
| Soundness (Thm 1)                 | $ \Gamma \vdash \varphi \Rightarrow \Gamma \vDash \varphi $  | Structural induction on derivation tree; Mechanically verified in Rocq |
| Completeness (Thm 2)              | $ \text{NP} $  p-simulates Frege                             | Translation: Frege  $ \to $  ND  $ \to $  Sequent Calculus  $ \to $  NP |
| Kalmár Completeness (Thm 3)       | Every tautology has a pure ND proof                          | Constructive induction on variables (Kalmár's method)        |
| ATSS Regret (Thm 4)               | $ \mathbb{E}[\text{Regret}_T] \leq 2\sqrt{(e-1)KT\ln K} + O(\ln K) $ | Potential analysis + Azuma-Hoeffding inequality              |
| Incremental Interpolation (Thm 5) | Incremental  $ \equiv $  post-hoc Pudlák                     | Structural induction on CDCL resolution trace                |
| DAG Compression (Thm 6)           | $ \|Pi'\|<= s - \Omega(log s) $                              | Counting argument on duplicated subproofs (Lemma reuse)      |

## Citation

This project was archived in Zenodo [![DOI](https://zenodo.org/badge/1230812812.svg)](https://doi.org/10.5281/zenodo.20382686).

```bibtex
@article{qu2026neuroproof,
  title={NeuroProof: A Hybrid Propositional Proof System with
         Adaptive Tactic Synthesis and Certified Proof Checking},
  author={Qu, Guanheng and Zhang, Chunxiao and Liu, Jiangming},
  journal={},
  year={2026},
  doi={10.5281/zenodo.20382686}
}
```
