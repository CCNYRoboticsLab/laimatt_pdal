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

class TypeColor(Enum):
    GREEN_CRACKS = 2
    RED_STAINS = 3
    BLUE_SPALLS = 4

app = Flask(__name__)
app.config['MAX_CONTENT_LENGTH'] = 4 * 1024 * 1024 * 1024 # 4 gb limit

class WebODM_API:

    def __init__(self):
        try:
            self.mydb = mysql.connector.connect(
            host="localhost",
            user="root",  # Your MySQL username
            password="",  # Your MySQL password (if any)
            port=3308,  # Your MySQL port
            unix_socket="/opt/lampp/var/mysql/mysql.sock"
            )
            self.cursor = self.mydb.cursor()
            self.cursor.execute("USE sample")
        except:
            return "database connection error\n"

    SUCCESS = 0
    NO_IMAGES = -1

    def run_gunicorn(self):
        bind_address = '0.0.0.0:2000'
        workers = 4
        module_name = 'app'
        app_name = 'app'

        # Command to run Gunicorn
        cmd = [
            'gunicorn',
            '-w', str(workers),
            '-b', bind_address,
            f'{module_name}:{app_name}'
        ]

        # Run the command
        subprocess.run(cmd)
        
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
        print(f"Extracted files: {extracted_files}")
                
        images = glob.glob(extract_dir + "/*.JPG") + glob.glob(extract_dir + "/*.jpg") + glob.glob(extract_dir + "/*.png") + glob.glob(extract_dir + "/*.PNG")
        self.SQLid = -1
                
        files = []
        for image_path in images:
            files.append(('images', (image_path, open(image_path, 'rb'), 'image/png')))
        
        return files
    
    def post_task(self, project_id, task_id):
        headers = self.authenticate()
        
        while True:
            res = requests.get('http://localhost:8000/api/projects/{}/tasks/{}/'.format(project_id, task_id), 
                        headers=headers).json()
            try:
                if res['status'] == 40:
                    print("Task has completed!")
                    break
                elif res['status'] == 30:
                    print("Task failed: {}".format(res))
                    self.cursor.execute("UPDATE whole_data SET status = 2 WHERE uid = " + str(self.SQLid))
                    self.mydb.commit()
                    self.cursor.close()
                    self.mydb.close()
                    shutil.rmtree(self.temp_dir)
                    return "Task failed: {}\n".format(res)
                else:
                    print("Processing, hold on...")
                    time.sleep(30)
            except:
                print("Task failed")
                self.cursor.execute("UPDATE whole_data SET status = 2 WHERE uid = " + str(self.SQLid))
                self.mydb.commit()
                self.cursor.close()
                self.mydb.close()
                shutil.rmtree(self.temp_dir)
                return "Task failed\n"
                
        
        update_query = "UPDATE whole_data SET status = 4, project_id = %s, task_id = %s, whole_las_path = %s, all_files = %s, whole_glb_path = %s WHERE uid = %s"
        tm_str = 'https://laimatt.boshang.online/downloadwebodm/{}/{}/textured_model.glb'.format(project_id, task_id)
        all_str = 'https://laimatt.boshang.online/downloadwebodm/{}/{}/all.zip'.format(project_id, task_id)
        pc_str = 'https://laimatt.boshang.online/downloadwebodm/{}/{}/georeferenced_model.laz'.format(project_id, task_id)
        update_data = (project_id, task_id, pc_str, all_str, tm_str, self.SQLid)
        self.cursor.execute(update_query, update_data)
        self.mydb.commit()
        
        color = TypeColor.BLUE_SPALLS.value
        filter_from_webodm(project_id, task_id, color)
        create_components(project_id, task_id, self.SQLid, color)

    def create_task(self, file):
        headers = self.authenticate()
            
        files = self.extract_files(file)
        if files == None: return "Bad input file\n"
        elif len(files) < 2:
            self.cursor.close()
            self.mydb.close()
            shutil.rmtree(self.temp_dir)
            return "not enough images, images found: " + str(files) + "\n"
        

        projecturl = "http://localhost:8000/api/projects/"
        data  = {
            "name": "API_Call"
        }
        project_id = requests.post(projecturl, headers=headers, data=data).json()['id']

        taskurl = "http://localhost:8000/api/projects/" + str(project_id) + "/tasks/"
        task_id = requests.post(taskurl, headers = headers, files=files).json()['id']
        
        print("INSERT INTO whole_data (status) VALUES (3)")
        self.cursor.execute("INSERT INTO whole_data (status) VALUES (3)")
        self.mydb.commit()
        self.SQLid = self.cursor.lastrowid
        
        if (self.SQLid == -1):
            self.cursor.close()
            self.mydb.close()
            shutil.rmtree(self.temp_dir)
            return "database error"
        
        self.post_task(project_id, task_id)
        
        self.cursor.close()
        self.mydb.close()
        shutil.rmtree(self.temp_dir)
        return "task complete and clustered\n"
            

    def authenticate(self):
        url = "http://localhost:8000/api/token-auth/"
        data = {
            "username": "authentication",
            "password": "authkeyword"
        }
        response = requests.post(url, data=data)
        
        return {'Authorization': 'JWT {}'.format(response.json()['token'])}

    def getFilePath(self, headers, project_id, task_id, request_type):  
        try:
            task = requests.get('http://localhost:8000/api/projects/{}/tasks/{}'.format(project_id, task_id), 
                    headers=headers).json()        
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
            
    def test_db(self):
        headers = self.authenticate()    
        project_id = 123
        task_id = "1423cc6e-0218-495a-9818-e10114997b9e"
        
        tm_str = self.getFilePath(headers, project_id, task_id, "textured_model.glb")  
        all_str = self.getFilePath(headers, project_id, task_id, "all.zip")  
        pc_str = self.getFilePath(headers, project_id, task_id, "georeferenced_model.laz")  
        
        result = tm_str + " " + pc_str
        print(tm_str + " " + pc_str)
        
        return result

    # API endpoint
    @app.route('/task', methods=['POST'])
    def task_api():
        if 'file' not in request.files:
            return jsonify({'error': 'No file part in the request'}), 400
        
        file = request.files['file']
        if file.filename == '':
            return jsonify({'error': 'No file selected for uploading'}), 400
        
        # folder = unzip_folder(file)
        
        # print(jsonify({'message': 'Folder uploaded and extracted successfully'}), 200)

        return api.create_task(file)

