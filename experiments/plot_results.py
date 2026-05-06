"""
plot_results.py
===============
Generate publication-quality plots for the NeuroProof benchmark results.
Requires: matplotlib, numpy, pandas.
"""

from __future__ import annotations
import os
import sys
import pandas as pd
import numpy as np
import matplotlib
matplotlib.use('Agg')   # non-interactive backend for servers
import matplotlib.pyplot as plt
import matplotlib.ticker as ticker
from matplotlib.lines import Line2D


# ── Style settings ────────────────────────────────────────────────────────────
plt.rcParams.update({
    'font.family':       'serif',
    'font.size':         11,
    'axes.labelsize':    12,
    'axes.titlesize':    13,
    'legend.fontsize':   10,
    'xtick.labelsize':   10,
    'ytick.labelsize':   10,
    'figure.dpi':        150,
    'savefig.bbox':      'tight',
    'savefig.dpi':       300,
    'text.usetex':       False,   # set True if LaTeX installed
})

COLORS = {
    'NeuroProof':        '#1f77b4',
    'DPLL-Baseline':     '#ff7f0e',
    'NeuroProof+ATSS':   '#2ca02c',
}
MARKERS = {
    'NeuroProof':        'o',
    'DPLL-Baseline':     's',
    'NeuroProof+ATSS':   '^',
}


def load_results(csv_path: str) -> pd.DataFrame:
    df = pd.read_csv(csv_path)
    return df


def _save(fig, out_dir, name):
    out = os.path.join(out_dir, name)
    fig.savefig(out)
    print(f"Saved: {out}")
    plt.close(fig)


# ── Figure 1: Phase Transition ────────────────────────────────────────────────

def plot_phase_transition(df: pd.DataFrame, out_dir: str) -> None:
    """
    Fig 1: Fraction of SAT instances vs clause-to-variable ratio
    for NeuroProof and DPLL-Baseline.
    """
    data = df[df['name'].str.startswith('rand3cnf')].copy()
    if data.empty:
        print("  [SKIP] Fig 1: no rand3cnf data")
        return

    data['ratio'] = data['name'].str.extract(r'_r([\d.]+)').astype(float)

    fig, axes = plt.subplots(1, 2, figsize=(10, 4))

    # --- Left: SAT fraction ---
    ax = axes[0]
    for solver, grp in data.groupby('solver'):
        grouped = grp.groupby('ratio')['status']
        ratios = sorted(grouped.groups.keys())
        fracs = [
            (grouped.get_group(r).isin(['SAT', 'UNSAT'])).mean()
            if solver == 'DPLL-Baseline'
            else (grouped.get_group(r).isin(['SAT', 'UNSAT'])).mean()
            for r in ratios
        ]
        ax.plot(ratios, fracs, marker=MARKERS.get(solver, 'o'),
                color=COLORS.get(solver, 'gray'),
                label=solver, linewidth=1.8, markersize=5)

    ax.axvline(4.267, color='gray', linestyle='--', alpha=0.6,
               label='Phase transition ($\\alpha \\approx 4.27$)')
    ax.set_xlabel('Clause-to-variable ratio $\\alpha$')
    ax.set_ylabel('Fraction solved (SAT or UNSAT)')
    ax.set_title('(a) Phase Transition (n=30)')
    ax.legend(loc='lower left', fontsize=9)
    ax.set_xlim(2.0, 6.0)
    ax.set_ylim(-0.05, 1.05)
    ax.grid(alpha=0.3)

    # --- Right: Median solve time ---
    ax2 = axes[1]
    for solver, grp in data.groupby('solver'):
        grouped = grp.groupby('ratio')['time_sec']
        ratios = sorted(grouped.groups.keys())
        medians = [grouped.get_group(r).median() * 1000 for r in ratios]
        ax2.semilogy(ratios, medians, marker=MARKERS.get(solver, 'o'),
                     color=COLORS.get(solver, 'gray'),
                     label=solver, linewidth=1.8, markersize=5)

    ax2.axvline(4.267, color='gray', linestyle='--', alpha=0.6)
    ax2.set_xlabel('Clause-to-variable ratio $\\alpha$')
    ax2.set_ylabel('Median solve time (ms)')
    ax2.set_title('(b) Solve Time vs Ratio')
    ax2.legend(loc='upper left', fontsize=9)
    ax2.set_xlim(2.0, 6.0)
    ax2.grid(alpha=0.3, which='both')

    fig.tight_layout()
    _save(fig, out_dir, 'fig1_phase_transition.pdf')


