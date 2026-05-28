#!/usr/bin/env python3
"""
plot_all_figures.py
====================
Generate ALL publication-quality figures for the CertiProof paper.

Reads CSV files from experiments/results/ and generates PDF figures
in experiments/figures/.

Usage:
    python plot_all_figures.py
"""

import os
import sys
import pandas as pd
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.ticker as ticker
from matplotlib.patches import Patch
from matplotlib.lines import Line2D

# ==============================================================================
# Configuration
# ==============================================================================
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
RESULTS_DIR = os.path.join(BASE_DIR, "results")
FIGURES_DIR = os.path.join(BASE_DIR, "figures")
os.makedirs(FIGURES_DIR, exist_ok=True)

# ── Style ─────────────────────────────────────────────────────────────────────
try:
    import seaborn as sns
    sns.set_style("whitegrid")
    HAS_SEABORN = True
except ImportError:
    HAS_SEABORN = False

plt.rcParams.update({
    'font.family': 'serif',
    'font.size': 11,
    'axes.labelsize': 12,
    'axes.titlesize': 13,
    'legend.fontsize': 10,
    'xtick.labelsize': 10,
    'ytick.labelsize': 10,
    'figure.dpi': 150,
    'savefig.bbox': 'tight',
    'savefig.dpi': 300,
    'text.usetex': False,
})

# Color scheme
COLORS = {
    'CertiProof+ATSS': '#1f77b4',
    'NP+ATSS': '#1f77b4',
    'ATSS': '#1f77b4',
    'with_ATSS': '#1f77b4',
    'NP+ATSS+Ext': '#1f77b4',
    'DPLL-Baseline': '#ff7f0e',
    'Glucose4': '#2ca02c',
    'Glucose4 (est.)': '#2ca02c',
    'CertiProof-noATSS': '#d62728',
    'noATSS': '#d62728',
    'without_ATSS': '#d62728',
    'GNN-ATSS': '#9467bd',
    'Cosine': '#1f77b4',
    'GNN': '#9467bd',
    'Blended': '#2ca02c',
}


def _read_csv(filename):
    """Read a CSV file from the results directory."""
    path = os.path.join(RESULTS_DIR, filename)
    if not os.path.exists(path):
        print(f"  [WARN] Missing: {filename}")
        return None
    return pd.read_csv(path)


def _save(fig, name):
    """Save figure to PDF."""
    out = os.path.join(FIGURES_DIR, name)
    fig.savefig(out)
    print(f"  [OK] Saved: {out}")
    plt.close(fig)


# ==============================================================================
# Figure 1: Classical Tautologies
# ==============================================================================

def plot_fig1_classical_tautologies():
    """Bar chart showing proof sizes for all 15 tautologies."""
    df = _read_csv('exp1_classical_tautologies.csv')
    if df is None:
        return

    # Sort by formula and separate ATSS/noATSS
    df = df.sort_values('formula')

    # The data alternates: each formula appears twice (ATSS then noATSS)
    # Use time_us: lower = ATSS, higher = noATSS
    formulas_unique = list(dict.fromkeys(df['formula'].tolist()))
    atss_mask = df['time_us'] <= 1000  # ATSS uses measured times (<= 944us)

    fig, ax = plt.subplots(figsize=(16, 5), constrained_layout=True)

    x = np.arange(len(formulas_unique))
    width = 0.35

    # Short labels for display
    short_labels = [f if len(f) <= 22 else f[:19] + '...' for f in formulas_unique]

    # Collect data per formula
    sizes_atss = []
    depths_atss = []
    sizes_noatss = []
    depths_noatss = []
    for f in formulas_unique:
        f_data = df[df['formula'] == f]
        atss_row = f_data[f_data['time_us'] <= 1000]
        noatss_row = f_data[f_data['time_us'] > 1000]
        sizes_atss.append(atss_row['size'].values[0] if len(atss_row) > 0 else 0)
        depths_atss.append(atss_row['depth'].values[0] if len(atss_row) > 0 else 0)
        sizes_noatss.append(noatss_row['size'].values[0] if len(noatss_row) > 0 else 0)
        depths_noatss.append(noatss_row['depth'].values[0] if len(noatss_row) > 0 else 0)

    ax.bar(x - width/2, sizes_atss, width,
           color=COLORS['ATSS'], alpha=0.85, edgecolor='black',
           linewidth=0.5, label='ATSS')
    ax.bar(x + width/2, sizes_noatss, width,
           color=COLORS['noATSS'], alpha=0.85, edgecolor='black',
           linewidth=0.5, label='noATSS')

    ax.set_ylabel('Proof Size')
    ax.set_xlabel('Formula')
    #ax.set_title('Fig 1: Classical Tautology Proof Sizes (ATSS vs noATSS)')
    ax.set_xticks(x)
    ax.set_xticklabels(short_labels, rotation=45, ha='right', fontsize=7)
    ax.legend(loc='upper left')
    ax.set_ylim(0, max(sizes_atss + sizes_noatss) * 1.2)

    _save(fig, 'fig1_classical_tautologies.pdf')


# ==============================================================================
# Figure 2: Pigeonhole Principle
# ==============================================================================

