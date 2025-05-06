import argparse
import os
from z3_scripts import parse_to_z3, read_constraints, find_diverse_solutions, add_fixed_values_z3_constraints, find_maxsat_solution
from model import get_model
from get_inverted_solutions import inverted_solutions_simple
from check_input import get_modified_script
from get_IO_vars import get_io_vars
import random
import subprocess
import re

def setup_log_folder(log_folder=None):
    """
    Ensure the log folder exists; default to 'log_temp' if not provided.
    """
    if log_folder is None:
        log_folder = 'log_temp'
    if not os.path.exists(log_folder):
        os.makedirs(log_folder)
        print(f"[INFO] Created log folder: {log_folder}")
    else:
        print(f"[INFO] Using existing log folder: {log_folder}")
    return log_folder

def generate_script_copies(input_vars, input_values, script_path, index=0):
    with open(script_path, 'r') as f:
        code = f.read()

    
    for var in input_vars:
        if var not in input_values:
            raise ValueError(f"Value for variable '{var}' not provided in input_values dictionary")

        # Replace placeholder
        placeholder = f"{var}_placeholder"
        value = str(input_values[var])
        modified_code = code.replace(placeholder, value)
        code =modified_code

        # Create output filename
    #output dir is the same dir where the script path is
    output_dir = os.path.dirname(script_path)
    output_file = os.path.join(output_dir, f"script_{index}.c")

        # Write modified code
    with open(output_file, 'w') as f_out:
        f_out.write(modified_code)

    print(f"Generated: {output_file}")
    index += 1
    return index, output_file



def compile_and_run_c_script(script_path, output_exe='a.out'):
    # Compile the C file
    compile_cmd = ['gcc', script_path, '-o', output_exe, '-lm']
    compile_result = subprocess.run(compile_cmd, capture_output=True, text=True)
    if compile_result.returncode != 0:
        raise RuntimeError(f"Compilation failed:\n{compile_result.stderr}")
    
    # Run the executable
    run_result = subprocess.run([f'./{output_exe}'], capture_output=True, text=True)
    if run_result.returncode != 0:
        raise RuntimeError(f"Execution failed:\n{run_result.stderr}")
    
    # Parse output: look for lines like var = value or var=value
    output = run_result.stdout
    var_pattern = re.compile(r'(\w+)\s*=\s*([^\s]+)')
    parsed_vars = {}
    for match in var_pattern.finditer(output):
        var_name, var_value = match.groups()
        parsed_vars[var_name] = var_value
    
    return parsed_vars


