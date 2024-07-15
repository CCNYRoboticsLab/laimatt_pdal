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
import zipfile
import tempfile
import shutil
import subprocess

class GetFileException(Exception):
    pass

class DatabaseException(Exception):
    pass

class TypeColor(Enum):
    ORIGINAL = 1
    GREEN_CRACKS = 2
    RED_STAINS = 3
    BLUE_SPALLS = 4

def getName(enum_class, value):
    for enum_member in enum_class:
        if enum_member.value == value:
            return enum_member.name
    return None  

def run_gunicorn():
    bind_address = '0.0.0.0:92384'
    workers = 4
    module_name = 'fullcall_ODM_API_server'
    app_name = 'laimatt_app'

    # Command to run Gunicorn
    cmd = [
        'gunicorn',
        '-w', str(workers),
        '-b', bind_address,
        f'{module_name}:{app_name}'
    ]

    # Run the command
    subprocess.run(cmd)

laimatt_app = Flask(__name__)
laimatt_app.config['MAX_CONTENT_LENGTH'] = 4 * 1024 * 1024 * 1024 # 4 gb limit

class WebODM_API:

    def __init__(self):
        print("test")
        self.task_id = ["", "", "", ""]
        self.SQLid = [-1, -1, -1, -1]
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
            raise DatabaseException("database exception error")

    SUCCESS = 0
    NO_IMAGES = -1
        
    def extract_files(self, file):
        try:
            self.temp_dir = tempfile.mkdtemp()
            zip_filepath = os.path.join(self.temp_dir, file.filename)
            file.save(zip_filepath)
            # Extract the contents of the zip file
            extract_dir = os.path.join(self.temp_dir, 'extracted_folder')
            with zipfile.ZipFile(zip_filepath, 'r') as zip_ref:
                zip_ref.extractall(extract_dir)
        except:
            self.cursor.close()
            self.mydb.close()
            shutil.rmtree(self.temp_dir)
            return None
            
        # Now you can process the contents of the extracted folder
        # For example, print the list of files extracted
        extracted_files = os.listdir(extract_dir)
        print(f"Extracted files: {extracted_files}", flush=True)
                
        images = glob.glob(extract_dir + "/*.JPG") + glob.glob(extract_dir + "/*.jpg") + glob.glob(extract_dir + "/*.png") + glob.glob(extract_dir + "/*.PNG")
                
        files = []
        for image_path in images:
            files.append(('images', (image_path, open(image_path, 'rb'), 'image/png')))
        
        return files
    
    def init_nodeODM(self, project_id, files, color, node):
        index = color - 1
        
        taskurl = "https://webodm.boshang.online/api/projects/" + str(project_id) + "/tasks/"
        data  = {
            "name": getName(TypeColor, color),
            "processing_node": node
        }
        self.task_id[index] = requests.post(taskurl, headers = self.headers, files=files, data = data).json()['id']
        
        print("INSERT INTO whole_data (status) VALUES (3)", flush=True)
        self.cursor.execute("INSERT INTO whole_data (status) VALUES (3)")
        self.mydb.commit()
        self.SQLid[index] = self.cursor.lastrowid
    
    def post_task(self, project_id, color):
        index = color - 1
        
        while True:
            res = requests.get('https://webodm.boshang.online/api/projects/{}/tasks/{}/'.format(project_id, self.task_id[index]), 
                        headers=self.headers).json()
            try:
                if res['status'] == 40:
                    print("Task has completed!", flush=True)
                    break
                elif res['status'] == 30:
                    print(getName(TypeColor, color) + " Task failed: {}\n".format(res), flush=True)
                    self.cursor.execute("UPDATE whole_data SET status = 2 WHERE uid = " + str(self.SQLid[index]))
                    self.mydb.commit()
                    return getName(TypeColor, color) + " Task failed: {}\n".format(res)
                else:
                    print("Currently processing: " + getName(TypeColor, color) + ", hold on...", flush=True)
                    time.sleep(30)
            except Exception as error:
                print(getName(TypeColor, color) + " Task failed: {}\n".format(res), flush=True)
                self.cursor.execute("UPDATE whole_data SET status = 2 WHERE uid = " + str(self.SQLid[index]))
                self.mydb.commit()
                print(error, flush=True)
                return getName(TypeColor, color) + " Task failed: {}\n"
                
        
        update_query = "UPDATE whole_data SET status = 4, project_id = %s, task_id = %s, las_file = %s, all_file = %s, glb_file = %s WHERE uid = %s"
        tm_str = 'https://laimatt.boshang.online/downloadwebodm/{}/{}/textured_model.glb'.format(project_id, self.task_id[index])
        all_str = 'https://laimatt.boshang.online/downloadwebodm/{}/{}/all.zip'.format(project_id, self.task_id[index])
        pc_str = 'https://laimatt.boshang.online/downloadwebodm/{}/{}/georeferenced_model.laz'.format(project_id, self.task_id[index])
        update_data = (project_id, self.task_id[index], pc_str, all_str, tm_str, self.SQLid[index])
        self.cursor.execute(update_query, update_data)
        self.mydb.commit()
        
        filter_from_webodm(project_id, self.task_id[index], color)
        create_components(project_id, self.task_id[index], self.SQLid[index], color)
        
        return None

    def create_task(self, file):
        # extract files into a list
        files = self.extract_files(file)
        if files == None: return "Bad input file\n"
        elif len(files) < 2:
            self.cursor.close()
            self.mydb.close()
            shutil.rmtree(self.temp_dir)
            return "not enough images, images found: " + str(files) + "\n"
        

        projecturl = "https://webodm.boshang.online/api/projects/"
        data  = {
            "name": "API_Call_threecolor"
        }
        project_id = requests.post(projecturl, headers=self.headers, data=data).json()['id']

        # self.init_nodeODM(project_id, files, TypeColor.ORIGINAL.value, 1)
        # self.init_nodeODM(project_id, files, TypeColor.GREEN_CRACKS.value, 15)
        # self.init_nodeODM(project_id, files, TypeColor.RED_STAINS.value, 14)
        self.init_nodeODM(project_id, files, TypeColor.BLUE_SPALLS.value, 1)
        
        # if (self.SQLid == -1):
        #     self.cursor.close()
        #     self.mydb.close()
        #     shutil.rmtree(self.temp_dir)
        #     return "database error"
        
        # self.post_task(project_id, TypeColor.GREEN_CRACKS.value)
        # self.post_task(project_id, TypeColor.RED_STAINS.value)
        result = self.post_task(project_id, TypeColor.BLUE_SPALLS.value)
        
        # if not (result == None):
        #     return "post_task error"
        
        self.cursor.close()
        self.mydb.close()
        shutil.rmtree(self.temp_dir)
        return "task complete and clustered\n"
            

    def authenticate(self):
        url = "https://webodm.boshang.online/api/token-auth/"
        data = {
            "username": "authentication",
            "password": "authkeyword"
        }
        response = requests.post(url, data=data)
        
        self.headers = {'Authorization': 'JWT {}'.format(response.json()['token'])}
        return self.headers

    def getFilePath(self, project_id, task_id, request_type):  
        try:
            task = requests.get('https://webodm.boshang.online/api/projects/{}/tasks/{}'.format(project_id, task_id), 
                    headers=self.headers).json()        
            available_assets = task['available_assets']
        except:
            raise GetFileException("task or project not found")
        
        if request_type == "textured_model.glb":
            if "textured_model.zip" in available_assets:
                return 'https://webodm.boshang.online/api/projects/{}/tasks/{}/download/textured_model.glb'.format(project_id, task_id)
            else:
                raise GetFileException("task found, but textured zip file not found")
        elif request_type == "georeferenced_model.laz":
            if "georeferenced_model.laz" in available_assets:
                return 'https://webodm.boshang.online/api/projects/{}/tasks/{}/download/georeferenced_model.laz'.format(project_id, task_id)
            else:
                raise GetFileException("task found, but laz file not found")
        elif request_type == "all.zip":
            if "all.zip" in available_assets:
                return 'https://webodm.boshang.online/api/projects/{}/tasks/{}/download/all.zip'.format(project_id, task_id)
            else:
                raise GetFileException("task found, but all.zip file not found")
        else:
            raise GetFileException("invalid request type")

