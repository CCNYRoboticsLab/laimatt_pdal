from flask import Flask, request, send_file, jsonify, Response
from filter import filter_from_webodm
from pdal_script import create_components
from enum import Enum
from io import BytesIO
import mysql.connector
import requests
import glob
import time
import os
from werkzeug.utils import secure_filename
import zipfile
import tempfile
import shutil
import traceback
import sys
import math

class GetFileException(Exception):
    pass

class DatabaseException(Exception):
    pass

class TypeColor(Enum):
    original = 1
    green_cracks = 2
    red_stains = 3
    blue_spalls = 4

def getName(enum_class, value):
    return next(
        (
            enum_member.name
            for enum_member in enum_class
            if enum_member.value == value
        ),
        None,
    )

# def run_gunicorn():
#     bind_address = '0.0.0.0:57902'
#     workers = 4
#     module_name = 'fullcall_ODM_API_server'
#     app_name = 'laimatt_app'

#     # Command to run Gunicorn
#     cmd = [
#         'gunicorn',
#         '-w', str(workers),
#         '-b', bind_address,
#         f'{module_name}:{app_name}'
#     ]

#     # Run the command
#     subprocess.run(cmd)

laimatt_app = Flask(__name__)
laimatt_app.config['MAX_CONTENT_LENGTH'] = 4 * 1024 * 1024 * 1024 # 4 gb limit