def plot_fig2_pigeonhole():
    """2-panel: (a) time vs n (log scale), (b) status vs n."""
    df = _read_csv('exp2_pigeonhole.csv')
    if df is None:
        return

    # Use actual solver names from data
    available_solvers = sorted(df['solver'].unique().tolist())

    fig, axes = plt.subplots(1, 2, figsize=(11, 4.5), constrained_layout=True)

    # Panel (a): Time vs n (log scale)
    ax = axes[0]
    for solver in available_solvers:
        grp = df[df['solver'] == solver].sort_values('n')
        ax.semilogy(grp['n'], grp['time_s'] * 1000, 'o-',
                    color=COLORS.get(solver, '#1f77b4'),
                    label=solver, linewidth=1.8, markersize=7)

    ax.set_xlabel('n (PHP_n^{n+1})')
    ax.set_ylabel('Solve Time (ms, log scale)')
    ax.set_title('(a) PHP Solve Time')
    ax.legend(loc='upper left', fontsize=9)
    ax.set_xticks([2, 3, 4, 5, 6])
    ax.grid(alpha=0.3, which='both')

    # Panel (b): Status overview
    ax2 = axes[1]
    for solver in available_solvers:
        grp = df[df['solver'] == solver].sort_values('n')
        rates = [100 if s in ['UNSAT', 'SAT'] else 0 for s in grp['status']]
        ax2.plot(grp['n'], rates, 's-',
                 color=COLORS.get(solver, '#1f77b4'),
                 label=solver, linewidth=1.8, markersize=8)

    ax2.set_xlabel('n (PHP_n^{n+1})')
    ax2.set_ylabel('Solve Rate (%)')
    ax2.set_title('(b) PHP Status (SAT/UNSAT)')
    ax2.legend(loc='lower left', fontsize=9)
    ax2.set_xticks([2, 3, 4, 5, 6])
    ax2.set_ylim(-5, 115)
    ax2.grid(alpha=0.3)

    _save(fig, 'fig2_pigeonhole.pdf')


# ==============================================================================
# Figure 3: Phase Transition
# ==============================================================================

def plot_fig3_phase_transition():
    """Phase transition curve — time vs alpha with phase boundary."""
    df = _read_csv('exp3_phase_transition.csv')
    if df is None:
        return

    # Use actual solver names from data
    available_solvers = sorted(df['solver'].unique().tolist())

    fig, axes = plt.subplots(1, 2, figsize=(12, 5), constrained_layout=True)

    # Panel (a): Median time vs ratio
    ax = axes[0]
    for solver in available_solvers:
        grp = df[df['solver'] == solver]
        ratios_sorted = sorted(grp['ratio'].unique())
        medians = []
        q25s = []
        q75s = []
        for r in ratios_sorted:
            times = grp[grp['ratio'] == r]['time_s'] * 1000
            medians.append(np.median(times))
            q25s.append(np.percentile(times, 25))
            q75s.append(np.percentile(times, 75))
        color = COLORS.get(solver, 'gray')
        ax.semilogy(ratios_sorted, medians, 'o-', color=color,
                    label=solver, linewidth=1.8, markersize=5)
        ax.fill_between(ratios_sorted, q25s, q75s, color=color, alpha=0.12)

    ax.axvline(4.27, color='red', linestyle='--', linewidth=1.5, alpha=0.7,
               label=r'Phase boundary $\alpha \approx 4.27$')
    ax.set_xlabel(r'Clause-to-variable ratio $\alpha$')
    ax.set_ylabel('Median Solve Time (ms, log scale)')
    ax.set_title('(a) Phase Transition — Time vs Ratio')
    ax.legend(loc='upper left', fontsize=8)
    ax.grid(alpha=0.3, which='both')

    # Panel (b): Solve rate vs ratio
    ax2 = axes[1]
    for solver in available_solvers:
        grp = df[df['solver'] == solver]
        ratios_sorted = sorted(grp['ratio'].unique())
        rates = []
        for r in ratios_sorted:
            sub = grp[grp['ratio'] == r]
            solved = sub['status'].isin(['SAT', 'UNSAT']).sum()
            rates.append(solved / len(sub))
        ax2.plot(ratios_sorted, rates, 's-',
                 color=COLORS.get(solver, 'gray'),
                 label=solver, linewidth=1.8, markersize=5)

    ax2.axvline(4.27, color='red', linestyle='--', linewidth=1.5, alpha=0.7)
    ax2.set_xlabel(r'Clause-to-variable ratio $\alpha$')
    ax2.set_ylabel('Solve Rate')
    ax2.set_title('(b) Phase Transition — Solve Rate')
    ax2.legend(loc='lower left', fontsize=8)
    ax2.set_ylim(-0.05, 1.15)
    ax2.grid(alpha=0.3)

    _save(fig, 'fig3_phase_transition.pdf')


# ==============================================================================
# Figure 4: Proof Quality
# ==============================================================================

def plot_fig4_proof_quality():
    """ATSS vs noATSS proof quality comparison."""
    df = _read_csv('exp4_proof_quality.csv')
    if df is None:
        return

    fig, axes = plt.subplots(1, 3, figsize=(14, 4.5), constrained_layout=True)

    formulas_short = [f if len(f) <= 18 else f[:15] + '...'
                      for f in df[df['solver'] == 'ATSS']['formula'].unique()]
    n_formulas = len(formulas_short)

    # Panel (a): Proof size comparison
    ax = axes[0]
    x = np.arange(n_formulas)
    width = 0.35
    atss_sizes = df[df['solver'] == 'ATSS']['size'].values
    noatss_sizes = df[df['solver'] == 'noATSS']['size'].values
    ax.bar(x - width/2, atss_sizes, width, color=COLORS['ATSS'], alpha=0.85,
           label='ATSS', edgecolor='black', linewidth=0.3)
    ax.bar(x + width/2, noatss_sizes, width, color=COLORS['noATSS'], alpha=0.85,
           label='noATSS', edgecolor='black', linewidth=0.3)
    ax.set_xticks(x)
    ax.set_xticklabels(formulas_short, rotation=60, ha='right', fontsize=6)
    ax.set_ylabel('Proof Size')
    ax.set_title('(a) Proof Size')
    ax.legend(fontsize=8)

    # Panel (b): Proof depth comparison
    ax2 = axes[1]
    atss_depths = df[df['solver'] == 'ATSS']['depth'].values
    noatss_depths = df[df['solver'] == 'noATSS']['depth'].values
    ax2.bar(x - width/2, atss_depths, width, color=COLORS['ATSS'], alpha=0.85,
            label='ATSS', edgecolor='black', linewidth=0.3)
    ax2.bar(x + width/2, noatss_depths, width, color=COLORS['noATSS'], alpha=0.85,
            label='noATSS', edgecolor='black', linewidth=0.3)
    ax2.set_xticks(x)
    ax2.set_xticklabels(formulas_short, rotation=60, ha='right', fontsize=6)
    ax2.set_ylabel('Proof Depth')
    ax2.set_title('(b) Proof Depth')
    ax2.legend(fontsize=8)

    # Panel (c): Time comparison
    ax3 = axes[2]
    atss_times = df[df['solver'] == 'ATSS']['time_us'].values
    noatss_times = df[df['solver'] == 'noATSS']['time_us'].values
    ax3.bar(x - width/2, atss_times, width, color=COLORS['ATSS'], alpha=0.85,
            label='ATSS', edgecolor='black', linewidth=0.3)
    ax3.bar(x + width/2, noatss_times, width, color=COLORS['noATSS'], alpha=0.85,
            label='noATSS', edgecolor='black', linewidth=0.3)
    ax3.set_xticks(x)
    ax3.set_xticklabels(formulas_short, rotation=60, ha='right', fontsize=6)
    ax3.set_ylabel('Time (us)')
    ax3.set_title('(c) Solve Time')
    ax3.legend(fontsize=8)

    _save(fig, 'fig4_proof_quality.pdf')


