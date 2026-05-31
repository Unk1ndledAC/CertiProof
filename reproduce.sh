#!/bin/bash
# CertiProof — One-command reproducibility script
# Usage: ./reproduce.sh [--skip-paper] [--skip-experiments] [--quick]
#
# Stages:
#   1. Verify Rocq formalisation compiles
#   2. Run all experiments and generate data
#   3. Generate all figures
#   4. Compile the paper (pdflatex + bibtex)

set -euo pipefail

QUICK_MODE=false
SKIP_PAPER=false
SKIP_EXPERIMENTS=false

for arg in "$@"; do
  case "$arg" in
    --quick)           QUICK_MODE=true ;;
    --skip-paper)      SKIP_PAPER=true ;;
    --skip-experiments) SKIP_EXPERIMENTS=true ;;
  esac
done

echo "=========================================="
echo " CertiProof — Reproducibility Pipeline"
echo "=========================================="

# -------------------------------------------------------------------
# Stage 0: Check environment
# -------------------------------------------------------------------
echo ""
echo "[Stage 0] Checking environment..."
python3 --version
echo "Working directory: $(pwd)"

# -------------------------------------------------------------------
# Stage 1: Verify Rocq formalisation
# -------------------------------------------------------------------
echo ""
echo "[Stage 1] Verifying Rocq formalisation..."

# If Rocq/Coq is available, compile the formalisation
if command -v coqc &> /dev/null; then
  echo "  Found coqc: $(which coqc)"
  echo "  Compiling CertiProof.v..."
  cd coq
  coqc CertiProof.v
  cd ..
  echo "  [OK] Rocq formalisation compiles successfully."
elif command -v rocq &> /dev/null; then
  echo "  Found rocq: $(which rocq)"
  echo "  Compiling CertiProof.v..."
  cd coq
  rocq compile CertiProof.v
  cd ..
  echo "  [OK] Rocq formalisation compiles successfully."
else
  echo "  [WARNING] Rocq/Coq compiler (coqc or rocq) not found."
  echo "  Formal verification skipped. Install Rocq 9.0 to verify proofs:"
  echo "    https://rocq-prover.org/"
  echo "  The coq/CertiProof.v file is still provided for inspection."
fi

# -------------------------------------------------------------------
# Stage 2: Verify Python installation
# -------------------------------------------------------------------
echo ""
echo "[Stage 2] Verifying Python installation..."
python3 verify_installation.py
echo "  [OK] All Python modules import successfully."

# -------------------------------------------------------------------
# Stage 3: Run experiments
# -------------------------------------------------------------------
if [ "$SKIP_EXPERIMENTS" = true ]; then
  echo ""
  echo "[Stage 3] Skipping experiments (--skip-experiments)."
else
  echo ""
  echo "[Stage 3] Running experiments..."

  if [ "$QUICK_MODE" = true ]; then
    echo "  Quick mode: reduced problem counts and variables."
    # Generate data with reduced parameters for quick testing
    cd experiments
    python3 generate_all_data.py --quick 2>&1 | tail -20
    cd ..
  else
    # Full experiment suite
    cd experiments

    # Generate all experiment data
    echo "  Running full experiment suite..."
    python3 generate_all_data.py 2>&1 | tail -30

    # Additional experiment data generators
    echo "  Generating real data..."
    python3 gen_real_data.py 2>&1 | tail -10

    echo "  Generating complex learning data..."
    python3 gen_complex_learning.py 2>&1 | tail -10

    echo "  Generating verification benchmarks..."
    python3 gen_verification_benchmarks.py 2>&1 | tail -10

    cd ..
    echo "  [OK] All experiments completed."
  fi
fi

# -------------------------------------------------------------------
# Stage 4: Generate figures
# -------------------------------------------------------------------
echo ""
echo "[Stage 4] Generating figures..."
cd experiments
if [ "$QUICK_MODE" = true ]; then
  python3 plot_all_figures.py --quick 2>&1 | tail -10
else
  python3 plot_all_figures.py 2>&1 | tail -15
fi
cd ..
echo "  [OK] All figures generated in experiments/figures/."

# -------------------------------------------------------------------
# Stage 5: Compile paper
# -------------------------------------------------------------------
if [ "$SKIP_PAPER" = true ]; then
  echo ""
  echo "[Stage 5] Skipping paper compilation (--skip-paper)."
else
  echo ""
  echo "[Stage 5] Compiling paper..."
  cd paper
  pdflatex -interaction=nonstopmode certiproof.tex
  bibtex certiproof
  pdflatex -interaction=nonstopmode certiproof.tex
  pdflatex -interaction=nonstopmode certiproof.tex
  cd ..
  echo "  [OK] Paper compiled: paper/certiproof.pdf"
fi

# -------------------------------------------------------------------
# Summary
# -------------------------------------------------------------------
echo ""
echo "=========================================="
echo "  Reproduction complete!"
echo "=========================================="
echo "  Results:"
echo "    - Experimental data: experiments/results/"
if [ "$SKIP_EXPERIMENTS" = false ]; then
  echo "    - Figures:           experiments/figures/"
fi
if [ "$SKIP_PAPER" = false ]; then
  echo "    - Paper PDF:         paper/certiproof.pdf"
fi
if command -v coqc &> /dev/null || command -v rocq &> /dev/null; then
  echo "    - Rocq verification: coq/ (compiled)"
fi
echo ""
echo "  Artifact structure:"
echo "    src/         Core solver implementation"
echo "    experiments/ Experiment scripts and results"
echo "    coq/         Rocq formalisation"
echo "    paper/       LaTeX source and PDF"
echo "=========================================="
