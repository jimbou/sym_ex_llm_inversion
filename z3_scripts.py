import re
from z3  import Solver, sat, Int, Real, And, Or, Not, Abs, Sum, RealVal, IntVal, Optimize, sat, StringVal
import random
import sys
import os
from z3 import Optimize, Abs, sat, Solver, StringVal
import string
import Levenshtein

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

def parse_to_z3(constraints, total_vars):
    variables = extract_variables(constraints)
    print(f"Extracted variables: {variables}")
    ctx = {}
    for var in variables:
        if var not in total_vars:
            print(f"Warning: Variable '{var}' not found in total_vars.")
            ctx[var] = Int(var)  # default to Int, can be changed based on context
        else:
            var_type = total_vars[var].lower()
            if 'float' in var_type or 'double' in var_type:
                ctx[var] = Real(var)
            else:
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



def find_numeric_min_solution(hard_constraints, soft_constraints, ctx):
    """
    Find an assignment that minimizes the L1 distance to the given numeric soft constraints.

    Args:
        hard_constraints: list of Z3 BoolRef (hard constraints)
        soft_constraints: dict mapping variable_name (str) to target numeric value (int or float)
        ctx: dict mapping variable_name (str) to Z3 variable

    Returns:
        dict[str, Z3 value]: a model assignment minimizing sum(|var - target|), or None
    """
    opt = Optimize()
    for c in hard_constraints:
        opt.add(c)

    objective_terms = []
    for var, val in soft_constraints.items():
        z3_var = ctx[var]
        if z3_var.sort().name() == "Real":
            val_expr = RealVal(val)
        else:
            val_expr = IntVal(int(val))
        objective_terms.append(Abs(z3_var - val_expr))

    opt.minimize(sum(objective_terms))

    if opt.check() == sat:
        m = opt.model()
        return {str(d): m[d] for d in m}
    else:
        return None

def add_fixed_values_z3_constraints(z3_constraints, fixed_values, ctx, types_dict):
    """
    Adds fixed-value constraints as Z3 expressions to the existing z3_constraints list
    and updates ctx with any missing declarations, using types_dict to choose Int vs Real.

    Args:
        z3_constraints: list of Z3 expressions (not strings!)
        fixed_values: dict, e.g., {"x": 3, "y": 3.14, "s": "hello"}
        ctx: dict, the context from parse_to_z3()
        types_dict: dict mapping variable_name (str) to type name (str),
                    e.g. {"x":"int", "y":"double", "s":"string"}

    Returns:
        updated_constraints: list of Z3 expressions
        ctx_new: updated ctx dict with any new Z3 variables added
    """
    ctx_new = ctx.copy()
    updated_constraints = list(z3_constraints)

    for var, raw_val in fixed_values.items():
        typ = types_dict.get(var, "int").lower()

        # Declare variable in Z3 context if missing
        
        #if any of the words float double  is in the type, use Real
        if any(word in typ for word in ["float", "double"]):
            ctx_new[var] = Real(var)
        else:
            ctx_new[var] = Int(var)

        z3_var = ctx_new[var]

        # Convert & wrap the value appropriately
        if any(word in typ for word in ["float", "double"]):
            # treat as Real: cast to float then to Python string for Z3
            val = float(raw_val)
            val_str = str(val)
        elif typ in {"int", "long"}:
            # treat as Int
            val = int(float(raw_val))
            val_str = str(val)
        else:
            # For other types (e.g., strings), we could extend here
            # For now, raise or skip
            raise ValueError(f"Unsupported fixed-value type '{typ}' for var '{var}'")

        # Build and add the constraint
        constraint = eval(f"{var} == {val_str}", {}, ctx_new)
        updated_constraints.append(constraint)
        print(f"[add_fixed_values] Added {typ} constraint: {var} == {val_str}")

    return updated_constraints, ctx_new


