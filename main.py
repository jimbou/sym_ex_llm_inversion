import argparse
import os
from z3_scripts import parse_to_z3, read_constraints, find_diverse_solutions,  find_diverse_solutions_v2,add_fixed_values_z3_constraints, find_maxsat_solution, exclude_solution_from_constraints, get_diverse_median_solution_wrapper, find_numeric_min_solution
from model import get_model
from get_inverted_solutions import inverted_solutions_simple
from get_inversion import invert_code
from check_input import get_modified_script
from get_IO_vars import get_io_vars, get_total_vars
from get_inital_seed import get_inital_seed
from helper_functions import setup_log_folder, generate_script_copies, compile_and_run_c_script
import random
import subprocess
import re

def create_log_folders_and_models(log_folder,model_type):
    log_folder_total= os.path.join(log_folder, "total_vars")
    if not os.path.exists(log_folder_total):
        os.makedirs(log_folder_total)
        print(f"[INFO] Created log folder: {log_folder_total}")
    else:
        print(f"[INFO] Using existing log folder: {log_folder_total}")
    #create the model
    model_total = get_model(model_type, 0.5, log_folder_total)
    #input output log folder
    log_folder_io= os.path.join(log_folder, "io_vars")
    if not os.path.exists(log_folder_io):
        os.makedirs(log_folder_io)
        print(f"[INFO] Created log folder: {log_folder_io}")
    else:
        print(f"[INFO] Using existing log folder: {log_folder_io}")
    #create the model
    model_io = get_model(model_type, 0.5, log_folder_io)

    #inverted solutions log folder
    log_folder_inverted= os.path.join(log_folder, "inverted_solutions")
    if not os.path.exists(log_folder_inverted):
        os.makedirs(log_folder_inverted)
        print(f"[INFO] Created log folder: {log_folder_inverted}")
    else:
        print(f"[INFO] Using existing log folder: {log_folder_inverted}")

    #create the model
    model_inverted = get_model(model_type, 0.5, log_folder_inverted)

    #create the folder for intial seed
    log_folder_seed= os.path.join(log_folder, "seed")
    if not os.path.exists(log_folder_seed):
        os.makedirs(log_folder_seed)
        print(f"[INFO] Created log folder: {log_folder_seed}")
    else:
        print(f"[INFO] Using existing log folder: {log_folder_seed}")
    model_seed = get_model(model_type, 0.5, log_folder_seed)

    #create the folder for modified code
    log_folder_modified= os.path.join(log_folder, "modified_script")
    if not os.path.exists(log_folder_modified):
        os.makedirs(log_folder_modified)
        print(f"[INFO] Created log folder: {log_folder_modified}")
    else:
        print(f"[INFO] Using existing log folder: {log_folder_modified}")

    model_modified = get_model(model_type, 0.5, log_folder_modified)

    return model_total, model_io, model_inverted, model_seed, model_modified, log_folder_total, log_folder_io, log_folder_inverted, log_folder_modified


def check_constraints_with_fallback(z3_constraints, ctx, inputs_concrete, types_dict, max_solutions=1):
    """
    Checks if the constraints are satisfiable with the given concrete inputs.
    If satisfiable, returns the solution and True.
    If not, performs MaxSAT refinement and returns the refined solution and False.

    Args:
        z3_constraints (list): List of Z3 constraint expressions.
        ctx (dict): Context dictionary for Z3 variables.
        inputs_concrete (dict): Concrete inputs to fix in the constraints.
        types_dict (dict): Dictionary of types for the inputs.
        max_solutions (int): Max number of diverse solutions to search for (default 1).

    Returns:
        tuple: (solution_dict, is_satisfiable)
    """
    # Add fixed values to constraints
    z3_constraints_updated, ctx_updated = add_fixed_values_z3_constraints(z3_constraints, inputs_concrete, ctx, types_dict)
    print(f"Z3 constraints after adding fixed values: {z3_constraints_updated}")
    print(f"Context after adding fixed values: {ctx_updated}")

    # Try to find a solution
    solutions = get_diverse_median_solution_wrapper(z3_constraints_updated, max_solutions=max_solutions)
    #if the solutions is none or empty we should go to maxsat
    if not solutions or len(solutions) == 0:
        print("No solution found using standard SAT solving.")
        sol_maxsat = find_numeric_min_solution(z3_constraints, inputs_concrete, ctx)
        print(f"MaxSAT solution: {sol_maxsat}")
        return sol_maxsat, False
    else:
        print(f"Found a solution: {solutions[0]}")
        return solutions[0], True



