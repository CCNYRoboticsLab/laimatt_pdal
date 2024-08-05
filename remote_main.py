import subprocess

script_path = '/home/roboticslab/Developer/image2overlays/main.py'
working_directory = '/home/roboticslab/Developer/image2overlays'

# # Run the script in the specified directory
# result = subprocess.run(['python', script_path], cwd=working_directory, capture_output=True, text=True)

# # Print the command's output
# print('STDOUT:', result.stdout)
# print('STDERR:', result.stderr)

process = subprocess.Popen(['python', script_path], cwd=working_directory, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)

# Read the output in real-time
for line in process.stdout:
    print('STDOUT:', line.strip())

# Read any error output (if needed)
for line in process.stderr:
    print('STDERR:', line.strip())

# Wait for the process to complete
process.wait()