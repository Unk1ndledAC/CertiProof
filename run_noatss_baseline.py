"""
Run NO-ATSS baseline for comparison (same 200 formulas, epoch=40).
"""
import sys, os
sys.path.insert(0, '.')
import random, time

from src.formula import Var, Implies, And, Or
from src.solver import ATSS
from src.tactic import TacticEngine

print("=" * 60)
print(" NO-ATSS Baseline (Paper-quality run)")
print(" 200 formulas, epoch_size=40, 5 epochs")
print("=" * 60)

rng = random.Random(42)
# No ATSS: fresh ATSS that never learns (all scores stay uniform)
no_atss = ATSS()  # starts with uniform prior, never updates
engine = TacticEngine(atss=no_atss, max_depth=200)

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

results = []
epoch_solved = 0

t_start = time.perf_counter()
for i in range(n_total):
    depth = rng.randint(1, 4)
    f = gen_formula(depth, rng)
    
    try:
        proof = engine.prove(f)
        epoch_solved += 1
    except Exception:
        pass
    
    if (i + 1) % epoch_size == 0:
        epoch_idx = (i + 1) // epoch_size
        results.append((epoch_idx, epoch_solved))
        print(f"  Epoch {epoch_idx}: solved {epoch_solved}/{epoch_size} "
              f"({100.0*epoch_solved/epoch_size:.1f}%)")
        epoch_solved = 0

print(f"\nTotal time: {time.perf_counter()-t_start:.2f}s")
avg_solved = sum(s for _, s in results) / len(results)
print(f"Average solved per epoch: {avg_solved:.1f}")
print(f"\nData: {results}")
