import re
from z3  import Solver, sat, Int, Real, And, Or, Not, Abs,  Optimize, sat
import random
import sys
import os

def read_constraints(filepath):
    with open(filepath, 'r') as f:
        lines = f.readlines()
    # Strip whitespace and ignore empty lines or comment lines
    constraints = [line.strip() for line in lines if line.strip() and not line.strip().startswith('#')]
    return constraints

def extract_variables(constraints):
    var_pattern = re.compile(r'\b[a-zA-Z_]\w*\b')
    variables = set()
    for c in constraints:
        for var in var_pattern.findall(c):
            if not var in {'And', 'Or', 'Not'}:
                variables.add(var)
    return variables

def parse_to_z3(constraints):
    variables = extract_variables(constraints)
    print(f"Extracted variables: {variables}")
    ctx = {}
    for var in variables:
        ctx[var] = Int(var)  # you can generalize to Real(var) if needed

    # Add logical functions
    ctx.update({'And': And, 'Or': Or, 'Not': Not})

    z3_constraints = []
    for c in constraints:
        try:
            z3_constraints.append(eval(c, {}, ctx))
        except Exception as e:
            print(f"Failed to parse constraint: '{c}' with error {e}")
            continue
    return z3_constraints, ctx



def add_fixed_values_z3_constraints(z3_constraints, fixed_values, ctx):
    """
    Adds fixed-value constraints as Z3 expressions to the existing z3_constraints list and updates ctx.

    Args:
        z3_constraints: list of Z3 expressions (not strings!)
        fixed_values: dict, e.g., {"x": 3, "z": 7}
        ctx: dict, the context from parse_to_z3()

    Returns:
        updated list of z3_constraints, updated ctx
    """
    ctx_new = ctx.copy()
    updated_constraints = z3_constraints.copy()
    for var, value in fixed_values.items():
        if var not in ctx_new:
            # Always declare variables as Int
            ctx_new[var] = Int(var)
        
        # Ensure the value is treated as an integer
        value = int(float(value))
        
        # Add the constraint
        constraint_str = f"{var} == {value}"
        try:
            updated_constraints.append(eval(constraint_str, {}, ctx_new))
        except Exception as e:
            print(f"Failed to add fixed constraint '{constraint_str}': {e}")
            continue
        print(f"Added fixed constraint: {constraint_str}")
    return updated_constraints, ctx_new




def find_maxsat_solution(hard_constraints, soft_constraints, ctx):
    """
    Try to find a solution using MaxSAT with soft constraints.

    Args:
        hard_constraints: list of Z3 expressions (hard constraints)
        soft_constraints: dict of variable: value (soft constraints)
        ctx: context with Z3 variables

    Returns:
        A solution dictionary if found, else None
    """
    opt = Optimize()
    for constr in hard_constraints:
        opt.add(constr)

    # Add soft constraints
    for var, value in soft_constraints.items():
        soft_constr = eval(f"{var} == {value}", {}, ctx)
        opt.add_soft(soft_constr)

    if opt.check() == sat:
        m = opt.model()
        solution = {str(d): m[d] for d in m}
        return solution
    else:
        return None

def find_diverse_solutions(z3_constraints, max_solutions=5, start_distance=100, min_distance=1, decay_factor=0.5):
    solver = Solver()
    solver.add(z3_constraints)
    solutions = []
    all_vars = set()
    current_distance = start_distance

    while len(solutions) < max_solutions and solver.check() == sat:
        model = solver.model()
        sol = {str(d): model[d].as_long() if model[d].sort().name() == 'Int' else model[d] for d in model}
        solutions.append(sol)
        all_vars.update(sol.keys())

        # Build exclusion to push next solution away
        distance_constraints = []
        for var in sol:
            if isinstance(sol[var], int):
                z3_var = Int(var)
                distance_constraints.append(Abs(z3_var - sol[var]) >= current_distance)

        solver.push()  # Save solver state
        solver.add(Or(distance_constraints))

        if solver.check() != sat:
            # Not enough solutions at this distance — reduce distance and retry
            solver.pop()  # Restore solver state before adding the distance constraint
            current_distance = max(int(current_distance * decay_factor), min_distance)
            if current_distance == min_distance:
                break  # Give up if we hit min_distance
        else:
            solver.pop()
            solver.add(Or(distance_constraints))  # Keep the constraint if it works

    return solutions