class WebODM_API:

    def __init__(self):
        self.task_id = ["", "", "", ""]
        self.SQLid = -1
        self.temp_dir = None  # Initialize temp_dir as None
        try:
            self.mydb = mysql.connector.connect(
            host="localhost",
            user="root",  # Your MySQL username
            password="",  # Your MySQL password (if any)
            port=80,  # Your MySQL port
            unix_socket="/app/mysql.sock"
            )
            self.cursor = self.mydb.cursor()
            self.cursor.execute("USE sample")
        except:
            self.cleanup()
            raise DatabaseException("database exception error")

    def __del__(self):
        self.cleanup()

    SUCCESS = 0
    NO_IMAGES = -1

    def cleanup(self):
        if hasattr(self, 'cursor') and self.cursor:
            self.cursor.close()
        if hasattr(self, 'mydb') and self.mydb:
            self.mydb.close()
        if self.temp_dir and os.path.exists(self.temp_dir):
            shutil.rmtree(self.temp_dir)
        self.temp_dir = None

    def extract_files(self, zip_filepath):
        try:
            # Extract the contents of the zip file
            extract_dir = os.path.join(self.temp_dir, 'extracted_folder')
            with zipfile.ZipFile(zip_filepath, 'r') as zip_ref:
                zip_ref.extractall(extract_dir)
        except Exception as e:
            print(f"Error extracting zip file: {str(e)}", flush=True)
            return None
            
        # Now you can process the contents of the extracted folder
        # For example, print the list of files extracted
        extracted_files = os.listdir(extract_dir)
        print(f"Extracted files: {extracted_files}", flush=True)
                
        images = glob.glob(os.path.join(extract_dir, "*.JPG")) + \
                 glob.glob(os.path.join(extract_dir, "*.jpg")) + \
                 glob.glob(os.path.join(extract_dir, "*.png")) + \
                 glob.glob(os.path.join(extract_dir, "*.PNG"))
                
        files = []
        for image_path in images:
            with open(image_path, 'rb') as img_file:
                files.append(('images', (os.path.basename(image_path), img_file.read(), 'image/png')))
        
        return files
    
    def init_nodeODM(self, project_id, files, color, node):
        index = color - 1
        
        taskurl = f"https://webodm.boshang.online/api/projects/{project_id}/tasks/"
        data = {
            "name": getName(TypeColor, color),
            "processing_node": node
        }
        try:
            response = requests.post(taskurl, headers=self.headers, files=files, data=data)
            response.raise_for_status()  # Raises an HTTPError for bad responses
            self.task_id[index] = response.json()['id']
        except requests.exceptions.RequestException as e:
            print(f"Error in init_nodeODM: {str(e)}", flush=True)
            raise
        
        if node == 1:
            print(f"INSERT INTO whole_data (status) VALUES (3) for {getName(TypeColor, color)}", flush=True)
            self.cursor.execute("INSERT INTO whole_data (status) VALUES (3)")
            self.mydb.commit()
            self.SQLid = self.cursor.lastrowid
    
    def post_task(self, project_id, color):
        index = color - 1
        
        self.cursor.execute(f"UPDATE whole_data SET status = {color + 4} WHERE uid = {self.SQLid}")
        self.mydb.commit()
                    
        while True:
            res = requests.get(f'https://webodm.boshang.online/api/projects/{project_id}/tasks/{self.task_id[index]}/', 
                        headers=self.headers).json()
            try:
                if res['status'] == 40:
                    print(f"Task for {getName(TypeColor, color)} has completed!", flush=True)
                    break
                elif res['status'] == 30:
                    print(f"{getName(TypeColor, color)} Task failed: {res}", flush=True)
                    self.cursor.execute(f"UPDATE whole_data SET status = 2 WHERE uid = {self.SQLid}")
                    self.mydb.commit()
                    return f"{getName(TypeColor, color)} Task failed: {res}"
                else:
                    print(f"Currently processing: {getName(TypeColor, color)}, hold on...", flush=True)
                    time.sleep(30)
            except Exception as error:
                print(f"{getName(TypeColor, color)} Task failed: {res}", flush=True)
                self.cursor.execute(f"UPDATE whole_data SET status = 2 WHERE uid = {self.SQLid}")
                self.mydb.commit()
                print(error, flush=True)
                return f"{getName(TypeColor, color)} Task failed: {res}"
        
        colorName = getName(TypeColor, color)
        
        update_query = "UPDATE whole_data SET project_id = %s, %s = '%s', %s = '%s', %s = '%s', %s = '%s' WHERE uid = %s"
        tm_str = f'https://laimatt.boshang.online/downloadwebodm/{project_id}/{self.task_id[index]}/textured_model.glb'
        all_str = f'https://laimatt.boshang.online/downloadwebodm/{project_id}/{self.task_id[index]}/all.zip'
        pc_str = f'https://laimatt.boshang.online/downloadwebodm/{project_id}/{self.task_id[index]}/georeferenced_model.laz'
        update_data = (str(project_id), 'task_id_' + colorName, self.task_id[index], 'all_file_' + colorName, all_str, \
            'las_file_' + colorName, pc_str, 'glb_file_' + colorName, tm_str, str(self.SQLid))
        toUpdate = update_query % update_data
        print(toUpdate)
        self.cursor.execute(toUpdate)
        self.mydb.commit()
        
        if not color == 1:
            filter_from_webodm(project_id, self.task_id[index], color)
            create_components(project_id, self.task_id[index], self.SQLid, color)
        
        return None

    def create_task(self, file):
        try:
            self.temp_dir = tempfile.mkdtemp()  # Create a temporary directory
            # Save the uploaded file to a temporary location
            filename = secure_filename(file.filename)
            temp_path = os.path.join(self.temp_dir, filename)
            file.save(temp_path)

            # Extract files into a list
            files = self.extract_files(temp_path)
            if files is None:
                return "Bad input file\n"
            elif len(files) < 2:
                return f"Not enough images, images found: {len(files)}\n"

            projecturl = "https://webodm.boshang.online/api/projects/"
            data = {
                "name": "API_Call_threecolor"
            }
            project_id = requests.post(projecturl, headers=self.headers, data=data).json()['id']
            # self.SQLid = [61, 61, 61, 61]
            # self.task_id = ["74b51bf5-ba1a-46f4-a377-1d11ec94b3d5", "1b8a7e5e-65b2-4928-8638-cbbe00933776", "7f081d95-e7cc-468b-b17f-e3cf4beac9e0", "4df4bc29-b5a4-4db9-96db-257e530fab96"]
            # project_id = 219
            
            
            tasks = [
                (TypeColor.original.value, 1),
                (TypeColor.green_cracks.value, 15),
                (TypeColor.red_stains.value, 14),
                (TypeColor.blue_spalls.value, 16)
            ]
            
            task_path = 'tasks/projID_{}'.format(project_id) 
            if os.path.exists(task_path):
                print(task_path + " already exists, remaking", flush=True)
                shutil.rmtree(task_path)
            os.makedirs(task_path)
            
            for color, node in tasks:
                self.init_nodeODM(project_id, files, color, node)
                result = self.post_task(project_id, color)
                if result is not None:
                    return f"Error processing task for {getName(TypeColor, color)}: {result}"
                time.sleep(30)  # Add a short delay between tasks  
            
            self.cursor.execute(f"UPDATE whole_data SET status = 4 WHERE uid = {self.SQLid}")
            self.mydb.commit()
            return "All tasks completed and clustered\n"
        except Exception as e:
            print(f"Error in create_task: {str(e)}", flush=True)
            raise
        finally:
            self.cleanup()

    def authenticate(self):
        url = "https://webodm.boshang.online/api/token-auth/"
        data = {
            "username": "authentication",
            "password": "authkeyword"
        }
        response = requests.post(url, data=data)
        
        self.headers = {'Authorization': f"JWT {response.json()['token']}"}
        return self.headers

    def getFilePath(self, project_id, task_id, request_type):  
        try:
            task = requests.get(
                f'https://webodm.boshang.online/api/projects/{project_id}/tasks/{task_id}',
                headers=self.headers,
            ).json()
            available_assets = task['available_assets']
        except:
            raise GetFileException("task or project not found")
        
        if request_type == "textured_model.glb":
            if "textured_model.zip" in available_assets:
                return f'https://webodm.boshang.online/api/projects/{project_id}/tasks/{task_id}/download/textured_model.glb'
            else:
                raise GetFileException("task found, but textured zip file not found")
        elif request_type == "georeferenced_model.laz":
            if "georeferenced_model.laz" in available_assets: 
                return f'https://webodm.boshang.online/api/projects/{project_id}/tasks/{task_id}/download/georeferenced_model.laz'
            else:
                raise GetFileException("task found, but laz file not found")
        elif request_type == "all.zip":
            if "all.zip" in available_assets: 
                return f'https://webodm.boshang.online/api/projects/{project_id}/tasks/{task_id}/download/all.zip'
            else:
                raise GetFileException("task found, but all.zip file not found")
        else:
            raise GetFileException("invalid request type")
        
    def get_bounding_box_corners(self, x, y, z, length, width, height):
        # Calculate half of each dimension
        half_length = length / 2.0
        half_width = width / 2.0
        half_height = height / 2.0

        # Calculate min and max bounds
        min_x = x - half_length
        max_x = x + half_length
        min_y = y - half_width
        max_y = y + half_width
        min_z = z - half_height
        max_z = z + half_height

        # Return min and max bounds as lists
        min_bound = [min_x, min_y, min_z]
        max_bound = [max_x, max_y, max_z]

        return min_bound, max_bound
    
    def get_cracks(self):
        
        start_row = 34
        end_row = 45
        columns = ["center_lat", "center_long", "center_alt", "box_length", "box_width", "box_height"]  # Replace with your actual column names

        # Update the SQL query to select specific columns
        query = f"SELECT {', '.join(columns)} FROM patch_crack LIMIT %s OFFSET %s"
        
        limit = end_row - start_row + 1
        offset = start_row - 1

        # Execute the query with LIMIT and OFFSET
        self.cursor.execute(query, (limit, offset))

        # Fetch and iterate through the rows
        results = []
        for row in self.cursor:
            try:
                # Convert each column value to float
                float_values = [float(value) for value in row]
                results.append(float_values)
                # Print the float values
                print(f"Float Values: {float_values}", flush=True)
            except ValueError as e:
                print(f"Error converting value to float: {e}", flush=True)
            
        return results        

