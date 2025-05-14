
import os
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