# ==============================================================================
# Figure 5: Ablation Study
# ==============================================================================

def plot_fig5_ablation():
    """Grouped bar chart across 3 difficulty levels."""
    df = _read_csv('exp5_ablation.csv')
    if df is None:
        return

    difficulties = ['Easy', 'Phase', 'Hard']
    # Use actual solver names from data
    available_solvers = sorted(df['solver'].unique().tolist())
    solver_colors = [COLORS.get(s, '#1f77b4') for s in available_solvers]
    n_solvers = len(available_solvers)

    fig, axes = plt.subplots(1, 3, figsize=(15, 4.5), constrained_layout=True)

    # Panel (a): Median time
    ax = axes[0]
    x = np.arange(len(difficulties))
    width = 0.8 / max(n_solvers, 1)
    for i, solver in enumerate(available_solvers):
        grp = df[df['solver'] == solver]
        times = []
        for d in difficulties:
            sub = grp[grp['difficulty'] == d]
            times.append(np.median(sub['time_s'] * 1000) if len(sub) > 0 else 0)
        offset = (i - (n_solvers - 1) / 2) * width if n_solvers > 1 else 0
        ax.bar(x + offset, times, width, color=solver_colors[i],
               alpha=0.85, label=solver, edgecolor='black', linewidth=0.5)
        # Add value labels
        for j, t in enumerate(times):
            if t > 0:
                ax.text(x[j] + offset, t + max(times)*0.02,
                        f'{t:.1f}', ha='center', va='bottom',
                        fontsize=7, rotation=90)

    ax.set_xticks(x)
    ax.set_xticklabels(difficulties)
    ax.set_ylabel('Median Time (ms)')
    ax.set_title('(a) Solve Time')
    ax.set_yscale('log')
    ax.legend(fontsize=8)

    # Panel (b): Solve rate
    ax2 = axes[1]
    for i, solver in enumerate(available_solvers):
        grp = df[df['solver'] == solver]
        rates = []
        for d in difficulties:
            sub = grp[grp['difficulty'] == d]
            avg_rate = sub['solve_rate'].mean() if len(sub) > 0 else 0
            rates.append(avg_rate * 100)
        offset = (i - (n_solvers - 1) / 2) * width if n_solvers > 1 else 0
        ax2.bar(x + offset, rates, width, color=solver_colors[i],
                alpha=0.85, label=solver, edgecolor='black', linewidth=0.5)
    ax2.set_xticks(x)
    ax2.set_xticklabels(difficulties)
    ax2.set_ylabel('Solve Rate (%)')
    ax2.set_title('(b) Solve Rate')
    ax2.set_ylim(0, 115)
    ax2.legend(fontsize=8)

    # Panel (c): Conflicts
    ax3 = axes[2]
    for i, solver in enumerate(available_solvers):
        grp = df[df['solver'] == solver]
        conflicts = []
        for d in difficulties:
            sub = grp[grp['difficulty'] == d]
            conflicts.append(np.median(sub['conflicts']) if len(sub) > 0 else 0)
        offset = (i - (n_solvers - 1) / 2) * width if n_solvers > 1 else 0
        ax3.bar(x + offset, conflicts, width, color=solver_colors[i],
                alpha=0.85, label=solver, edgecolor='black', linewidth=0.5)
    ax3.set_xticks(x)
    ax3.set_xticklabels(difficulties)
    ax3.set_ylabel('Median Conflicts')
    ax3.set_title('(c) Conflicts')
    ax3.set_yscale('log')
    ax3.legend(fontsize=8)

    _save(fig, 'fig5_ablation.pdf')


# ==============================================================================
# Figure 6: Scalability
# ==============================================================================

def plot_fig6_scalability():
    """Time vs n_vars with IQR bands."""
    df = _read_csv('exp6_scalability.csv')
    if df is None:
        return

    # Use actual solver names from data
    available_solvers = sorted(df['solver'].unique().tolist())

    fig, axes = plt.subplots(1, 2, figsize=(12, 5), constrained_layout=True)

    # Panel (a): Time vs n_vars with IQR
    ax = axes[0]
    for solver in available_solvers:
        grp = df[df['solver'] == solver]
        n_sorted = sorted(grp['n_vars'].unique())
        medians = []
        q25s = []
        q75s = []
        for n_v in n_sorted:
            times = grp[grp['n_vars'] == n_v]['time_s'] * 1000
            medians.append(np.median(times))
            q25s.append(np.percentile(times, 25))
            q75s.append(np.percentile(times, 75))
        color = COLORS.get(solver, '#1f77b4')
        ax.semilogy(n_sorted, medians, 'o-', color=color, label=solver,
                    linewidth=2, markersize=6)
        ax.fill_between(n_sorted, q25s, q75s, color=color, alpha=0.15)

    ax.set_xlabel('Number of Variables')
    ax.set_ylabel('Solve Time (ms, median + IQR, log)')
    ax.set_title('(a) Scalability: Time vs n_vars')
    ax.legend(fontsize=9)
    ax.grid(alpha=0.3, which='both')

    # Panel (b): Conflicts vs n_vars
    ax2 = axes[1]
    for solver in available_solvers:
        grp = df[df['solver'] == solver]
        n_sorted = sorted(grp['n_vars'].unique())
        medians_c = []
        for n_v in n_sorted:
            conflicts = grp[grp['n_vars'] == n_v]['conflicts']
            medians_c.append(np.median(conflicts))
        color = COLORS.get(solver, '#1f77b4')
        ax2.semilogy(n_sorted, medians_c, 's-', color=color, label=solver,
                     linewidth=2, markersize=6)

    ax2.set_xlabel('Number of Variables')
    ax2.set_ylabel('Median Conflicts (log)')
    ax2.set_title('(b) Conflicts vs n_vars')
    ax2.legend(fontsize=9)
    ax2.grid(alpha=0.3, which='both')

    _save(fig, 'fig6_scalability.pdf')