# ── Figure 2: Pigeonhole Principle ───────────────────────────────────────────

def plot_pigeonhole(df: pd.DataFrame, out_dir: str) -> None:
    """Fig 2: Solve time and solve rate for PHP_n."""
    data = df[df['name'].str.startswith('PHP_') &
              ~df['name'].str.startswith('sota_PHP')].copy()
    if data.empty:
        # Fall back to sota_PHP data
        data = df[df['name'].str.startswith('PHP_')].copy()
    if data.empty:
        print("  [SKIP] Fig 2: no PHP data")
        return

    data['n'] = data['name'].str.extract(r'PHP_(\d+)').astype(int)

    fig, axes = plt.subplots(1, 2, figsize=(10, 4))

    # --- Left: Solve time ---
    ax = axes[0]
    for solver, grp in data.groupby('solver'):
        ns = sorted(grp['n'].unique())
        times = []
        for n in ns:
            sub = grp[grp['n'] == n]
            if len(sub) > 0:
                times.append(sub['time_sec'].values[0] * 1000)
            else:
                times.append(float('nan'))
        ax.semilogy(ns, times, marker=MARKERS.get(solver, 'o'),
                    color=COLORS.get(solver, 'gray'),
                    label=solver, linewidth=1.8, markersize=6)

    ax.set_xlabel('Number of holes $n$')
    ax.set_ylabel('Solve time (ms, log scale)')
    ax.set_title('(a) Pigeonhole: Solve Time')
    ax.legend(fontsize=9)
    ax.grid(alpha=0.3, which='both')

    # --- Right: Solve rate ---
    ax2 = axes[1]
    for solver, grp in data.groupby('solver'):
        ns = sorted(grp['n'].unique())
        rates = []
        for n in ns:
            sub = grp[grp['n'] == n]
            if len(sub) > 0:
                sat_unsat = sub['status'].isin(['SAT', 'UNSAT']).sum()
                rates.append(sat_unsat / len(sub) * 100)
            else:
                rates.append(0)
        ax2.plot(ns, rates, marker=MARKERS.get(solver, 'o'),
                 color=COLORS.get(solver, 'gray'),
                 label=solver, linewidth=1.8, markersize=6)

    ax2.set_xlabel('Number of holes $n$')
    ax2.set_ylabel('Solve rate (%)')
    ax2.set_title('(b) Pigeonhole: Solve Rate')
    ax2.legend(fontsize=9)
    ax2.set_ylim(-5, 110)
    ax2.grid(alpha=0.3)

    fig.tight_layout()
    _save(fig, out_dir, 'fig2_pigeonhole.pdf')


# ── Figure 3: Proof Quality Table ─────────────────────────────────────────────

def plot_proof_quality(df: pd.DataFrame, out_dir: str) -> None:
    """Fig 3: Proof size/depth table for classical tautologies."""
    data = df[df['name'].str.startswith('tauto(')].copy()
    if data.empty:
        print("  [SKIP] Fig 3: no tauto data")
        return

    data['formula'] = data['name'].str.extract(r'tauto\((.+)\)')
    data = data[data['status'] == 'PROVED']

    if data.empty:
        print("  [SKIP] Fig 3: no PROVED results")
        return

    fig, ax = plt.subplots(figsize=(10, 5))
    ax.axis('off')

    col_labels = ['Formula', 'Proof Size', 'Proof Depth', 'Time (ms)']
    rows = []
    for _, row in data.iterrows():
        rows.append([
            row['formula'][:45],
            str(int(row['proof_size'])),
            str(int(row['proof_depth'])),
            f"{row['time_sec'] * 1000:.2f}"
        ])

    table = ax.table(
        cellText=rows,
        colLabels=col_labels,
        cellLoc='center',
        loc='center',
        colWidths=[0.50, 0.15, 0.15, 0.15]
    )
    table.auto_set_font_size(False)
    table.set_fontsize(9)
    table.scale(1, 1.5)

    for j in range(len(col_labels)):
        table[(0, j)].set_facecolor('#2c5f8a')
        table[(0, j)].set_text_props(color='white', fontweight='bold')

    for i in range(1, len(rows) + 1):
        for j in range(len(col_labels)):
            if i % 2 == 0:
                table[(i, j)].set_facecolor('#e8f0f8')

    ax.set_title('Proof Quality on Classical Tautologies (NeuroProof+ATSS)',
                 fontsize=12, y=0.98)

    _save(fig, out_dir, 'fig3_proof_quality.pdf')