# API endpoint
@app.route('/test', methods=['POST'])
def test_api():
    
    project_id = 163
    task_id = "2db66de4-561b-4cf0-9633-d79a6b3996f7"
    uid = 25
    color = TypeColor.BLUE_SPALLS.value
    
    filter_from_webodm(project_id, task_id, color)
    create_components(project_id, task_id, uid, color)
        
    return "clustering done\n"

@app.route('/download/<project_id>/<task_id>/<filename>', methods=['GET'])
def download(project_id, task_id, filename):
    
    # Assuming files are stored in a directory named 'files' under the app root directory
    task = os.path.join(app.root_path, 'tasks/task_{}_{}'.format(project_id, task_id))
    uploads = os.path.join(task, 'tests/test_10_0.2_10000/component_las_10_0.2_10000')

    if not (os.path.isfile(os.path.join(uploads, filename))):
        return "requested file does not exist"
    # Use send_file function to send the file
    return send_file(os.path.join(uploads, filename), as_attachment=True)

@app.route('/downloadwebodm/<project_id>/<task_id>/<filename>', methods=['GET'])
def downloadwebodm(project_id, task_id, filename):
    
    headers = api.authenticate()    
    try:
        url = api.getFilePath(headers, project_id, task_id, filename)
    except GetFileException as e:
        return repr(e)
        
    # Send a GET request to the URL
    response = requests.get(url, headers=headers)

    if response.status_code == 200:
        # If the request is successful, create a BytesIO object to hold the file contents
        file_stream = BytesIO(response.content)
        file_stream.seek(0)  # Move pointer to the beginning of the stream
        
        # Send the file to the client
        return send_file(file_stream, as_attachment=True, download_name=filename)
    else:
        return Response('Failed to fetch file from URL', status=response.status_code)

api = WebODM_API()
if __name__ == '__main__':
    # run_gunicorn()
        
    # run as a flask app instead
    app.run(host='0.0.0.0', port=2000, debug=True)
        