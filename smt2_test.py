from z3 import *

def bytes_to_int(bytevals):
    """Reconstruct a 32-bit integer from a list of 4 Z3 bytes (low to high order)."""
    return sum((b.as_long() << (8 * i)) for i, b in enumerate(bytevals))

def get_symbolic_arrays(smt_ast):
    """Extract declared symbolic array names from the AST."""
    arrays = []
    for decl in smt_ast:
        if isinstance(decl, FuncDeclRef):
            # Check if it's an array: (_ BitVec 32) -> (_ BitVec 8)
            domain = decl.domain()
            range_ = decl.range()
            if domain == BitVecSort(32) and range_ == BitVecSort(8):
                arrays.append(decl.name())
    return arrays

def extract_array_value(model, array_name, num_bytes=4):
    """Extract byte values from a symbolic array in the model."""
    array = Const(array_name, ArraySort(BitVecSort(32), BitVecSort(8)))
    return [model[Select(array, BitVecVal(i, 32))] for i in range(num_bytes)]

# Parse the SMT2 file
filename = "/home/jim/sym_ex_llm_inversion/smt_example.smt2"
smt_ast = parse_smt2_file(filename)
print("Parsed SMT AST:", smt_ast)
# Solve
solver = Solver()
solver.add(smt_ast)
if solver.check() != sat:
    print("UNSAT")
    exit()
else :
    print("SAT")
    # Get the model
    model = solver.model()
    print("Model:", model)

# Dynamically find and extract values
symbolic_arrays = get_symbolic_arrays(smt_ast)
for name in symbolic_arrays:
    bytevals = extract_array_value(model, name)
    if None in bytevals:
        print(f"Variable '{name}' has undefined bytes — skipping")
        continue
    int_val = bytes_to_int(bytevals)
    print(f"{name} =", int_val)