def find_string_distance_solution(hard_constraints, soft_constraints, ctx,
                                  num_samples=100, max_edits=2):
    """
    Heuristic search to find a string assignment closest (by Levenshtein) to target values.

    Args:
        hard_constraints: list of Z3 BoolRef (hard constraints)
        soft_constraints: dict mapping variable_name (str) to target string
        ctx: dict mapping variable_name (str) to Z3 String variable
        num_samples: number of random mutations to attempt
        max_edits: maximum random edits per sample

    Returns:
        dict[str, Z3 value]: the best model found, or None
    """
    def random_edit(s):
        """Apply up to `max_edits` random insert/delete/substitute operations."""
        alphabet = string.ascii_letters + string.digits + " "
        candidate = s
        for _ in range(random.randint(1, max_edits)):
            op = random.choice(['insert', 'delete', 'substitute'])
            if op == 'insert':
                pos = random.randrange(len(candidate) + 1)
                candidate = candidate[:pos] + random.choice(alphabet) + candidate[pos:]
            elif op == 'delete' and candidate:
                pos = random.randrange(len(candidate))
                candidate = candidate[:pos] + candidate[pos+1:]
            elif op == 'substitute' and candidate:
                pos = random.randrange(len(candidate))
                candidate = candidate[:pos] + random.choice(alphabet) + candidate[pos+1:]
        return candidate

    best_model = None
    best_dist = float('inf')

    # For simplicity, we support exactly one string variable here
    if len(soft_constraints) != 1:
        raise ValueError("This function currently supports exactly one string variable.")
    var_name, target = next(iter(soft_constraints.items()))

    for _ in range(num_samples):
        cand = random_edit(target)
        solver = Solver()
        for c in hard_constraints:
            solver.add(c)
        solver.add(ctx[var_name] == StringVal(cand))

        if solver.check() == sat:
            dist = Levenshtein.distance(cand, target)
            if dist < best_dist:
                best_dist = dist
                m = solver.model()
                best_model = {str(d): m[d] for d in m}

    return best_model

def find_maxsat_mixed_solution(hard_constraints, soft_constraints, ctx):
    """
    Try to find a solution using MaxSAT with soft constraints.
    Supports both numeric and string soft constraints.

    Args:
        hard_constraints: list of Z3 BoolRef (hard constraints)
        soft_constraints: dict mapping
            - variable_name (str) to target value (int, float, or str)
        ctx: dict mapping variable_name (str) to Z3 variable

    Returns:
        dict[str, Z3 value] if found, else None
    """
    opt = Optimize()
    # 1. add all hard constraints
    for c in hard_constraints:
        opt.add(c)

    # 2. add each soft constraint
    for var, target in soft_constraints.items():
        z3_var = ctx[var]
        if isinstance(target, str):
            # wrap string target in StringVal
            soft_c = (z3_var == StringVal(target))
        else:
            # assume numeric target
            soft_c = (z3_var == target)
        opt.add_soft(soft_c)

    # 3. solve MaxSAT
    if opt.check() == sat:
        m = opt.model()
        # return mapping var->value
        return { str(d): m[d] for d in m }
    else:
        return None


def find_maxsat_solution(hard_constraints, soft_constraints, ctx, random=False):
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
    #selec a random number from 0.5 to 1
    
    for var, value in soft_constraints.items():
        
        if random:
            random_factor = random.uniform(0.5, 1)
            value_low *= random_factor
            value_high = value * (2 - random_factor)
            soft_constr = eval(f"{var} >= {value_low}", {}, ctx)
            opt.add_soft(soft_constr)
            soft_constr = eval(f"{var} <= {value_high}", {}, ctx)
            opt.add_soft(soft_constr)
        else:
            
            soft_constr = eval(f"{var} == {value}", {}, ctx)
            opt.add_soft(soft_constr)

    if opt.check() == sat:
        m = opt.model()
        solution = {str(d): m[d] for d in m}
        return solution
    else:
        return None

from z3 import Solver, Int, Real, Abs, Or

