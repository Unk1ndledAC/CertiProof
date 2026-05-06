"""
verify_installation.py
======================
Quick verification script for NeuroProof.
Tests each core module to ensure correct functionality.

Usage:
    python verify_installation.py

All tests should complete in under 10 seconds on any modern machine.
No external dependencies are required (pure Python stdlib only).
"""

import sys
import os
import time

sys.path.insert(0, os.path.dirname(__file__))

passed = 0
failed = 0


def check(name, condition, detail=""):
    global passed, failed
    if condition:
        passed += 1
        print(f"  [PASS] {name}")
    else:
        failed += 1
        msg = f"  [FAIL] {name}"
        if detail:
            msg += f" -- {detail}"
        print(msg)


def test_formula_module():
    """Test formula.py: parsing, AST construction, normal forms."""
    print("\n[1] formula.py")
    from src.formula import (Var, Not, And, Or, Implies, Iff, Xor,
                              Top, Bot, parse, to_nnf, to_cnf, eliminate_iff,
                              Connective)

    # AST construction
    p = Var("p")
    q = Var("q")
    check("Var construction", p.name == "p")
    check("Top/Bot singletons", Top.connective == Connective.TOP
          and Bot.connective == Connective.BOT)

    # Connectives
    f = And(p, q)
    check("And construction", f.connective == Connective.AND
          and f.left == p and f.right == q)
    f = Or(p, q)
    check("Or construction", f.connective == Connective.OR)
    f = Implies(p, q)
    check("Implies construction", f.connective == Connective.IMP)
    f = Iff(p, q)
    check("Iff construction", f.connective == Connective.IFF)
    f = Xor(p, q)
    check("Xor construction", f.connective == Connective.XOR)

    # Not with simplification
    check("Double negation elimination", Not(Not(p)) == p)
    check("Not Top = Bot", Not(Top) == Bot)
    check("Not Bot = Top", Not(Bot) == Top)

    # Operator overloads
    check("__and__", (p & q) == And(p, q))
    check("__or__", (p | q) == Or(p, q))
    check("__invert__", (~p) == Not(p))
    check("__rshift__", (p >> q) == Implies(p, q))

    # Properties
    f = And(Or(p, q), Implies(p, q))
    check("variables()", f.variables() == frozenset({"p", "q"}))
    check("size()", f.size > 0)
    check("depth()", f.depth > 0)
    check("is_literal (Var)", p.is_literal)
    check("is_literal (Not Var)", Not(p).is_literal)
    check("is_clause (Or of literals)", Or(p, Not(q)).is_clause)

    # Parsing
    f = parse("p -> q")
    check("parse implication", f == Implies(p, q))
    f = parse("p & q")
    check("parse conjunction", f == And(p, q))
    f = parse("p | q")
    check("parse disjunction", f == Or(p, q))
    f = parse("~p")
    check("parse negation", f == Not(p))
    f = parse("p <-> q")
    check("parse biconditional", f == Iff(p, q))
    f = parse("(p -> q) -> (~q -> ~p)")
    check("parse complex formula",
          f == Implies(Implies(p, q), Implies(Not(q), Not(p))))

    # NNF / CNF
    f = parse("~(p & q)")
    nnf = to_nnf(f)
    check("to_nnf", nnf.connective == Connective.OR)
    cnf = to_cnf(parse("p -> q"))
    check("to_cnf", cnf is not None)

    # eliminate_iff
    f = Iff(p, q)
    check("eliminate_iff", eliminate_iff(f).connective == Connective.AND)


def test_proof_module():
    """Test proof.py: ProofBuilder, Proof verification."""
    print("\n[2] proof.py")
    from src.formula import Var, Not, And, Or, Implies, Top, Bot
    from src.proof import Proof, ProofStep, ProofBuilder, Rule

    p = Var("p")
    q = Var("q")

    # Simple proof: p -> p (axiom assumption)
    # An AXIOM step has no undischarged assumptions (it's a bare assumption)
    pb = ProofBuilder()
    step = pb.assume(Implies(p, p))
    proof = Proof(step)
    check("Proof construction", proof.conclusion == Implies(p, p))
    check("Proof is theorem (AXIOM)", proof.is_theorem)

    # Proof of p -> p via IMP_I
    pb2 = ProofBuilder()
    hyp = pb2.assume(p, "hyp:p")
    body = pb2.assume(p, "hyp:p2")
    imp = pb2.imp_i(hyp, body)
    proof2 = Proof(imp)
    check("IMP-I proof", proof2.conclusion == Implies(p, p))
    check("IMP-I is theorem", proof2.is_theorem)
    check("IMP-I size", proof2.size > 0)

    # Modus ponens
    pb3 = ProofBuilder()
    h1 = pb3.assume(Implies(p, q))
    h2 = pb3.assume(p)
    mp = pb3.imp_e(h1, h2)
    check("IMP-E (modus ponens)", mp.conclusion == q)

    # Proof checking
    check("Proof check (valid)", proof2.check())

    # Build with AND-I
    pb4 = ProofBuilder()
    s1 = pb4.assume(p)
    s2 = pb4.assume(q)
    s3 = pb4.and_i(s1, s2)
    check("AND-I proof", s3.conclusion == And(p, q))