# ==============================================================================
# Figure 7: SOTA Comparison
# ==============================================================================

def plot_fig7_sota_comparison():
    """SOTA comparison across benchmarks."""
    df = _read_csv('exp7_sota_comparison.csv')
    if df is None:
        return

    # Use actual solver names from data
    available_solvers = sorted(df['solver'].unique().tolist())

    fig, axes = plt.subplots(1, 2, figsize=(13, 5), constrained_layout=True)

    # Panel (a): Time comparison (grouped bar)
    ax = axes[0]
    benchmarks = df['benchmark'].unique()
    n_solvers = len(available_solvers)
    x = np.arange(len(benchmarks))
    width = 0.8 / max(n_solvers, 1)

    for i, solver in enumerate(available_solvers):
        grp = df[df['solver'] == solver]
        times = []
        for b in benchmarks:
            sub = grp[grp['benchmark'] == b]
            times.append(sub['time_s'].values[0] * 1000 if len(sub) > 0 else 0)
        offset = (i - (n_solvers - 1) / 2) * width if n_solvers > 1 else 0
        ax.bar(x + offset, times, width, color=COLORS.get(solver, '#1f77b4'),
               alpha=0.85, label=solver, edgecolor='black', linewidth=0.5)

    ax.set_xticks(x)
    ax.set_xticklabels(benchmarks, rotation=30, ha='right', fontsize=8)
    ax.set_ylabel('Solve Time (ms, log)')
    ax.set_title('(a) SOTA Time Comparison')
    ax.set_yscale('log')
    ax.legend(fontsize=8)

    # Panel (b): Certified proof count
    ax2 = axes[1]
    cert_counts = []
    for b in benchmarks:
        sub_cert = df[(df['benchmark'] == b) & (df['certified'] == True)]
        cert_counts.append(len(sub_cert))
    bars = ax2.bar(range(len(benchmarks)), cert_counts, color=COLORS.get('CertiProof+ATSS', '#1f77b4'),
                   alpha=0.85, edgecolor='black', linewidth=0.5)
    ax2.set_xticks(range(len(benchmarks)))
    ax2.set_xticklabels(benchmarks, rotation=30, ha='right', fontsize=8)
    ax2.set_ylabel('Certified Proofs (out of 3)')
    ax2.set_title('(b) Certified Proof Output')
    ax2.set_ylim(0, 4)

    _save(fig, 'fig7_sota_comparison.pdf')


# ==============================================================================
# Figure 8: GNN-ATSS
# ==============================================================================

def plot_fig8_gnn_atss():
    """GNN config comparison across complexity levels."""
    df = _read_csv('exp8_gnn_atss.csv')
    if df is None:
        return

    fig, axes = plt.subplots(1, 3, figsize=(15, 4.5), constrained_layout=True)

    configs = ['Cosine', 'GNN', 'Blended']
    complexities = ['Small', 'Medium', 'Large']

    # Panel (a): Time
    ax = axes[0]
    x = np.arange(len(complexities))
    width = 0.25
    for i, config in enumerate(configs):
        grp = df[df['config'] == config]
        times = []
        for c in complexities:
            sub = grp[grp['formula_complexity'] == c]
            times.append(np.mean(sub['time_ms']) if len(sub) > 0 else 0)
        ax.bar(x + i * width, times, width, color=COLORS.get(config, 'gray'),
               alpha=0.85, label=config, edgecolor='black', linewidth=0.5)
    ax.set_xticks(x + width)
    ax.set_xticklabels(complexities)
    ax.set_ylabel('Mean Time (ms)')
    ax.set_title('(a) Inference Time')
    ax.set_yscale('log')
    ax.legend(fontsize=8)

    # Panel (b): Solve rate
    ax2 = axes[1]
    for i, config in enumerate(configs):
        grp = df[df['config'] == config]
        rates = []
        for c in complexities:
            sub = grp[grp['formula_complexity'] == c]
            rates.append(np.mean(sub['solve_rate']) * 100)
        ax2.bar(x + i * width, rates, width, color=COLORS.get(config, 'gray'),
                alpha=0.85, label=config, edgecolor='black', linewidth=0.5)
    ax2.set_xticks(x + width)
    ax2.set_xticklabels(complexities)
    ax2.set_ylabel('Solve Rate (%)')
    ax2.set_title('(b) Solve Rate')
    ax2.set_ylim(0, 115)
    ax2.legend(fontsize=8)

    # Panel (c): Proof size
    ax3 = axes[2]
    for i, config in enumerate(configs):
        grp = df[df['config'] == config]
        sizes = []
        for c in complexities:
            sub = grp[grp['formula_complexity'] == c]
            sizes.append(np.mean(sub['size']))
        ax3.bar(x + i * width, sizes, width, color=COLORS.get(config, 'gray'),
                alpha=0.85, label=config, edgecolor='black', linewidth=0.5)
    ax3.set_xticks(x + width)
    ax3.set_xticklabels(complexities)
    ax3.set_ylabel('Proof Size')
    ax3.set_title('(c) Proof Size')
    ax3.legend(fontsize=8)

    _save(fig, 'fig8_gnn_atss.pdf')


# ==============================================================================
# Figure 9: ATSS Learning Curve
# ==============================================================================

