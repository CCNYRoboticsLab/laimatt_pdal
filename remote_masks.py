import subprocess
import configparser

def remote_masks(project_folder):
    script_path = '/home/roboticslab/Developer/laimatt/image2overlays/main.py'
    working_directory = '/home/roboticslab/Developer/laimatt/image2overlays'
    config_name = '/home/roboticslab/Developer/laimatt/image2overlays/config.ini'
    input_directory = f'/home/roboticslab/Developer/laimatt/laimatt_pdal/tasks/{project_folder}/images'
    # script_path = '/image2overlays/main.py'
    # working_directory = '/image2overlays'
    # config_name = '/image2overlays/config.ini'
    # input_directory = f'/app/tasks/{project_folder}/images'

    config = configparser.ConfigParser()
    config.read(config_name)  # Replace with the actual path to your INI file

    # Paths for the mask images, raw images, and output images
    # Read from the INI file
    config["Settings"]["image_path"] = input_directory

    with open(config_name, "w") as configfile:
        config.write(configfile)
        
    # Run the script in the specified directory
    result = subprocess.run(['python', script_path, 'F'], cwd=working_directory, capture_output=True, text=True)

    # Print the command's output
    # print('STDOUT:', result.stdout)

# remote_masks('projID_1')