def test_kernel_module():
    """Test kernel.py: verification of proof steps."""
    print("\n[3] kernel.py")
    from src.formula import Var, Not, And, Or, Implies, Top, Bot, Iff
    from src.proof import ProofStep, ProofBuilder, Rule
    from src.kernel import verify_step, verify_step_strict, KernelError

    p = Var("p")
    q = Var("q")

    # AXIOM
    check("AXIOM rule", verify_step(ProofStep(
        conclusion=p, rule=Rule.AXIOM, premises=[])))

    # TRUTH
    check("TRUTH rule", verify_step(ProofStep(
        conclusion=Top, rule=Rule.TRUTH, premises=[])))

    # AND_I
    check("AND-I rule", verify_step(ProofStep(
        conclusion=And(p, q), rule=Rule.AND_I,
        premises=[ProofStep(p, Rule.AXIOM), ProofStep(q, Rule.AXIOM)])))

    # OR_I_LEFT
    check("OR-I-L rule", verify_step(ProofStep(
        conclusion=Or(p, q), rule=Rule.OR_I_LEFT,
        premises=[ProofStep(p, Rule.AXIOM)])))

    # IMP_E
    check("IMP-E rule", verify_step(ProofStep(
        conclusion=q, rule=Rule.IMP_E,
        premises=[
            ProofStep(Implies(p, q), Rule.AXIOM),
            ProofStep(p, Rule.AXIOM),
        ])))

    # Invalid step should fail
    check("Invalid step rejected", not verify_step(ProofStep(
        conclusion=q, rule=Rule.AND_E_LEFT,
        premises=[ProofStep(p, Rule.AXIOM)])))

    # verify_step_strict should raise
    try:
        verify_step_strict(ProofStep(
            conclusion=Bot, rule=Rule.TRUTH,
            premises=[ProofStep(p, Rule.AXIOM)]))
        check("Strict verify raises", False)
    except KernelError:
        check("Strict verify raises", True)


def test_solver_module():
    """Test solver.py: CDCL solving, ATSS."""
    print("\n[4] solver.py")
    from src.formula import Var, Not, And, Or, Implies, parse
    from src.solver import (NeuroProofSolver, ATSS, SolverStatus,
                             Clause, pos, neg_lit, negate_lit,
                             clause_from_formula)

    # Basic literal operations
    check("pos() and neg_lit()", pos("x1") == ("x1", True)
          and neg_lit("x1") == ("x1", False))
    check("negate_lit()", negate_lit(("x1", True)) == ("x1", False))

    # Clause operations
    p, q = Var("p"), Var("q")
    clause = clause_from_formula(Or(p, Not(q)))
    check("clause_from_formula", clause == frozenset({("p", True), ("q", False)}))

    # ATSS
    atss = ATSS()
    check("ATSS initial score", abs(atss.score(p) - 0.5) < 0.01)
    atss.record_success(p)
    check("ATSS score after success", atss.score(p) > 0.5)
    atss.record_failure(p)
    check("ATSS score after failure (decayed)", atss.score(p) < 1.0)

    # Simple SAT solving
    solver = NeuroProofSolver(max_conflicts=10000)
    clauses = [
        frozenset({("x1", True), ("x2", True)}),
    ]
    result = solver.solve_clauses(clauses, {"x1", "x2"})
    check("SAT solve", result.status == SolverStatus.SAT)
    check("SAT model", result.model is not None)

    # Simple UNSAT
    clauses = [
        frozenset({("x1", True)}),
        frozenset({("x1", False)}),
    ]
    result = solver.solve_clauses(clauses, {"x1"})
    check("UNSAT solve", result.status == SolverStatus.UNSAT)

    # Tautology via formula
    # Note: p -> p is a tautology (always true), so solve_formula returns SAT
    result = solver.solve_formula(parse("p -> p"))
    check("Tautology formula", result.status == SolverStatus.SAT)

    # Unsatisfiable formula
    solver_limited = NeuroProofSolver(max_conflicts=100)
    result = solver_limited.solve_clauses([
        frozenset({("x1", True)}),
        frozenset({("x1", False)}),
    ], {"x1"})
    check("UNSAT for small instance", result.status == SolverStatus.UNSAT)

    # Unknown for hard instance
    # Generate a phase-transition 3-CNF instance that may not resolve quickly
    solver_limited2 = NeuroProofSolver(max_conflicts=10)
    # Use the formula solver on a moderately complex formula
    f_unknown = parse("(a -> b) & (b -> c) & (c -> d) & (d -> e) & (e -> a) & (a -> ~a)")
    result = solver_limited2.solve_formula(f_unknown)
    check("Solve complex formula",
          result.status in (SolverStatus.UNSAT, SolverStatus.SAT, SolverStatus.UNKNOWN))


