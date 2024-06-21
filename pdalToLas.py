import subprocess

for x in range(22):
    command = [
        "pdal",
        "translate",
        "component_csv/data_" + str(x) + ".csv",
        "component_las/lasdata_" + str(x) + ".las"
    ]
    result = subprocess.run(command, capture_output=True, text=True, check=True)
