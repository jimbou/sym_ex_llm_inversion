import re
import shutil
from pathlib import Path
import subprocess

PROMPT = """
You are given:

1. The full C code:
{full_c_code}

2. The isolated difficult function or code block:
{difficult_c_code}

3. A set of initial variable assignments (context) needed to reach the difficult function:
{pre_assignments}

Your task is to generate a minimal, compilable C program that:

1. Includes:
   - All necessary includes (e.g., stdio.h, math.h).
   - The difficult function.
   - A main() function that:
        a. Defines and assigns all required variables from the initial assignments, 
        b. Calls the difficult function.

2. After the difficult function:
   - Add a printf statement that prints the output variable(s) in this format:
     ###RESULT### variable1=value1 variable2=value2

3. Immediately after printf:
   - Insert exit(0); to terminate the program.

IMPORTANT:
- Use correct C types and format specifiers (e.g., %d, %f).
- Return ONLY valid, compilable C code — no explanations, no comments.
- Keep the code minimal: only the includes, the difficult function, 
  the minimal required main(), and necessary context.
"""


# Parses the model response to see if it responded True or False
def clean_llm_c_response(llm_response):
    """
    Cleans the LLM response to extract only the valid C code.
    - Removes anything before the first line that looks like C code.
    - Removes anything after the last closing brace '}'.
    """
    lines = llm_response.strip().splitlines()

    # Find first line that looks like C code (starts with #include, int, void, double, etc.)
    c_keywords = ['#include', 'int', 'void', 'double', 'float', 'char', 'long', 'short', 'unsigned']
    start_idx = None
    for idx, line in enumerate(lines):
        if any(line.strip().startswith(kw) for kw in c_keywords):
            start_idx = idx
            break

    if start_idx is None:
        raise ValueError("Could not find the start of C code in LLM response.")

    # Find last line with closing brace '}'
    end_idx = None
    for idx in reversed(range(len(lines))):
        if lines[idx].strip() == '}' or lines[idx].strip().endswith('}'):
            end_idx = idx
            break

    if end_idx is None:
        raise ValueError("Could not find the end of C code in LLM response.")

    # Extract the code slice
    clean_c_code = '\n'.join(lines[start_idx:end_idx + 1])

    # Remove leftover markdown artifacts like 'c' or ``` marks
    clean_c_code = re.sub(r'^c\s*', '', clean_c_code.strip(), flags=re.IGNORECASE)
    clean_c_code = clean_c_code.strip('`').strip()

    return clean_c_code


#I want a function that given a c code and 

def save_c_code(response, output_file):
    """
    Saves the LLM response as a C source file.

    Args:
        response (str): The LLM-provided C code.
        output_file (str or Path): Path where the .c file will be saved.
    """
    #if output file is not a pth
    if not isinstance(output_file, Path):
        output_file = Path(output_file)
    with output_file.open("w", encoding="utf-8") as f:
        f.write(response)


def apply_input_values(source_file, target_file, input_values):
    """
    Copies the C file and replaces placeholders like {var}_placeholder.

    Args:
        source_file (str or Path): Original C file.
        target_file (str or Path): New C file with replaced values.
        input_values (dict): e.g., {'x': 5, 'y': 10}
    """
    source_file = Path(source_file)
    target_file = Path(target_file)

    # Copy file first
    shutil.copy(source_file, target_file)

    # Replace placeholders in target file
    code = target_file.read_text()
    for var, value in input_values.items():
        placeholder = f"{var}_placeholder"
        code = re.sub(rf"\b{placeholder}\b", str(value), code)
    target_file.write_text(code)


def compile_run_parse(c_file, executable_name="a.out"):
    """
    Compiles the C file, runs it, and extracts ###RESULT### outputs.

    Args:
        c_file (str or Path): Path to the modified C file.
        executable_name (str): Name for the compiled binary.

    Returns:
        dict: Parsed output variables from program run.
    """
    c_file = str(c_file)

    # Compile the code
    compile_cmd = ["gcc", c_file, "-o", executable_name]
    compile_result = subprocess.run(compile_cmd, capture_output=True, text=True)
    if compile_result.returncode != 0:
        raise RuntimeError(f"Compilation failed:\n{compile_result.stderr}")

    # Run the binary
    run_cmd = [f"./{executable_name}"]
    run_result = subprocess.run(run_cmd, capture_output=True, text=True)
    if run_result.returncode != 0:
        raise RuntimeError(f"Execution failed:\n{run_result.stderr}")

    # Extract ###RESULT### line
    output = run_result.stdout
    match = re.search(r"###RESULT###(.*)", output)
    if not match:
        raise ValueError("No ###RESULT### line found in program output.")

    result_line = match.group(1).strip()
    result_pairs = re.findall(r"(\w+)=(\S+)", result_line)
    result_dict = {key: value for key, value in result_pairs}

    return result_dict

def replace_values_with_placeholders(c_code, variables):
    """
    Replaces variable assignments in the given C code with placeholders.
    
    Args:
        c_code (str): The C code as a string.
        variables (list): A list of variable names to replace with placeholders.
    
    Returns:
        str: Modified C code with placeholders.
    """
    lines = c_code.split('\n')
    modified_lines = []

    assignment_pattern = re.compile(r'^(\s*[a-zA-Z_][a-zA-Z0-9_\s\*]+)\s+({})\s*=\s*[^;]+;'.format('|'.join(variables)))

    for line in lines:
        match = assignment_pattern.match(line)
        if match:
            var_type = match.group(1)
            var_name = match.group(2)
            placeholder_line = f"{var_type} {var_name} = {var_name}_placeholder;"
            modified_lines.append(placeholder_line)
        else:
            modified_lines.append(line)

    return '\n'.join(modified_lines)

def solution_to_string(solution):
    return " ".join(f"{var}={value}" for var, value in solution.items())

# This function handles the core logic for checking program correctness using a naive entailment approach.
def get_modified_script(model, code, full_code, modified_script_path, pre_assignments, variables_to_replace):

    #pre assignment is a dict of variable, vallue pairs
    #turn it into string
    pre_assign_string=solution_to_string(pre_assignments)
    
    prompt = PROMPT.format(full_c_code=full_code,
                            difficult_c_code=code,
                            pre_assignments=pre_assign_string)
    
    print(f"Prompt: {prompt}")
    response = model.query(prompt)
    clean_response =clean_llm_c_response(response)
    clean_response=replace_values_with_placeholders(clean_response, variables_to_replace)
    
    print(f"Response: {clean_response}")  
    save_c_code(clean_response, modified_script_path)
    print(f"Modified C code saved to {modified_script_path}")
    # apply_input_values(modified_c_code, modified_c_code_concrete, input_values)
    # result =compile_run_parse(modified_c_code_concrete)
    return 


# TBD: WHAT OTHER APPROACH CAN BE USED OTHER THAN NAIVE?