def find_diverse_solutions(z3_constraints, max_solutions=5, start_distance=100, min_distance=1, decay_factor=0.5):
    solver = Solver()
    solver.add(z3_constraints)
    solutions = []
    current_distance = start_distance

    while len(solutions) < max_solutions and solver.check() == sat:
        model = solver.model()
        sol = {}
        distance_constraints = []

        for d in model:
            var_name = str(d)
            sort_name = model[d].sort().name()
            if sort_name == 'Int':
                val = model[d].as_long()
                sol[var_name] = val
                z3_var = Int(var_name)
                distance_constraints.append(Abs(z3_var - val) >= current_distance)
            elif sort_name == 'Real':
                val = float(model[d].as_decimal(10).rstrip('?'))
                sol[var_name] = val
                z3_var = Real(var_name)
                distance_constraints.append(Abs(z3_var - val) >= current_distance)
            else:
                # Keep as Z3 value (e.g., String)
                sol[var_name] = model[d]

        solutions.append(sol)

        solver.push()
        if distance_constraints:
            solver.add(Or(distance_constraints))

        if solver.check() != sat:
            solver.pop()
            current_distance = max(current_distance * decay_factor, min_distance)
            if current_distance == min_distance:
                break
        else:
            solver.pop()
            solver.add(Or(distance_constraints))

    return solutions



def find_diverse_solutions_v2(z3_constraints, max_solutions=5, percentage=0.2, min_distance=1.0, decay_factor=0.9):
    solver = Solver()
    solver.add(z3_constraints)
    solutions = []

    while len(solutions) < max_solutions and solver.check() == sat:
        model = solver.model()
        sol = {}
        distance_terms = []
        magnitude_sum = 0.0

        for d in model:
            var_name = str(d)
            sort_name = model[d].sort().name()

            if sort_name == 'Int':
                val = model[d].as_long()
                sol[var_name] = val
                z3_var = Int(var_name)
            elif sort_name == 'Real':
                val = float(model[d].as_decimal(10).rstrip('?'))
                sol[var_name] = val
                z3_var = Real(var_name)
            else:
                sol[var_name] = model[d]
                continue

            distance_terms.append(Abs(z3_var - val))
            magnitude_sum += abs(val)

        solutions.append(sol)

        # Compute scaled distance threshold based on magnitude
        scaled_distance = max(percentage * magnitude_sum, min_distance)

        # Add global diversity constraint
        solver.push()
        solver.add(Sum(distance_terms) >= scaled_distance)

        if solver.check() != sat:
            solver.pop()
            percentage *= decay_factor
            if percentage * magnitude_sum < min_distance:
                break
        else:
            solver.pop()
            solver.add(Sum(distance_terms) >= scaled_distance)

    return solutions

def get_diverse_median_solution_wrapper(z3_constraints, max_solutions=1, **kwargs):
    """
    Wrapper that returns the median solution when only one is requested.

    If max_solutions == 1:
        - Try to find 3 solutions, return the 2nd (median)
        - If 2 found, return the 2nd
        - If 1 found, return that
    Else:
        - Return list of solutions as usual
    """
    if max_solutions == 1:
        candidate_solutions = find_diverse_solutions_v2(
            z3_constraints, max_solutions=3, **kwargs
        )
        if len(candidate_solutions) >= 3:
            return [candidate_solutions[1]]
        elif len(candidate_solutions) == 2:
            return [candidate_solutions[1]]
        elif len(candidate_solutions) == 1:
            return [candidate_solutions[0]]
        else:
            return None
    else:
        return find_diverse_solutions_v2(
            z3_constraints, max_solutions=max_solutions, **kwargs
        )


def exclude_solution_from_constraints(z3_constraints, ctx, solution):
    """
    Adds a constraint to exclude a given solution from being returned again by Z3.

    Args:
        z3_constraints (list): Existing Z3 constraints (hard constraints).
        ctx (dict): Context with Z3 variable mappings.
        solution (dict): Dictionary of variable assignments to block (e.g., {'x': 3, 'y': 5}).

    Returns:
        tuple: (updated_constraints, updated_ctx)
    """
    exclusion_conditions = []

    for var_name, value in solution.items():

        exclusion_conditions.append(ctx[var_name] == value)

    if exclusion_conditions:
        exclusion_clause = Not(And(*exclusion_conditions))
        z3_constraints.append(exclusion_clause)

    return z3_constraints, ctx