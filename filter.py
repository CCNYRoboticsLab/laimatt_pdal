import subprocess
import laspy
import os
import shutil
import numpy as np
import laspy
import requests

def filter_points_laspy(file_path, output_file):
    # Open the LAS file
    in_file = laspy.read(file_path)

    # Extract RGB color information
    colors = np.vstack((in_file.red, in_file.green, in_file.blue)).T / 256.0

    # # Print the range of the RGB channels
    # print("Range of R channel:", np.min(colors[:, 0]), np.max(colors[:, 0]))
    # print("Range of G channel:", np.min(colors[:, 1]), np.max(colors[:, 1]))
    # print("Range of B channel:", np.min(colors[:, 2]), np.max(colors[:, 2]))

    # Define red condition: R > 0.8, G < 0.2, B < 0.2 (color values are in range 0 to 1)
    red_mask = (colors[:, 0] < 0.2) & (colors[:, 1] < 0.2) & (colors[:, 2] > 0.8)

    # Apply the mask to filter points and colors
    red_points = np.vstack((in_file.x, in_file.y, in_file.z)).T[red_mask]
    red_colors = (colors * 255)[red_mask].astype(np.uint16)
    red_info = np.hstack((red_points, red_colors))

    # Close the input LAS file
    
    print(red_mask)
    print(red_points)
    print(red_colors)
    print(in_file.header)
    print(red_info)

    # Create a new LAS file for the filtered points
    with laspy.open(output_file, mode='w', header=in_file.header) as out_writer:
        
        
        out_file = laspy.ScaleAwarePointRecord.zeros(red_info.shape[0], header=in_file.header)
        # Copy header and points data
        out_file.x = red_points[:, 0]
        out_file.y = red_points[:, 1]
        out_file.z = red_points[:, 2]


        # Update color information
        out_file.red = red_colors[:, 0]
        out_file.green = red_colors[:, 1]
        out_file.blue = red_colors[:, 2]
        
        out_writer.write_points(out_file)

    print(f"Filtered LAS file saved to {output_file}")

def download_file(url, save_path):
    token = authenticate()
    headers = {'Authorization': 'JWT {}'.format(token)}
    # Send a GET request to the URL
    response = requests.get(url, headers=headers)
    
    # Check if the request was successful (status code 200)
    if response.status_code == 200:
        # Open a file in binary write mode ('wb') and write the content of the response
        with open(save_path, 'wb') as f:
            f.write(response.content)
        print(f"File downloaded successfully and saved to: {save_path}")
    else:
        print(f"Failed to download file. Status code: {response.status_code}")
    
def lazTolas(laz, las):
    command = [
            "pdal",
            "translate",
            laz,
            las
        ]
    result = subprocess.run(command, capture_output=True, text=True, check=True)
    
def authenticate():
    url = "http://localhost:8000/api/token-auth/"
    data = {
        "username": "authentication",
        "password": "authkeyword"
    }
    response = requests.post(url, data=data)
    return response.json()['token']

def filter_from_webodm(project_id, task_id):
    # webodm_path = '/var/lib/docker/volumes/webodm_appmedia/_data/project/{}/task/{}/assets/'.format(project_id, task_id) + 'ccny_postprocessing' 
    # if not os.path.exists(webodm_path):
    #     # Create the directory
    #     os.makedirs(webodm_path)
    
    task_path = 'tasks/task_{}_{}'.format(project_id, task_id) 
    
    if os.path.exists(task_path):
        print(task_path + " already exists, remaking")
        shutil.rmtree(task_path)
    os.makedirs(task_path)

    input_file = task_path + '/original_model.laz'  # Replace with your input LAS/LAZ file path
    input_las = task_path + '/original_model.las'
    output_file = task_path + '/filtered_model.las'  # Specify output file path for filtered points
    url = 'https://webodm.boshang.online/api/projects/{}/tasks/{}/download/georeferenced_model.laz'.format(project_id, task_id)
    download_file(url, input_file)
    
    # alt = '/var/lib/docker/volumes/webodm_appmedia/_data/project/{}/task/{}/assets/odm_georeferencing/odm_georeferenced_model.laz'.format(project_id, task_id)
    lazTolas(input_file, input_las)
    filtered_red_pcd = filter_points_laspy(input_las, output_file)