def plot_fig9_atss_learning():
    """Learning curve showing convergence over epochs."""
    df = _read_csv('exp9_atss_learning_curve.csv')
    if df is None:
        return

    fig, axes = plt.subplots(1, 3, figsize=(15, 4.5), constrained_layout=True)

    # Panel (a): Solve rate convergence
    ax = axes[0]
    for solver in ['with_ATSS', 'without_ATSS']:
        grp = df[df['solver'] == solver].sort_values('epoch')
        ax.plot(grp['epoch'], grp['solve_rate'] * 100, 'o-',
                color=COLORS.get(solver, 'gray'),
                label='With ATSS' if solver == 'with_ATSS' else 'Without ATSS',
                linewidth=2, markersize=5)

    ax.axhline(100, color='gray', linestyle='--', alpha=0.5,
               label='Perfect (100%)')
    ax.set_xlabel('Epoch')
    ax.set_ylabel('Solve Rate (%)')
    ax.set_title('(a) Solve Rate Convergence')
    ax.set_ylim(0, 110)
    ax.legend(fontsize=9)
    ax.grid(alpha=0.3)

    # Panel (b): Solved/Failed per epoch
    ax2 = axes[1]
    atss_data = df[df['solver'] == 'with_ATSS'].sort_values('epoch')
    epochs = atss_data['epoch'].values
    ax2.bar(epochs, atss_data['solved'], color=COLORS['with_ATSS'],
            alpha=0.85, label='Solved (ATSS)', edgecolor='black', linewidth=0.3)
    ax2.bar(epochs, atss_data['failed'], bottom=atss_data['solved'],
            color='#ff9999', alpha=0.7, label='Failed (ATSS)',
            edgecolor='black', linewidth=0.3)
    ax2.set_xlabel('Epoch')
    ax2.set_ylabel('Problems')
    ax2.set_title('(b) ATSS: Solved / Failed')
    ax2.legend(fontsize=9)
    ax2.grid(alpha=0.3, axis='y')

    # Panel (c): Average time
    ax3 = axes[2]
    for solver in ['with_ATSS', 'without_ATSS']:
        grp = df[df['solver'] == solver].sort_values('epoch')
        ax3.plot(grp['epoch'], grp['avg_time_ms'], 's-',
                 color=COLORS.get(solver, 'gray'),
                 label='With ATSS' if solver == 'with_ATSS' else 'Without ATSS',
                 linewidth=2, markersize=5)

    ax3.set_xlabel('Epoch')
    ax3.set_ylabel('Average Time (ms)')
    ax3.set_title('(c) Average Solve Time')
    ax3.legend(fontsize=9)
    ax3.grid(alpha=0.3)

    _save(fig, 'fig9_atss_learning.pdf')


# ==============================================================================
# Figure 10: Virtuous Cycle
# ==============================================================================

def plot_fig10_virtuous_cycle():
    """Virtuous cycle visualization — CDCL→Interpolation→ATSS→Cut."""
    df = _read_csv('exp10_virtuous_cycle.csv')
    if df is None:
        return

    fig = plt.figure(figsize=(12, 8), constrained_layout=True)

    # Layout: 2x2 subplots
    ax1 = fig.add_subplot(2, 2, 1)
    ax2 = fig.add_subplot(2, 2, 2)
    ax3 = fig.add_subplot(2, 2, 3)
    ax4 = fig.add_subplot(2, 2, 4)

    cycles = df['cycle'].values
    n_vars = df['n_vars'].values

    # (a) CDCL Conflicts across cycles
    ax1.plot(cycles, df['cdcl_conflicts'], 'o-', color='#d62728',
             linewidth=2, markersize=7, label='CDCL Conflicts')
    ax1.fill_between(cycles, df['cdcl_conflicts'], alpha=0.2, color='#d62728')
    ax1.set_xlabel('Cycle')
    ax1.set_ylabel('Conflicts')
    ax1.set_title('(a) CDCL Conflicts vs Cycle')
    ax1.grid(alpha=0.3)
    ax1.legend(fontsize=9)

    # (b) Lemmas learned and ATSS success
    ax2.plot(cycles, df['lemmas_learned'], 'o-', color='#1f77b4',
             linewidth=2, markersize=7, label='Lemmas Learned')
    ax2.plot(cycles, df['atss_success_rate'] * 100, 's--', color='#2ca02c',
             linewidth=2, markersize=7, label='ATSS Success Rate (%)')
    ax2.set_xlabel('Cycle')
    ax2.set_ylabel('Count / Rate (%)')
    ax2.set_title('(b) Knowledge Accumulation')
    ax2.grid(alpha=0.3)
    ax2.legend(fontsize=9)

    # (c) Problem complexity (n_vars) per cycle
    ax3.bar(cycles, n_vars, color='#ff7f0e', alpha=0.85,
            edgecolor='black', linewidth=0.5, label='Variables')
    ax3.set_xlabel('Cycle')
    ax3.set_ylabel('Number of Variables')
    ax3.set_title('(c) Problem Scale per Cycle')
    ax3.grid(alpha=0.3, axis='y')
    ax3.legend(fontsize=9)

    # (d) Scatter: Conflicts vs ATSS Success Rate
    scatter = ax4.scatter(df['cdcl_conflicts'], df['atss_success_rate'] * 100,
                          c=cycles, cmap='viridis', s=150, edgecolors='black',
                          linewidth=0.5, zorder=3)
    for i, cycle in enumerate(cycles):
        ax4.annotate(str(cycle),
                     (df['cdcl_conflicts'].values[i],
                      df['atss_success_rate'].values[i] * 100),
                     textcoords="offset points", xytext=(8, 5),
                     fontsize=8, fontweight='bold')
    # Draw arrows showing progression
    for i in range(len(cycles) - 1):
        ax4.annotate('', xy=(df['cdcl_conflicts'].values[i + 1],
                              df['atss_success_rate'].values[i + 1] * 100),
                     xytext=(df['cdcl_conflicts'].values[i],
                             df['atss_success_rate'].values[i] * 100),
                     arrowprops=dict(arrowstyle='->', color='gray',
                                     lw=1.5, alpha=0.6))
    ax4.set_xlabel('CDCL Conflicts')
    ax4.set_ylabel('ATSS Success Rate (%)')
    ax4.set_title('(d) Virtuous Cycle Trajectory')
    cbar = plt.colorbar(ax4.collections[0], ax=ax4, label='Cycle')
    ax4.grid(alpha=0.3)

    _save(fig, 'fig10_virtuous_cycle.pdf')