# ── Figure 4: ATSS Learning Curve ─────────────────────────────────────────────

def plot_atss_learning_curve(df: pd.DataFrame, out_dir: str) -> None:
    """
    Fig 4: ATSS online learning convergence.

    Reads epoch data from the CSV (saved by EXP-5) and plots the
    actual solve rate per epoch.
    """
    fig, axes = plt.subplots(1, 2, figsize=(10, 4))

    # Filter ATSS learning curve data
    learning = df[df['name'] == 'atss_learning_curve'].copy()
    if learning.empty:
        print("  [SKIP] fig4: no ATSS learning curve data in CSV")
        plt.close(fig)
        return

    # --- Left: Solve rate per epoch ---
    ax = axes[0]
    epochs = learning['instance_id'].values
    # proof_depth was repurposed to store solve_rate * 100
    solve_rates = learning['proof_depth'].values.astype(float)
    # decisions was repurposed to store solved count
    solved_counts = learning['decisions'].values.astype(int)
    # conflicts was repurposed to store failed count
    failed_counts = learning['conflicts'].values.astype(int)
    total_per_epoch = solved_counts + failed_counts

    ax.plot(epochs + 1, solve_rates, 'o-', color='#2ca02c', markersize=4,
            linewidth=1.5, label='ATSS solve rate')
    ax.axhline(100, color='gray', linestyle='--', alpha=0.5,
               label='Perfect (100%)')
    ax.set_xlabel('Epoch')
    ax.set_ylabel('Solve rate (%)')
    ax.set_title('(a) ATSS Solve Rate Convergence')
    ax.set_ylim(0, 110)
    ax.legend(fontsize=9)
    ax.grid(alpha=0.3)

    # --- Right: Solved count per epoch ---
    ax2 = axes[1]
    ax2.bar(epochs + 1, solved_counts, color='#1f77b4', alpha=0.7,
            label='Solved', edgecolor='black', linewidth=0.5)
    ax2.bar(epochs + 1, failed_counts, bottom=solved_counts,
            color='#d62728', alpha=0.7,
            label='Failed', edgecolor='black', linewidth=0.5)
    ax2.set_xlabel('Epoch')
    ax2.set_ylabel('Problems')
    ax2.set_title('(b) Solved / Failed per Epoch')
    ax2.legend(fontsize=9)
    ax2.grid(alpha=0.3, axis='y')

    fig.tight_layout()
    _save(fig, out_dir, 'fig4_atss_learning.pdf')


# ── Figure 5: Ablation Study ──────────────────────────────────────────────────

def plot_ablation(df: pd.DataFrame, out_dir: str) -> None:
    """
    Fig 5: Ablation study — NeuroProof vs DPLL-Baseline
    at easy (ratio=2.0), phase transition (ratio=4.3), and hard (ratio=6.0).
    """
    abl_data = df[df['name'].str.startswith('ablation_')].copy()

    if abl_data.empty:
        print("  [SKIP] Fig 5: no ablation data")
        return

    abl_data['difficulty'] = abl_data['name'].map({
        n: 'Easy (r=2.0)' if 'easy' in n
        else 'Phase (r=4.3)' if 'phase' in n
        else 'Hard (r=6.0)'
        for n in abl_data['name']
    })

    fig, axes = plt.subplots(1, 2, figsize=(10, 4))

    # --- Left: Median solve time by difficulty ---
    ax = axes[0]
    difficulties = ['Easy (r=2.0)', 'Phase (r=4.3)', 'Hard (r=6.0)']
    x = np.arange(len(difficulties))
    width = 0.35

    for i, (solver, color) in enumerate(
        [('NeuroProof', COLORS['NeuroProof']),
         ('DPLL-Baseline', COLORS['DPLL-Baseline'])]):
        grp = abl_data[abl_data['solver'] == solver]
        times = []
        for d in difficulties:
            sub = grp[grp['difficulty'] == d]['time_sec'].values * 1000
            times.append(np.median(sub) if len(sub) > 0 else 0)
        ax.bar(x + i * width, times, width, color=color, alpha=0.8,
               label=solver)

    ax.set_xticks(x + width / 2)
    ax.set_xticklabels(difficulties, fontsize=9)
    ax.set_ylabel('Median solve time (ms)')
    ax.set_title('(a) Solve Time by Difficulty')
    ax.legend(fontsize=9)
    ax.grid(alpha=0.3, axis='y')
    ax.set_yscale('log')

    # --- Right: Solve rate by difficulty ---
    ax2 = axes[1]
    for i, (solver, color) in enumerate(
        [('NeuroProof', COLORS['NeuroProof']),
         ('DPLL-Baseline', COLORS['DPLL-Baseline'])]):
        grp = abl_data[abl_data['solver'] == solver]
        rates = []
        for d in difficulties:
            sub = grp[grp['difficulty'] == d]
            solved = sub['status'].isin(['SAT', 'UNSAT']).sum()
            rates.append(solved / len(sub) * 100 if len(sub) > 0 else 0)
        ax2.bar(x + i * width, rates, width, color=color, alpha=0.8,
                label=solver)

    ax2.set_xticks(x + width / 2)
    ax2.set_xticklabels(difficulties, fontsize=9)
    ax2.set_ylabel('Solve rate (%)')
    ax2.set_title('(b) Solve Rate by Difficulty')
    ax2.legend(fontsize=9)
    ax2.set_ylim(0, 115)
    ax2.grid(alpha=0.3, axis='y')

    fig.tight_layout()
    _save(fig, out_dir, 'fig5_ablation.pdf')