# API endpoint
@laimatt_app.route('/task', methods=['POST'])
def task_api():
    try:
        if 'file' not in request.files:
            return jsonify({'error': 'No file part in the request'}), 400
        
        file = request.files['file']
        if file.filename == '':
            return jsonify({'error': 'No file selected for uploading'}), 400
        
        api.authenticate()
        result = api.create_task(file)
        return result
    except Exception as e:
        # Log the full exception traceback
        print(f"An error occurred: {str(e)}", file=sys.stderr)
        print(traceback.format_exc(), file=sys.stderr)
        # You might want to log this to a file as well
        
        # Return a more informative error response
        return jsonify({
            'error': 'An internal server error occurred',
            'details': str(e)
        }), 500
        
# Modify the error handler for 500 errors
@laimatt_app.errorhandler(500)
def internal_error(error):
    print(f"500 error occurred: {str(error)}", file=sys.stderr)
    return jsonify({
        'error': 'An internal server error occurred',
        'details': str(error)
    }), 500

# API endpoint
@laimatt_app.route('/test', methods=['POST'])
def test_api():
    api.authenticate()
    
    project_id = 181
    task_id = "57e7cde0-c2d4-48d0-918b-f71b09702faf"
    uid = 23
    color = TypeColor.blue_spalls.value
    
    print("test)")
    # filter_from_webodm(project_id, task_id, color)
    # create_components(project_id, task_id, uid, color)
        
    return "clustering done\n"

