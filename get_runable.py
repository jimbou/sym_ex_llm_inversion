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
           EXCEPT for the input variables of the difficult function, 
           which should instead be assigned to placeholders 
           named var_name_placeholder.
        b. Calls the difficult function.

2. After the difficult function:
   - Add a printf statement that prints the output variable(s) in this format:
     ###RESULT### variable1=value1 variable2=value2

3. Immediately after printf:
   - Insert exit(0); to terminate the program.

IMPORTANT:
- Use correct C types and format specifiers (e.g., %d, %f).
- Return ONLY valid, compilable C code — no explanations, no comments.
- Ensure the placeholders follow exactly this format: var_name_placeholder.
- Keep the code minimal: only the includes, the difficult function, 
  the minimal required main(), and necessary context.

Example placeholder assignment:
    double x = x_placeholder;
"""


# Parses the model response to see if it responded True or False

def extract_correctness_from_response(response_content: str) -> str:
    pattern = r"Correctness:\s*\*\*(.*?)\*\*|Correctness:\s*(True|False)"
    match = re.findall(pattern, response_content)
    if match:
        if match[-1][0]:
            return match[-1][0].strip()
        elif match[-1][1]:
            return match[-1][1].strip()
    return response_content


import re

def extract_input_pairs(response_text):
    """
    Parses LLM response and extracts input variable-value pairs.
    Returns a dictionary {variable: value}.
    """
    pattern = r'@@@(\w+)\s+([-+]?\d+(?:\.\d+)?)@@@'
    matches = re.findall(pattern, response_text)
    
    if not matches:
        raise ValueError("No input pairs found in the response.")

    inputs = {var.strip(): float(val) if '.' in val else int(val) for var, val in matches}
    return inputs

def save_c_code(response, output_file):
    """
    Saves the LLM response as a C source file.

    Args:
        response (str): The LLM-provided C code.
        output_file (str or Path): Path where the .c file will be saved.
    """
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


# This function handles the core logic for checking program correctness using a naive entailment approach.
def get_modified_script(model, code, full_code, log_folder, input_values):
    prompt = PROMPT.format(full_c_code=full_code,
                            difficult_c_code=code)
    
    response = model.query(prompt)
    modified_c_code = f"{log_folder}/modified_code.c"
    modified_c_code_concrete = f"{log_folder}/modified_code_concrete.c"
    save_c_code(response, modified_c_code)
    print(f"Modified C code saved to {modified_c_code}")
    apply_input_values(modified_c_code, modified_c_code_concrete, input_values)
    result =compile_run_parse(modified_c_code_concrete)
    return result


# TBD: WHAT OTHER APPROACH CAN BE USED OTHER THAN NAIVE?