# ── Figure 6: Scalability ─────────────────────────────────────────────────────

def plot_scalability(df: pd.DataFrame, out_dir: str) -> None:
    """
    Fig 6: Solve time vs n_vars at phase transition ratio.
    Shows median with IQR bands.
    """
    data = df[df['name'].str.startswith('scale_n')].copy()
    if data.empty:
        print("  [SKIP] Fig 6: no scalability data")
        return

    data['n_vars'] = data['name'].str.extract(r'scale_n(\d+)').astype(int)

    fig, ax = plt.subplots(figsize=(8, 5))

    for solver, grp in data.groupby('solver'):
        sizes = sorted(grp['n_vars'].unique())
        medians = []
        q25s = []
        q75s = []
        for s in sizes:
            sub = grp[grp['n_vars'] == s]['time_sec'].values * 1000
            if len(sub) > 0:
                medians.append(np.median(sub))
                q25s.append(np.percentile(sub, 25))
                q75s.append(np.percentile(sub, 75))
            else:
                medians.append(float('nan'))
                q25s.append(float('nan'))
                q75s.append(float('nan'))

        color = COLORS.get(solver, 'gray')
        marker = MARKERS.get(solver, 'o')
        ax.plot(sizes, medians, marker=marker, color=color,
                label=solver, linewidth=2, markersize=6)
        ax.fill_between(sizes, q25s, q75s, color=color, alpha=0.15)

    ax.set_xlabel('Number of variables $n$')
    ax.set_ylabel('Solve time (ms, median + IQR)')
    ax.set_title('Scalability at Phase Transition ($\\alpha = 4.267$)')
    ax.legend(fontsize=10)
    ax.grid(alpha=0.3)
    ax.set_yscale('log')

    fig.tight_layout()
    _save(fig, out_dir, 'fig6_scalability.pdf')


# ── Figure 7: SOTA Comparison ────────────────────────────────────────────────