@laimatt_app.route('/download/<project_id>/<type>/<filename>', methods=['GET'])
def download(project_id, type, filename):
    api.authenticate()
    
    # Assuming files are stored in a directory named 'files' under the app root directory
    task = os.path.join(laimatt_app.root_path, f'tasks/projID_{project_id}')
    uploads = os.path.join(task, f'tests/{type}_test_10_0.2_10000/component_las_10_0.2_10000')
    
    if not (os.path.isfile(os.path.join(uploads, filename))):
        return "requested file does not exist"
    # Use send_file function to send the file
    return send_file(os.path.join(uploads, filename), as_attachment=True)

@laimatt_app.route('/downloadwebodm/<project_id>/<task_id>/<filename>', methods=['GET'])
def downloadwebodm(project_id, task_id, filename):
    api.authenticate()    
    try:
        url = api.getFilePath(project_id, task_id, filename)
    except GetFileException as e:
        return repr(e)
        
    # Send a GET request to the URL
    print(url, flush = True)
    response = requests.get(url, headers=api.authenticate())
    # if (response.content < 50):
    #     response = requests.get(url, headers=api.authenticate())

    if response.status_code == 200:
        # If the request is successful, create a BytesIO object to hold the file contents
        file_stream = BytesIO(response.content)
        file_stream.seek(0)  # Move pointer to the beginning of the stream
        
        # Send the file to the client
        return send_file(file_stream, as_attachment=True, download_name=filename)
    else:
        return Response('Failed to fetch file from URL', status=response.status_code)
    
@laimatt_app.route('/')
def hello_geek():
    return '<h1>Hello from Flask & Docker</h2>'

@laimatt_app.route('/analyze_crack', methods=['GET'])
def analyze_crack():
    try:
        x = float(request.args.get("x"))
        y = float(request.args.get("y"))
        z = float(request.args.get("z"))
        length = float(request.args.get("length"))
        width = float(request.args.get("width"))
        height = float(request.args.get("height"))
        
        min_bound, max_bound = api.get_bounding_box_corners(x, y, z, length, width, height)
        cracks = api.get_cracks()
        
        diagonal = 0
        for crack in cracks:
            if crack[0] >= min_bound[0] and crack[0] <= max_bound[0] and \
                crack[1] >= min_bound[1] and crack[1] <= max_bound[1] and \
                crack[2] >= min_bound[2] and crack[2] <= max_bound[2]:
                
                print(f"{crack} chosen", flush=True)
                diagonal += math.sqrt(length**2 + width**2 + height**2)
                    
        return str(diagonal)
        
    except Exception as e:
        print(f"Error in /analyze_crack: {str(e)}", flush = True)
        return jsonify({"error": "An error occurred during analysis."}), 500

api = WebODM_API()
# if __name__ == '__main__':
#     # run_gunicorn()
        
#     # run as a flask app instead
#     laimatt_app.run(host='0.0.0.0', port=57902, debug=True)
#     # laimatt_app.run()