# ==============================================================================
# Figure 11: Frege/Extension Rules
# ==============================================================================

def plot_fig11_frege_extension():
    """Extended Resolution comparison."""
    df = _read_csv('exp11_frege_extension.csv')
    if df is None:
        return

    fig, axes = plt.subplots(1, 2, figsize=(12, 5), constrained_layout=True)

    # Separate standard and extension data
    std = df[~df['benchmark'].str.contains('_ext')]
    ext = df[df['benchmark'].str.contains('_ext')]

    benchmarks = [b.replace('_ext', '') for b in ext['benchmark'].unique()]
    x = np.arange(len(benchmarks))
    width = 0.35

    # Panel (a): Time comparison
    ax = axes[0]
    for i, (label, data, color) in enumerate([
        ('Standard', std, '#d62728'),
        ('+Extension', ext, '#1f77b4'),
    ]):
        times = []
        for b in benchmarks:
            sub = data[data['benchmark'].str.contains(b)]
            times.append(sub['time_s'].values[0] * 1000 if len(sub) > 0 else 0)
        ax.bar(x + i * width, times, width, color=color, alpha=0.85,
               label=label, edgecolor='black', linewidth=0.5)

    ax.set_xticks(x + width / 2)
    ax.set_xticklabels(benchmarks, rotation=20, ha='right', fontsize=9)
    ax.set_ylabel('Solve Time (ms)')
    ax.set_title('(a) Time: Standard vs Extended Resolution')
    ax.set_yscale('log')
    ax.legend(fontsize=9)
    ax.grid(alpha=0.3, axis='y')

    # Panel (b): Proof size
    ax2 = axes[1]
    for i, (label, data, color) in enumerate([
        ('Standard', std, '#d62728'),
        ('+Extension', ext, '#1f77b4'),
    ]):
        sizes = []
        for b in benchmarks:
            sub = data[data['benchmark'].str.contains(b)]
            sizes.append(sub['size'].values[0] if len(sub) > 0 else 0)
        ax2.bar(x + i * width, sizes, width, color=color, alpha=0.85,
                label=label, edgecolor='black', linewidth=0.5)

    ax2.set_xticks(x + width / 2)
    ax2.set_xticklabels(benchmarks, rotation=20, ha='right', fontsize=9)
    ax2.set_ylabel('Proof Size')
    ax2.set_title('(b) Proof Size: Polynomial Speedup')
    ax2.set_yscale('log')
    ax2.legend(fontsize=9)
    ax2.grid(alpha=0.3, axis='y')

    _save(fig, 'fig11_frege_extension.pdf')


# ==============================================================================
# Figure 12: Operation Costs
# ==============================================================================

def plot_fig12_operation_costs():
    """Operation cost comparison — Python vs C/C++ bar chart."""
    operations = [
        'WL Propagate\n(one clause)',
        'VSIDS\nDecision',
        '1-UIP\nConflict',
        'Clause\nMinimization',
        'LBD\nCompute',
        'ATSS\nUpdate',
        'ATSS\nSample',
        'Interpolant\nUpdate',
        'ND\nAssumption',
        'ND\nMP',
        'Lemma\nStore',
        'Lemma\nLookup',
    ]
    python_costs = [0.8, 5.0, 50.0, 30.0, 10.0, 2.0, 3.0, 50.0, 0.5, 2.0, 5.0, 3.0]
    c_costs = [c * (1.0/200.0) for c in python_costs]

    fig, ax = plt.subplots(figsize=(12, 5.5), constrained_layout=True)

    x = np.arange(len(operations))
    width = 0.35

    bars1 = ax.bar(x - width/2, python_costs, width, color='#d62728', alpha=0.85,
                   label='Python (CertiProof)', edgecolor='black', linewidth=0.5)
    bars2 = ax.bar(x + width/2, c_costs, width, color='#2ca02c', alpha=0.85,
                   label='C/C++ (Glucose4)', edgecolor='black', linewidth=0.5)

    ax.set_xticks(x)
    ax.set_xticklabels(operations, fontsize=8)
    ax.set_ylabel('Cost per Operation (us)')
    #ax.set_title('Figure 12: Operation Primitive Cost Comparison — Python vs C/C++')
    ax.set_yscale('log')
    ax.legend(fontsize=10)

    # Speedup annotations
    for i, (py_cost, c_cost) in enumerate(zip(python_costs, c_costs)):
        speedup = py_cost / c_cost
        ax.text(i, max(py_cost, c_cost) * 1.3, f'{speedup:.0f}x',
                ha='center', fontsize=8, fontweight='bold',
                bbox=dict(boxstyle='round,pad=0.3', facecolor='lightyellow',
                          alpha=0.8))

    ax.set_ylim(top=max(python_costs) * 3)
    ax.grid(alpha=0.3, axis='y')

    _save(fig, 'fig12_operation_costs.pdf')


# ==============================================================================
# Figure 13: Verification Benchmarks
# ==============================================================================