def main():
    retries_max = 5
    retries_internal =3
    retries_potential= 3
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
    parser.add_argument('--model', required=False,
                        help='Model to use (optional, default: deepseek-v3-aliyun)')
    args = parser.parse_args()
    # Check if the model argument is provided, otherwise use the default
    if args.model:
        model_type = args.model
    else:
        model_type = "deepseek-v3-aliyun"

    # Check if the log folder argument is provided, otherwise use the default
    if args.log_folder:
        log_folder = args.log_folder
    else:
        log_folder = 'log_temp'
    log_folder = setup_log_folder(args.log_folder)

  
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

    
    #create all the log folfders and models
    model_total, model_io, model_inverted, model_seed, model_modified, log_folder_total, log_folder_io, log_folder_inverted, log_folder_modified = create_log_folders_and_models(log_folder, model_type)
    total_vars =get_total_vars(model_total,  full_code)
    #get the total vars
    #Read the post constraints and parse them to z3 
    constraints_post_raw = read_constraints(post_constraints_path)
    z3_constraints_post, ctx_post = parse_to_z3(constraints_post_raw, total_vars)
    print(f"[INFO] Parsed Z3 constraints for post: {z3_constraints_post}")
    # find  solutions for the post constraints
    solutions_post = get_diverse_median_solution_wrapper(z3_constraints_post, max_solutions=5)
    print("Found solutions:")
    for sol in solutions_post:
        print(sol)
    #randomise the post solutions
    solutions_post = random.sample(solutions_post, len(solutions_post))

    #Read the pre constraints and parse them to z3
    constraints_pre_raw = read_constraints(pre_constraints_path)
    z3_constraints_pre, ctx_pre = parse_to_z3(constraints_pre_raw, total_vars)
    print(f"[INFO] Parsed Z3 constraints for pre: {z3_constraints_pre}")
    # find  solutions for the pre constraints
    solutions_pre = get_diverse_median_solution_wrapper(z3_constraints_pre, max_solutions=1)
    print("Found solutions:")
    for sol in solutions_pre:
        print(sol)
    #randomise the pre solutions, currently not needed since there is only 1 solution
    if len(solutions_pre) > 1:
        solutions_pre = random.sample(solutions_pre, len(solutions_pre))
    

    

    #get io_vars as a list of tuples
    inputs_with_type, outputs_with_type = get_io_vars(model_io, difficult_func, full_code, log_folder, solutions_pre[0], solutions_post[0])

    # get just the inputs and outputs without the types
    inputs = [var for var, _ in inputs_with_type]
    outputs = [var for var, _ in outputs_with_type]

    # Create dictionaries for inputs and outputs with their types
    inputs_dict = {var: var_type for var, var_type in inputs_with_type}
    outputs_dict = {var: var_type for var, var_type in outputs_with_type}

    #print the inputs and outputs dict in nice format
    for var, var_type in inputs_dict.items():
        print(f"Input variable: {var}, Type: {var_type}")
    for var, var_type in outputs_dict.items():
        print(f"Output variable: {var}, Type: {var_type}")


    #get one solution from the pre and post solutions
    solutions_pre_0 = solutions_pre.pop(0)
    #find a solution for only the inputs
    inputs_subset = {var: solutions_pre_0[var] for var in inputs if var in solutions_pre_0}
    print(f"Subset of pre-solution for inputs: {inputs_subset}")

    #do the same for the solutions_post
    #i wanna find the median solution of the available , meaning the solution in the middle of the list if we were to sort it
    #sort the solutions_post by the first output var
    #sort the solutions_post by the first output var
    solutions_post.sort(key=lambda x: x[outputs[0]])
    #get the median solution
    median_index = len(solutions_post) // 2
    solutions_post_0 = solutions_post[median_index]
    #remove the median from the list and then randomise it 
    solutions_post = [sol for sol in solutions_post if sol != solutions_post_0]
    #randomise the post solutions
    
    #find a solution for only the outputs
    outputs_subset = {var: solutions_post_0[var] for var in outputs if var in solutions_post_0}
    print(f"Subset of post-solution for outputs: {outputs_subset}")

    
    #get the inverted solutions and store them in the log folder inverted in the file inverted_solution.c
    invert_code(model_inverted, difficult_func,  inputs_dict, outputs_dict, log_folder_inverted)
    inverted_script_path = os.path.join(log_folder_inverted, "inverted_solution.c")
    
    #get an initial seed of input values  
    # inital_seed = get_inital_seed(model_seed, difficult_func, inputs_dict, outputs_dict, pre_constraints, post_constraints, inputs_subset, outputs_subset)
    # print(f"Initial seed: {inital_seed}")
    

    index_back =0
    index_back, c_back_new_file = generate_script_copies(outputs, outputs_subset, inverted_script_path, index_back)
    inital_seed= compile_and_run_c_script(c_back_new_file, output_exe='inverted.out')
    print(f"Initial seed: {inital_seed}")
    
    
    #get the modified script from the model, this is a runnable version with the inputsand outputs as placeholders
    modified_script_path = os.path.join(log_folder_modified, "modified_script.c")    
    get_modified_script(model_modified, difficult_func, full_code, modified_script_path, solutions_pre_0, inputs)
    
    # here we should test if the inputs concrete satisfy the pre if not maxsat to extract some that satisfy (1)
    initial_solution, sat_pre =check_constraints_with_fallback(z3_constraints_pre, ctx_pre, inital_seed, inputs_dict)
    
    #if the initial seed does not satisfy the pre constraints we should exclude it in the pre from now on
    if not sat_pre:
        z3_constraints_pre, ctx_pre = exclude_solution_from_constraints(z3_constraints_pre, ctx_pre, inital_seed)
        print(f"Initial seed does not satisfy pre constraints, excluding it from the constraints")
    print(f"Initial solution: {initial_solution}")
    #index_forward is the current index of the script copies and retries is the number of retries of finding a solution, index_back is the index of the script copies for the backward search
    index_forward =0
    
    
    explore_potential =0
    while explore_potential< retries_potential:
        explore_potential += 1
        #the loop of going back and forth between pre and post
        retries =0
        while retries < retries_max:
            retries += 1
            print(f"Retry {retries}/{retries_max}")

            #keep only from the initial solution the inputs
            initial_solution = {var: initial_solution[var] for var in inputs if var in initial_solution}

            ## then we run it  on the code get outpt (2)
            index_forward, c_new_file = generate_script_copies(inputs, initial_solution, modified_script_path, index_forward)
            runned_vars = compile_and_run_c_script(c_new_file)
            print(f"Runned vars: {runned_vars}")

            ## see if the output satisfies post, if not then maxsat (3)
            initial_post_solution, sat_post =check_constraints_with_fallback(z3_constraints_post, ctx_post, runned_vars, outputs_dict)
            if sat_post:
                print(f"found solution that satisfies pre and post {initial_solution}")
                return initial_solution
            
            #exclude the solution from the post constraints
            z3_constraints_post, ctx_post = exclude_solution_from_constraints(z3_constraints_post, ctx_post, initial_post_solution)
            ## get the candidate and invert
            retries_inversion =0
            
            while retries_inversion < retries_internal :
                retries_inversion+=1
                print(f"Solution for post though maxsat: {initial_post_solution}")
                #for every output var in outputs get the value from the solution and create a string
                solution_str =""
                for var in outputs:
                    if var not in initial_post_solution:
                        raise ValueError(f"Value for variable '{var}' not provided in solution dictionary")
                    # Replace placeholder
                    value = str(initial_post_solution[var])
                    solution_str += f"{var}={value}\n"
                #for the output vars outputs we need to get their values from the 
                if retries_inversion // 2 == 0:
                    index_back, c_back_new_file = generate_script_copies(outputs, initial_post_solution, inverted_script_path, index_back)
                    inputs_concrete= compile_and_run_c_script(c_back_new_file, output_exe='inverted.out')
                    print(f"I used the inverted script to get the inputs {inputs_concrete}")
                else:
                    inputs_concrete= inverted_solutions_simple(model_inverted, difficult_func, solution_str,  inputs_dict, outputs_dict)
                    print(f"I used the llm inversion to get the inputs {inputs_concrete}")
                #here we need to change instead of finding maxsat if the reversion was not very successful to get retries with feedback
                print(f"the inputs from reversion are {inputs_concrete}")
                ## get the inputs , and (1) , (2), (3)
                index_forward, c_new_file = generate_script_copies(inputs, inputs_concrete, modified_script_path, index_forward)

                runned_vars = compile_and_run_c_script(c_new_file)
                current_post_solution, current_sat_post = check_constraints_with_fallback(z3_constraints_post, ctx_post, runned_vars, outputs_dict)

                print(f"Runned vars: {runned_vars}")
                print(f"current post solution: {current_post_solution} and sat post {current_sat_post}")
                if current_sat_post:
                    break
                else:
                    initial_post_solution=current_post_solution
                    #exclude the solution from the post constraints
                    z3_constraints_post, ctx_post = exclude_solution_from_constraints(z3_constraints_post, ctx_post, runned_vars)
            #if it is not sat we should have feedback to get another solution TBA
            
            current_pre_solution, current_sat_pre = check_constraints_with_fallback(z3_constraints_pre, ctx_pre, inputs_concrete, inputs_dict)
            if current_sat_pre and current_sat_post:
                print(f"pre is also satisfied . this is good solution {inputs_concrete}")
                return inputs_concrete
            #go back to the loop
            #exlude the solution from the pre constraints
            z3_constraints_pre, ctx_pre = exclude_solution_from_constraints(z3_constraints_pre, ctx_pre, inputs_concrete)
            initial_solution = current_pre_solution
            print(f"this solution {current_pre_solution} satisfies pre so we can check if it satisfies post too")

       
            print(f"this solution {runned_vars} does not satisfy post and we have trouble inverting from maxsat")  
            #lets pop another candidate inout 
           
        
        if len(solutions_post) == 0:
            print ("could not find a solution that satisfies pre and post")
            return
        
        solutions_post.sort(key=lambda x: x[outputs[0]])
        #get the median solution
        median_index = len(solutions_post) // 2
        solutions_post_new = solutions_post[median_index]
        #remove the median from the list and then randomise it 
        solutions_post = [sol for sol in solutions_post if sol != solutions_post_new]
        #randomise the post solutions
        
        #find a solution for only the outputs
        outputs_subset = {var: solutions_post_new[var] for var in outputs if var in solutions_post_new}
        print(f"Subset of post-solution for outputs: {outputs_subset}")

        
        index_back, c_back_new_file = generate_script_copies(outputs, outputs_subset, inverted_script_path, index_back)
        inital_seed= compile_and_run_c_script(c_back_new_file, output_exe='inverted.out')
        print(f"Initial seed: {inital_seed}")
        
        
        # here we should test if the inputs concrete satisfy the pre if not maxsat to extract some that satisfy (1)
        initial_solution, sat_pre = check_constraints_with_fallback(z3_constraints_pre, ctx_pre, inital_seed, inputs_dict)
            #else : go back to the loop with current solution pre as the current sol
        print(f"I am here with the pre solution {initial_solution} and sat pre {sat_pre} an d i am gonna try again with explore potential {explore_potential}")

if __name__ == "__main__":
    
    main()
