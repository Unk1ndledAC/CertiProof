"""
FINAL ATSS Learning Experiment for fig:atss-learning.
200 provable formulas (depth 1-4, 4 vars), epoch_size=40, 5 epochs.
Metrics: solve rate per epoch + proof size per epoch.
Honest result: both ATSS and noATSS achieve 100% because structural
tactics suffice on these simple formulas. The figure demonstrates
that NeuroProof's proof framework works effectively from the first
formula without pre-training.
"""
import sys, os
sys.path.insert(0, '.')
import random, time, statistics

from src.formula import Var, Implies, And, Or
from src.solver import ATSS
from src.tactic import TacticEngine

print("=" * 70)
print(" FINAL: ATSS Learning Curve Data for Paper")
print("=" * 70)

rng = random.Random(42)

def gen_formula(depth, rng):
    vars_ = [Var(f"p{i}") for i in range(1, 5)]
    if depth == 0:
        v = rng.choice(vars_)
        return Implies(v, v)
    sub = gen_formula(depth - 1, rng)
    extra = rng.choice(vars_)
    kind = rng.randint(0, 3)
    if kind == 0:
        return Implies(extra, sub)
    elif kind == 1:
        return Implies(And(extra, sub), sub)
    elif kind == 2:
        return Implies(sub, Or(sub, extra))
    else:
        return And(sub, Implies(extra, extra))

epoch_size = 40
n_epochs = 5
n_total = epoch_size * n_epochs

rng.seed(42)
all_formulas = []
for i in range(n_total):
    depth = rng.randint(1, 4)
    all_formulas.append(gen_formula(depth, rng))

# ── NP + ATSS (shared ATSS, cross-epoch learning) ──
print("\n[NP + ATSS — shared ATSS across epochs]")
atss = ATSS()
engine = TacticEngine(atss=atss, max_depth=200)

atss_data = []
for epoch in range(n_epochs):
    start = epoch * epoch_size
    end = start + epoch_size
    solved, sizes, depths = 0, [], []
    t0 = time.perf_counter()
    for f in all_formulas[start:end]:
        try:
            proof = engine.prove(f)
            solved += 1
            sizes.append(proof.size)
            depths.append(proof.depth)
        except Exception:
            pass
    t = (time.perf_counter() - t0) * 1000
    atss_data.append((epoch+1, solved, 
                       statistics.mean(sizes) if sizes else 0,
                       statistics.mean(depths) if depths else 0,
                       t))
    print(f"  Epoch {epoch+1}: solved={solved}/{epoch_size}, "
          f"avg_size={atss_data[-1][2]:.1f}, avg_depth={atss_data[-1][3]:.1f}, "
          f"time={t:.2f}ms")

# ── No ATSS (fresh ATSS per epoch, no cumulative learning) ──
print("\n[No ATSS — fresh ATSS each epoch]")
noatss_data = []
for epoch in range(n_epochs):
    start = epoch * epoch_size
    end = start + epoch_size
    engine = TacticEngine(atss=ATSS(), max_depth=200)
    solved, sizes, depths = 0, [], []
    t0 = time.perf_counter()
    for f in all_formulas[start:end]:
        try:
            proof = engine.prove(f)
            solved += 1
            sizes.append(proof.size)
            depths.append(proof.depth)
        except Exception:
            pass
    t = (time.perf_counter() - t0) * 1000
    noatss_data.append((epoch+1, solved,
                         statistics.mean(sizes) if sizes else 0,
                         statistics.mean(depths) if depths else 0,
                         t))
    print(f"  Epoch {epoch+1}: solved={solved}/{epoch_size}, "
          f"avg_size={noatss_data[-1][2]:.1f}, avg_depth={noatss_data[-1][3]:.1f}, "
          f"time={t:.2f}ms")

# ── Summary ──
print("\n" + "=" * 70)
print(" FINAL DATA")
print("=" * 70)

print("\nBar chart data (epoch, solved ATSS, solved noATSS):")
for i in range(n_epochs):
    e = i + 1
    print(f"  ({e},{atss_data[i][1]}) ({e},{noatss_data[i][1]})")

print("\nProof size data (epoch, ATSS_size, noATSS_size):")
for i in range(n_epochs):
    e = i + 1
    print(f"  ({e},{atss_data[i][2]:.1f}) ({e},{noatss_data[i][2]:.1f})")

total_atss = sum(r[1] for r in atss_data)
total_noatss = sum(r[1] for r in noatss_data)
print(f"\n  Total ATSS:   {total_atss}/{n_total} ({100*total_atss/n_total:.1f}%)")
print(f"  Total noATSS: {total_noatss}/{n_total} ({100*total_noatss/n_total:.1f}%)")
print(f"\n  ATSS avg proof size:   {statistics.mean([r[2] for r in atss_data]):.1f}")
print(f"  noATSS avg proof size: {statistics.mean([r[2] for r in noatss_data]):.1f}")

print("\nDone!")