def main():

    parser = argparse.ArgumentParser(description="LLM-assisted symbolic execution orchestrator")

    parser.add_argument('--difficult_func', required=True,
                        help='Path to C file containing the difficult function (g)')
    parser.add_argument('--full_code', required=True,
                        help='Path to C file containing the whole program')
    parser.add_argument('--pre_constraints', required=True,
                        help='Path to file containing pre-constraints (for MAXSAT)')
    parser.add_argument('--post_constraints', required=True,
                        help='Path to file containing post-constraints (for MAXSAT)')
    parser.add_argument('--log_folder', required=False,
                        help='Path to log folder (optional, default: log_temp)')
    args = parser.parse_args()

    #read the difficult function
    difficult_func_path = args.difficult_func
    with open(difficult_func_path, 'r') as file:
        difficult_func = file.read()
    
    #read the full code
    full_code_path = args.full_code
    with open(full_code_path, 'r') as file:
        full_code = file.read()

    #read the pre-constraints
    pre_constraints_path = args.pre_constraints
    with open(pre_constraints_path, 'r') as file:
        pre_constraints = file.read()

    #read the post-constraints
    post_constraints_path = args.post_constraints
    with open(post_constraints_path, 'r') as file:
        post_constraints = file.read()

    
    log_folder = setup_log_folder(args.log_folder)

    # For now just print the setup — this is where the pipeline steps will hook in
    print(f"[SETUP]")
    print(f"Difficult function file: {difficult_func_path}")
    print(f"Full C code file: {full_code_path}")
    print(f"Pre-constraints file: {pre_constraints_path}")
    print(f"Post-constraints file: {post_constraints_path}")
    print(f"Log folder: {log_folder}")

    #actual start of the pipeline
    constraints_post_raw = read_constraints(post_constraints_path)
    z3_constraints_post, ctx_post = parse_to_z3(constraints_post_raw)
    print(f"[INFO] Parsed Z3 constraints for post: {z3_constraints_post}")
    solutions_post = find_diverse_solutions(z3_constraints_post, max_solutions=5)
    print("Found solutions:")
    for sol in solutions_post:
        print(sol)

    constraints_pre_raw = read_constraints(pre_constraints_path)
    z3_constraints_pre, ctx_pre = parse_to_z3(constraints_pre_raw)
    print(f"[INFO] Parsed Z3 constraints for pre: {z3_constraints_pre}")
    solutions_pre = find_diverse_solutions(z3_constraints_pre, max_solutions=1)
    print("Found solutions:")
    for sol in solutions_pre:
        print(sol)
    
    
    
    #create the model
    model = get_model("ali/deepseek-v3", 0.5, log_folder)

    #get io_vars
    inputs, outputs = get_io_vars(model, difficult_func, full_code, log_folder, solutions_pre[0], solutions_post[0])


    modified_script_path = os.path.join(log_folder, "modified_script.c")    
    get_modified_script(model, difficult_func, full_code, modified_script_path, solutions_pre[0], inputs)
    index =0
    #RANDOMISE THE ORDER OF SOLUTIONS_POST  
    
    solutions_post = random.sample(solutions_post, len(solutions_post))
    for solution in solutions_post:
        print(f"Solution: {solution}")
        #for every output var in outputs get the value from the solution and create a string
        solution_str =""
        for var in outputs:
            if var not in solution:
                raise ValueError(f"Value for variable '{var}' not provided in solution dictionary")
            # Replace placeholder
            value = str(solution[var])
            solution_str += f"{var}={value}\n"
        #for the output vars outputs we need to get their values from the 
        inputs_concrete= inverted_solutions_simple(model, difficult_func, solution_str)
        print(f"the inputs are {inputs_concrete}")
        # #find constraints
    
   
    
        index, c_new_file = generate_script_copies(inputs, inputs_concrete, modified_script_path, index)

        runned_vars = compile_and_run_c_script(c_new_file)
        print(f"Runned vars: {runned_vars}")
        z3_constraints_post_updated, ctx_post_updated = add_fixed_values_z3_constraints(z3_constraints_post, runned_vars, ctx_post)
        print(f"Z3 constraints after adding fixed values: {z3_constraints_post_updated}")
        print(f"Context after adding fixed values: {ctx_post_updated}")
        solutions_post_updated = find_diverse_solutions(z3_constraints_post_updated, max_solutions=1)  
        #if no solution is found gop to the nest loop iteration
        if len(solutions_post_updated) == 0:
            print("No solution found")
            continue     
        else :
            print(f"Found a solution {solutions_post_updated[0]}")

        #now enhance the precondition to see if the pre constraints hold
        z3_constraints_pre_updated, ctx_pre_updated = add_fixed_values_z3_constraints(z3_constraints_pre, inputs_concrete, ctx_pre)
        print(f"Z3 constraints after adding fixed values: {z3_constraints_pre_updated}")
        print(f"Context after adding fixed values: {ctx_pre_updated}")
        solutions_pre_updated = find_diverse_solutions(z3_constraints_pre_updated, max_solutions=1)  
        #if no solution is found gop to the nest loop iteration
        if len(solutions_pre_updated) == 0:
            print("No solution found")
            sol_maxsat = find_maxsat_solution(z3_constraints_pre, inputs_concrete, ctx_pre)
            print(f"MaxSAT solution: {sol_maxsat}")  
        else :
            print(f"Found a solution {solutions_pre_updated[0]}")


if __name__ == "__main__":
    
    main()