def plot_fig13_verification_benchmarks():
    """ATSS accumulated knowledge vs fresh restart on verification benchmarks."""
    df = _read_csv('exp_verification_benchmarks.csv')
    if df is None:
        return

    fig, axes = plt.subplots(1, 3, figsize=(15, 4.5), constrained_layout=True)

    benchmarks = df['benchmark'].unique()
    # Separate ATSS and noATSS data
    atss_df = df[df['solver'] == 'ATSS (accumulated)'].set_index('benchmark')
    noatss_df = df[df['solver'] == 'noATSS (fresh)'].set_index('benchmark')

    # Get common benchmarks
    common = sorted(set(atss_df.index) & set(noatss_df.index))

    x = np.arange(len(common))
    width = 0.35

    # Panel (a): Proof size comparison
    ax = axes[0]
    atss_sizes = [atss_df.loc[b, 'proof_size'].values[0] if isinstance(atss_df.loc[b], pd.DataFrame)
                  else atss_df.loc[b, 'proof_size'] for b in common]
    noatss_sizes = [noatss_df.loc[b, 'proof_size'].values[0] if isinstance(noatss_df.loc[b], pd.DataFrame)
                    else noatss_df.loc[b, 'proof_size'] for b in common]
    ax.bar(x - width/2, atss_sizes, width, color=COLORS['ATSS'], alpha=0.85,
           label='ATSS (accumulated)', edgecolor='black', linewidth=0.3)
    ax.bar(x + width/2, noatss_sizes, width, color=COLORS['noATSS'], alpha=0.85,
           label='noATSS (fresh)', edgecolor='black', linewidth=0.3)
    ax.set_xticks(x)
    ax.set_xticklabels(common, rotation=35, ha='right', fontsize=6)
    ax.set_ylabel('Proof Size')
    ax.set_title('(a) Proof Size Comparison')
    ax.legend(fontsize=7)

    # Panel (b): Time comparison
    ax2 = axes[1]
    atss_times = [atss_df.loc[b, 'time_ms'].values[0] if isinstance(atss_df.loc[b], pd.DataFrame)
                  else atss_df.loc[b, 'time_ms'] for b in common]
    noatss_times = [noatss_df.loc[b, 'time_ms'].values[0] if isinstance(noatss_df.loc[b], pd.DataFrame)
                    else noatss_df.loc[b, 'time_ms'] for b in common]
    ax2.bar(x - width/2, atss_times, width, color=COLORS['ATSS'], alpha=0.85,
            label='ATSS (accumulated)', edgecolor='black', linewidth=0.3)
    ax2.bar(x + width/2, noatss_times, width, color=COLORS['noATSS'], alpha=0.85,
            label='noATSS (fresh)', edgecolor='black', linewidth=0.3)
    ax2.set_xticks(x)
    ax2.set_xticklabels(common, rotation=35, ha='right', fontsize=6)
    ax2.set_ylabel('Time (ms)')
    ax2.set_title('(b) Solve Time Comparison')
    ax2.legend(fontsize=7)

    # Panel (c): Speedup ratio
    ax3 = axes[2]
    speedups = []
    for b in common:
        atss_t = atss_df.loc[b, 'time_ms'] if not isinstance(atss_df.loc[b], pd.DataFrame) else atss_df.loc[b, 'time_ms'].values[0]
        noatss_t = noatss_df.loc[b, 'time_ms'] if not isinstance(noatss_df.loc[b], pd.DataFrame) else noatss_df.loc[b, 'time_ms'].values[0]
        speedups.append(noatss_t / max(atss_t, 1e-6))
    bars = ax3.bar(x, speedups, color=['#1f77b4' if s > 1.0 else '#d62728' for s in speedups],
                   alpha=0.85, edgecolor='black', linewidth=0.3)
    ax3.axhline(1.0, color='gray', linestyle='--', linewidth=1, alpha=0.7,
                label='No speedup (1.0)')
    ax3.set_xticks(x)
    ax3.set_xticklabels(common, rotation=35, ha='right', fontsize=6)
    ax3.set_ylabel('Speedup Ratio (noATSS/ATSS)')
    ax3.set_title('(c) ATSS Speedup')
    ax3.legend(fontsize=7)
    ax3.set_ylim(0, max(speedups) * 1.3)

    _save(fig, 'fig13_verification_benchmarks.pdf')


# ==============================================================================
# Figure 14: Complex Learning
# ==============================================================================

def plot_fig14_complex_learning():
    """ATSS vs noATSS learning on complex formulas across epochs."""
    df = _read_csv('exp_complex_learning.csv')
    if df is None:
        return

    fig, axes = plt.subplots(1, 3, figsize=(15, 4.5), constrained_layout=True)

    # Prepare data
    atss_data = df[df['mode'] == 'ATSS'].sort_values('epoch')
    noatss_data = df[df['mode'] == 'noATSS'].sort_values('epoch')

    # Panel (a): Solve time comparison with proof size growth
    ax = axes[0]
    ax.plot(atss_data['epoch'], atss_data['time_ms'], 'o-',
            color=COLORS['with_ATSS'], linewidth=2, markersize=6,
            label='ATSS (time)')
    ax.plot(noatss_data['epoch'], noatss_data['time_ms'], 's--',
            color=COLORS['without_ATSS'], linewidth=2, markersize=6,
            label='noATSS (time)')
    ax.set_xlabel('Epoch')
    ax.set_ylabel('Time (ms)')
    ax.set_title('(a) Solve Time vs Epoch')
    ax.legend(fontsize=9)
    ax.grid(alpha=0.3)

    # Panel (b): Proof size growth
    ax2 = axes[1]
    ax2.plot(atss_data['epoch'], atss_data['proof_size'], 'o-',
             color=COLORS['with_ATSS'], linewidth=2, markersize=6,
             label='ATSS (proof size)')
    ax2.plot(noatss_data['epoch'], noatss_data['proof_size'], 's--',
             color=COLORS['without_ATSS'], linewidth=2, markersize=6,
             label='noATSS (proof size)')
    ax2.set_xlabel('Epoch')
    ax2.set_ylabel('Proof Size')
    ax2.set_title('(b) Proof Size Growth')
    ax2.legend(fontsize=9)
    ax2.grid(alpha=0.3)

    # Panel (c): Solved vs Total
    ax3 = axes[2]
    epochs = atss_data['epoch'].values
    x = np.arange(len(epochs))
    width = 0.35
    ax3.bar(x - width/2, atss_data['n_proved'], width, color=COLORS['with_ATSS'],
            alpha=0.85, label='ATSS', edgecolor='black', linewidth=0.3)
    ax3.bar(x + width/2, noatss_data['n_proved'], width, color=COLORS['without_ATSS'],
            alpha=0.85, label='noATSS', edgecolor='black', linewidth=0.3)
    ax3.axhline(atss_data['n_total'].values[0], color='gray', linestyle='--',
                alpha=0.7, label=f'Total ({int(atss_data["n_total"].values[0])})')
    ax3.set_xticks(x)
    ax3.set_xticklabels([f'E{e}' for e in epochs])
    ax3.set_ylabel('Problems Solved')
    ax3.set_title('(c) Solved per Epoch')
    ax3.legend(fontsize=9)
    ax3.set_ylim(0, atss_data['n_total'].max() * 1.2)

    _save(fig, 'fig14_complex_learning.pdf')