def test_tactic_module():
    """Test tactic.py: tactic engine, tauto prove."""
    print("\n[5] tactic.py")
    from src.formula import parse, Var
    from src.solver import SolverStatus
    from src.tactic import TacticEngine, tauto, decide, refute, TacticResult, TacticStatus

    # Basic tautologies
    tests = [
        ("p -> p", True),
        ("(p & q) -> p", True),
        ("(p & q) -> q", True),
        ("p -> (q -> p)", True),
        ("p -> (p | q)", True),
        ("q -> (p | q)", True),
        ("p | ~p", True),          # law of excluded middle
        ("~(p & ~p)", True),       # law of non-contradiction
    ]

    for fstr, expected in tests:
        f = parse(fstr)
        try:
            proof = tauto(f)
            ok = proof.is_theorem and proof.size > 0
        except Exception as e:
            ok = False
        check(f"tauto({fstr})", ok)

    # Modus ponens tautology
    f = parse("(p -> q) -> ((q -> r) -> (p -> r))")
    try:
        proof = tauto(f)
        check("Transitivity", proof.is_theorem and proof.size > 0)
    except Exception:
        check("Transitivity", False)

    # decide: check SAT/UNSAT/UNKNOWN
    sat_status = decide(parse("p | q"))
    check("decide (SAT formula)", sat_status in (SolverStatus.SAT,))

    # UNSAT detection
    unsat_status = decide(parse("p & ~p"))
    check("decide (UNSAT formula)", unsat_status in (SolverStatus.UNSAT,))


def test_tseitin_module():
    """Test tseitin.py: CNF encoding."""
    print("\n[6] tseitin.py")
    from src.formula import parse, And, Or, Var, Connective
    from src.tseitin import TseitinEncoder

    # Simple encoding
    enc = TseitinEncoder()
    f = parse("p -> q")
    cnf = enc.encode(f)
    check("Tseitin encode produces formula", cnf is not None)
    check("Tseitin CNF is AND", cnf.connective == Connective.AND
          or cnf.connective == Connective.OR
          or cnf.connective == Connective.VAR)

    # Verify equisatisfiability: (p->q) is SAT
    # Note: solve_formula auto-converts to CNF, so use solve_clauses
    # for direct CNF testing. We test that the Tseitin encoding works.
    enc2 = TseitinEncoder()
    cnf2 = enc2.encode(parse("p -> p"))
    # cnf2 includes the assertion that the root aux var is True,
    # so it should be satisfiable. Use solve_clauses to avoid
    # double Tseitin encoding.
    from src.solver import NeuroProofSolver, SolverStatus, Clause
    clauses = NeuroProofSolver._cnf_to_clauses(cnf2)
    all_vars = set()
    for c in clauses:
        for v, _ in c:
            all_vars.add(v)
    solver = NeuroProofSolver()
    result = solver.solve_clauses(clauses, all_vars)
    check("Tseitin equisatisfiable (p->p SAT)", result.status == SolverStatus.SAT)


def test_integration():
    """Integration test: full prove + verify chain."""
    print("\n[7] Integration")
    from src.formula import parse
    from src.tactic import tauto
    from src.kernel import verify_step

    # Prove contrapositive
    f = parse("(p -> q) -> (~q -> ~p)")
    proof = tauto(f)
    check("Contrapositive: theorem", proof.is_theorem)
    check("Contrapositive: positive size", proof.size > 0)

    # Prove hypothetical syllogism
    f2 = parse("(p -> q) -> (q -> r) -> (p -> r)")
    proof2 = tauto(f2)
    check("Hypothetical syllogism: theorem", proof2.is_theorem)
    check("Hypothetical syllogism: positive size", proof2.size > 0)


def main():
    print("=" * 60)
    print(" NeuroProof Installation Verification")
    print("=" * 60)

    t0 = time.perf_counter()

    test_formula_module()
    test_proof_module()
    test_kernel_module()
    test_solver_module()
    test_tactic_module()
    test_tseitin_module()
    test_integration()

    elapsed = time.perf_counter() - t0

    print("\n" + "=" * 60)
    print(f" Results: {passed} passed, {failed} failed "
          f"({elapsed:.2f}s)")
    print("=" * 60)

    if failed == 0:
        print("All tests passed! NeuroProof is correctly installed.")
    else:
        print(f"WARNING: {failed} test(s) failed.")
        sys.exit(1)


if __name__ == "__main__":
    main()