# API endpoint
@laimatt_app.route('/task', methods=['POST'])
def task_api():
    if 'file' not in request.files:
        return jsonify({'error': 'No file part in the request'}), 400
    
    file = request.files['file']
    if file.filename == '':
        return jsonify({'error': 'No file selected for uploading'}), 400
    
    # folder = unzip_folder(file)
    
    # print(jsonify({'message': 'Folder uploaded and extracted successfully'}), 200)

    api.authenticate()
    return api.create_task(file)

# API endpoint
@laimatt_app.route('/test', methods=['POST'])
def test_api():
    api.authenticate()
    
    project_id = 181
    task_id = "57e7cde0-c2d4-48d0-918b-f71b09702faf"
    uid = 23
    color = TypeColor.BLUE_SPALLS.value
    
    print("test)")
    # filter_from_webodm(project_id, task_id, color)
    # create_components(project_id, task_id, uid, color)
        
    return "clustering done\n"

@laimatt_app.route('/download/<project_id>/<task_id>/<filename>', methods=['GET'])
def download(project_id, task_id, filename):
    api.authenticate()
    
    # Assuming files are stored in a directory named 'files' under the app root directory
    task = os.path.join(laimatt_app.root_path, 'tasks/task_{}_{}'.format(project_id, task_id))
    uploads = os.path.join(task, 'tests/test_10_0.2_10000/component_las_10_0.2_10000')

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

api = WebODM_API()
print("test")
if __name__ == '__main__':
    # run_gunicorn()
        
    # run as a flask app instead
    laimatt_app.run(host='0.0.0.0', port=33333, debug=True)
    # laimatt_app.run()
