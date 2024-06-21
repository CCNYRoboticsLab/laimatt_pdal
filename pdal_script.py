import subprocess
import csv
import pandas as pd
import laspy
import glob
import mysql.connector
import os
import sys
import shutil

def csvToLas(test_dir, length):
    path = test_dir + "/component_las_" + test_dir
    os.makedirs(path)
        
    for x in range(length):
        command = [
            "pdal",
            "translate",
            test_dir + "/component_csv/component_" + f"{x:06d}" + ".csv",
            path + "/component_" + f"{x:06d}" + ".las"
        ]
        result = subprocess.run(command, capture_output=True, text=True, check=True)
    
def lasToCsv(test_dir, min_p, tolerance, max_p):
    command = [
        "pdal",
        "translate",
        "3sections - 170 - 253.las",
        test_dir + "/full_segmented.csv",
        "-f",
        "filters.cluster",
        "--filters.cluster.min_points=" + str(min_p),
        "--filters.cluster.tolerance=" + str(tolerance),
        "--filters.cluster.max_points=" + str(max_p) 
    ]
    result = subprocess.run(command, capture_output=True, text=True, check=True)
    
    csv_file = test_dir + "/full_segmented.csv"

    df = pd.read_csv(csv_file)
    df_sorted = df.sort_values(by="ClusterID", ascending=True)
    df_sorted.to_csv(csv_file, index=False)

def create_csvs(test_dir):
    index = 0
    csv_file = test_dir + "/full_segmented.csv"
    folder_path = test_dir + "/component_csv"
    os.makedirs(folder_path)
    with open(csv_file, 'r') as file:
        reader = csv.reader(file)
        header = next(reader)
        last_col = len(header) - 1
        previous_value = 0

        csvoutput = open(folder_path + '/component_000000.csv', 'w', newline='')
        writer = csv.writer(csvoutput)
        writer.writerow(header)

        for row in reader:
        # Get the value from the specified column
            current_value = int(float(row[last_col]))   

            # If the value is different from the previous value, start a new row
            if current_value != previous_value:
                csvoutput.close()
                csvoutput = open(folder_path + '/component_' + f"{current_value:06d}" + '.csv', 'w', newline='')
                writer = csv.writer(csvoutput)
                writer.writerow(header)
                
                index += 1
                previous_value = current_value
            else:
                # Otherwise, add the row to the current row
                writer.writerow(row)
        csvoutput.close()

    return index

    
def bounding_box_info(las_file_path):
    with laspy.open(las_file_path) as f:
        x_min, x_max = f.header.x_min, f.header.x_max        
        y_min, y_max = f.header.y_min, f.header.y_max
        z_min, z_max = f.header.z_min, f.header.z_max
        
        center_x = (x_min + x_max) / 2
        center_y = (y_min + y_max) / 2
        center_z = (z_min + z_max) / 2 
        length = x_max - x_min
        width = y_max - y_min
        height = z_max - z_min
        
        return [center_x, center_y, center_z, length, width, height]
    
def populate_db(test_dir):
    # mydb = mysql.connector.connect(
    #     host="localhost",
    #     user="root",  # Your MySQL username
    #     password="",  # Your MySQL password (if any)
    #     port=3308,  # Your MySQL port
    #     unix_socket="/opt/lampp/var/mysql/mysql.sock"
    # )
    # cursor = mydb.cursor()
    # cursor.execute("USE sample")
    

    for filepath in sorted(glob.iglob(test_dir + '/component_las_' + test_dir + '/*')):
        b = bounding_box_info(filepath)
        query = "INSERT INTO patch_crack (center_lat, center_long, center_alt, box_length, box_width, box_height, type, file_path_las) " + \
            "VALUES ('%s', '%s', '%s', '%s', '%s', '%s', 3, %s)"
        data = (b[0], b[1], b[2], b[3], b[4], b[5], filepath)
        print(query, data)
        # cursor.execute(query, data)
        # mydb.commit()

    # Close the connection when done
    # mydb.close()
    
def populate_csv(test_dir):
    csvoutput = open(test_dir + '/component_data.csv', 'w', newline='')
    writer = csv.writer(csvoutput)
    writer.writerow(['x', 'y', 'z', 'length', 'width', 'height', 'type', 'original file'])
    
    for filepath in sorted(glob.iglob(test_dir + '/component_las_' + test_dir + '/*')):
        box_info = bounding_box_info(filepath)
        writer.writerow(box_info + ['crack', filepath])
    
    csvoutput.close()
        
min_p = 23
tolerance = .5
max_p = 100

if len(sys.argv) > 3:
    min_p = int(sys.argv[1])
    tolerance = float(sys.argv[2])
    max_p = int(sys.argv[3])

if not (os.path.exists("tests")):
    os.makedirs("tests")

test_dir = "tests/test_"+ str(min_p) + "_" + str(tolerance) + "_" + str(max_p)
if os.path.exists(test_dir):
    print(test_dir + " already exists, remaking")
    shutil.rmtree(test_dir)
os.makedirs(test_dir)



lasToCsv(test_dir, min_p, tolerance, max_p)
index = create_csvs(test_dir)
csvToLas(test_dir, index + 1)

populate_db(test_dir)
populate_csv(test_dir)