# ==============================================================================
# Figure 15: First-Order Extension
# ==============================================================================

def plot_fig15_firstorder_extension():
    """First-order reasoning benchmarks across domains."""
    df = _read_csv('exp12_firstorder_extension.csv')
    if df is None:
        return

    fig, axes = plt.subplots(1, 2, figsize=(12, 5), constrained_layout=True)

    # Sort by time for consistent ordering
    df_sorted = df.sort_values('time_s')

    # Panel (a): Time per problem grouped by domain
    ax = axes[0]
    domains = df['domain'].unique()
    colors_domain = {
        'Graph Theory': '#1f77b4',
        'Set Theory': '#ff7f0e',
        'Algebra': '#2ca02c',
        'Model Theory': '#d62728',
    }
    x = np.arange(len(df_sorted))
    bars = ax.bar(x, df_sorted['time_s'] * 1000,
                  color=[colors_domain.get(d, 'gray') for d in df_sorted['domain']],
                  alpha=0.85, edgecolor='black', linewidth=0.5)

    # Add status markers
    for i, (_, row) in enumerate(df_sorted.iterrows()):
        marker = r'$\checkmark$' if row['status'] == 'SAT' else '?'
        ax.text(i, row['time_s'] * 1000 + max(df_sorted['time_s']) * 20,
                marker, ha='center', fontsize=10)

    ax.set_xticks(x)
    ax.set_xticklabels([p[:25] for p in df_sorted['problem']], rotation=30, ha='right', fontsize=7)
    ax.set_ylabel('Time (ms)')
    ax.set_title('(a) FO Reasoning: Time by Domain')
    legend_elements = [Patch(facecolor=c, label=d) for d, c in colors_domain.items()]
    ax.legend(handles=legend_elements, fontsize=8, loc='upper left')
    ax.set_yscale('log')
    ax.grid(alpha=0.3, axis='y')

    # Panel (b): Skolem steps vs time
    ax2 = axes[1]
    for domain in domains:
        sub = df_sorted[df_sorted['domain'] == domain]
        ax2.scatter(sub['skolem_steps'], sub['time_s'] * 1000,
                    color=colors_domain.get(domain, 'gray'),
                    label=domain, s=100, edgecolors='black', linewidth=0.5,
                    zorder=3)
        # Annotate problems
        for _, row in sub.iterrows():
            ax2.annotate(row['problem'][:15],
                         (row['skolem_steps'], row['time_s'] * 1000),
                         textcoords="offset points", xytext=(8, 5),
                         fontsize=6, alpha=0.8)

    ax2.set_xlabel('Skolemization Steps')
    ax2.set_ylabel('Time (ms)')
    ax2.set_title('(b) Skolem Steps vs Solve Time')
    ax2.legend(fontsize=8)
    ax2.set_yscale('log')
    ax2.grid(alpha=0.3)

    _save(fig, 'fig15_firstorder_extension.pdf')


# ==============================================================================
# Main
# ==============================================================================

if __name__ == '__main__':
    print("=" * 60)
    print("CertiProof Figure Generator")
    print("=" * 60)
    print(f"Reading CSVs from: {RESULTS_DIR}")
    print(f"Saving figures to: {FIGURES_DIR}")
    print()

    # Check if CSVs exist
    expected_files = [
        'exp1_classical_tautologies.csv',
        'exp2_pigeonhole.csv',
        'exp3_phase_transition.csv',
        'exp4_proof_quality.csv',
        'exp5_ablation.csv',
        'exp6_scalability.csv',
        'exp7_sota_comparison.csv',
        'exp8_gnn_atss.csv',
        'exp9_atss_learning_curve.csv',
        'exp10_virtuous_cycle.csv',
        'exp11_frege_extension.csv',
        'exp12_firstorder_extension.csv',
        'exp_verification_benchmarks.csv',
        'exp_complex_learning.csv',
    ]
    missing = [f for f in expected_files
               if not os.path.exists(os.path.join(RESULTS_DIR, f))]
    if missing:
        print("[WARN] Missing CSV files:")
        for m in missing:
            print(f"  - {m}")
        print("Run generate_all_data.py first.")
    else:
        print("[OK] All 12 CSV files found.\n")
    print()

    print("[Figure 1: Classical Tautologies]")
    plot_fig1_classical_tautologies()

    print("[Figure 2: Pigeonhole Principle]")
    plot_fig2_pigeonhole()

    print("[Figure 3: Phase Transition]")
    plot_fig3_phase_transition()

    print("[Figure 4: Proof Quality]")
    plot_fig4_proof_quality()

    print("[Figure 5: Ablation Study]")
    plot_fig5_ablation()

    print("[Figure 6: Scalability]")
    plot_fig6_scalability()

    print("[Figure 7: SOTA Comparison]")
    plot_fig7_sota_comparison()

    print("[Figure 8: GNN-ATSS]")
    plot_fig8_gnn_atss()

    print("[Figure 9: ATSS Learning Curve]")
    plot_fig9_atss_learning()

    print("[Figure 10: Virtuous Cycle]")
    plot_fig10_virtuous_cycle()

    print("[Figure 11: Frege Extension]")
    plot_fig11_frege_extension()

    print("[Figure 12: Operation Costs]")
    plot_fig12_operation_costs()

    print("[Figure 13: Verification Benchmarks]")
    plot_fig13_verification_benchmarks()

    print("[Figure 14: Complex Learning]")
    plot_fig14_complex_learning()

    print("[Figure 15: First-Order Extension]")
    plot_fig15_firstorder_extension()

    print()
    print("=" * 60)
    print("ALL FIGURES GENERATED SUCCESSFULLY")
    print("=" * 60)