def plot_sota_comparison(df: pd.DataFrame, out_dir: str) -> None:
    """
    Fig 7: Head-to-head SOTA comparison — DPLL vs NeuroProof+ATSS
    on PHP instances and random 3-CNF.
    """
    sota_data = df[df['name'].str.startswith('sota_')].copy()
    if sota_data.empty:
        print("  [SKIP] Fig 7: no SOTA comparison data")
        return

    fig, axes = plt.subplots(1, 2, figsize=(10, 4))

    # Part A: PHP
    php_data = sota_data[sota_data['name'].str.startswith('sota_PHP')].copy()
    if not php_data.empty:
        php_data['n'] = php_data['name'].str.extract(r'sota_PHP_(\d+)').astype(int)
        ax = axes[0]

        for solver, grp in php_data.groupby('solver'):
            ns = sorted(grp['n'].unique())
            times = []
            for n in ns:
                sub = grp[grp['n'] == n]
                if len(sub) > 0:
                    times.append(sub['time_sec'].values[0] * 1000)
                else:
                    times.append(float('nan'))
            ax.bar([n - 0.15 if solver == 'DPLL-Baseline' else n + 0.15 for n in ns],
                   times, width=0.3,
                   color=COLORS.get(solver, 'gray'), alpha=0.8,
                   label=solver)

        ax.set_xlabel('PHP$_n$')
        ax.set_ylabel('Solve time (ms, log)')
        ax.set_title('(a) Pigeonhole: DPLL vs NeuroProof')
        ax.set_yscale('log')
        ax.legend(fontsize=9)
        ax.grid(alpha=0.3, axis='y')

    # Part B: Random 3-CNF
    rand_data = sota_data[sota_data['name'].str.startswith('sota_rand3cnf')].copy()
    if not rand_data.empty:
        rand_data['ratio'] = rand_data['name'].str.extract(
            r'sota_rand3cnf_r([\d.]+)').astype(float)
        ax2 = axes[1]

        for solver, grp in rand_data.groupby('solver'):
            ratios = sorted(grp['ratio'].unique())
            medians = []
            for r in ratios:
                sub = grp[grp['ratio'] == r]['time_sec'].values * 1000
                if len(sub) > 0:
                    medians.append(np.median(sub))
                else:
                    medians.append(float('nan'))
            ax2.plot(ratios, medians, marker=MARKERS.get(solver, 'o'),
                     color=COLORS.get(solver, 'gray'),
                     label=solver, linewidth=1.8, markersize=5)

        ax2.axvline(4.267, color='gray', linestyle='--', alpha=0.5)
        ax2.set_xlabel('Ratio $\\alpha$')
        ax2.set_ylabel('Median solve time (ms)')
        ax2.set_title('(b) Random 3-CNF: DPLL vs NeuroProof')
        ax2.legend(fontsize=9)
        ax2.grid(alpha=0.3)
        ax2.set_yscale('log')

    fig.tight_layout()
    _save(fig, out_dir, 'fig7_sota_comparison.pdf')


# ── Figure 8: Tseitin Results ─────────────────────────────────────────────────

def plot_tseitin(df: pd.DataFrame, out_dir: str) -> None:
    """Fig 8: Tseitin encoding solve time vs graph size."""
    data = df[df['name'].str.startswith('Tseitin_n')].copy()
    if data.empty:
        print("  [SKIP] Fig 8: no Tseitin data")
        return

    data['n_verts'] = data['name'].str.extract(r'Tseitin_n(\d+)').astype(int)

    fig, ax = plt.subplots(figsize=(8, 5))

    for solver, grp in data.groupby('solver'):
        sizes = sorted(grp['n_verts'].unique())
        medians = []
        for s in sizes:
            sub = grp[grp['n_verts'] == s]['time_sec'].values * 1000
            if len(sub) > 0:
                medians.append(np.median(sub))
            else:
                medians.append(float('nan'))

        color = COLORS.get(solver, 'gray')
        marker = MARKERS.get(solver, 'o')
        ax.plot(sizes, medians, marker=marker, color=color,
                label=solver, linewidth=2, markersize=6)

    ax.set_xlabel('Graph size (vertices)')
    ax.set_ylabel('Median solve time (ms)')
    ax.set_title('Tseitin Tautology Performance')
    ax.legend(fontsize=10)
    ax.grid(alpha=0.3)
    ax.set_yscale('log')

    fig.tight_layout()
    _save(fig, out_dir, 'fig8_tseitin.pdf')


# ── Main ──────────────────────────────────────────────────────────────────────

if __name__ == '__main__':
    experiments_dir = os.path.dirname(__file__)
    csv_path = os.path.join(experiments_dir, 'results.csv')

    if not os.path.exists(csv_path):
        print(f"No results found at {csv_path}")
        print("Run benchmark_suite.py first.")
        sys.exit(1)

    df = load_results(csv_path)
    print(f"Loaded {len(df)} results from {csv_path}")

    out_dir = os.path.join(experiments_dir, 'figures')
    os.makedirs(out_dir, exist_ok=True)

    print("\nGenerating figures...")
    plot_phase_transition(df, out_dir)
    plot_pigeonhole(df, out_dir)
    plot_proof_quality(df, out_dir)
    plot_atss_learning_curve(df, out_dir)
    plot_ablation(df, out_dir)
    plot_scalability(df, out_dir)
    plot_sota_comparison(df, out_dir)
    plot_tseitin(df, out_dir)

    print("\nAll figures generated.")
