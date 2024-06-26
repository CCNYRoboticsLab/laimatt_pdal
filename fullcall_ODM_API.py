from flask import Flask, request, send_file, jsonify, Response
import mysql.connector
import requests
import glob
import json
import time
import os
import zipfile
import tempfile
import shutil
from filter import filter_from_webodm
from pdal_script import create_components
from enum import Enum
from io import BytesIO

class TypeColor(Enum):
    GREEN_CRACKS = 2
    RED_STAINS = 3
    BLUE_SPALLS = 4

SUCCESS = 0
NO_IMAGES = -1

app = Flask(__name__)
app.config['MAX_CONTENT_LENGTH'] = 4 * 1024 * 1024 * 1024 # 4 gb limit

def create_task(file):
    
    mydb = mysql.connector.connect(
        host="localhost",
        user="root",  # Your MySQL username
        password="",  # Your MySQL password (if any)
        port=3308,  # Your MySQL port
        unix_socket="/opt/lampp/var/mysql/mysql.sock"
    )

    cursor = mydb.cursor()
    cursor.execute("USE sample")
    
    token = authenticate()
    headers = {'Authorization': 'JWT {}'.format(token)}
        
    try:
        temp_dir = tempfile.mkdtemp()
        zip_filepath = os.path.join(temp_dir, file.filename)
        file.save(zip_filepath)
        # Extract the contents of the zip file
        extract_dir = os.path.join(temp_dir, 'extracted_folder')
        with zipfile.ZipFile(zip_filepath, 'r') as zip_ref:
            zip_ref.extractall(extract_dir)
    except:
        cursor.close()
        mydb.close()
        shutil.rmtree(temp_dir)
        return "bad input file\n"
        
    # Now you can process the contents of the extracted folder
    # For example, print the list of files extracted
    extracted_files = os.listdir(extract_dir)
    print(f"Extracted files: {extracted_files}")
    
    images = glob.glob(extract_dir + "/*.JPG") + glob.glob(extract_dir + "/*.jpg") + glob.glob(extract_dir + "/*.png") + glob.glob(extract_dir + "/*.PNG")
    SQLid = -1
            
    files = []
    for image_path in images:
        files.append(('images', (image_path, open(image_path, 'rb'), 'image/png')))
        
    print("images: " + str(files))
    if len(files) < 2:
        cursor.execute("INSERT INTO whole_data (status) VALUES (1)")
        mydb.commit()
        cursor.close()
        mydb.close()
        return "not enough images\n"

    projecturl = "http://localhost:8000/api/projects/"
    data  = {
        "name": "API_Call"
    }
    project_id = requests.post(projecturl, headers=headers, data=data).json()['id']

    taskurl = "http://localhost:8000/api/projects/" + str(project_id) + "/tasks/"
    task_id = requests.post(taskurl, headers = headers, files=files).json()['id']
    
    print("INSERT INTO whole_data (status) VALUES (3)")
    cursor.execute("INSERT INTO whole_data (status) VALUES (3)")
    mydb.commit()
    SQLid = cursor.lastrowid

    while True:
        res = requests.get('http://localhost:8000/api/projects/{}/tasks/{}/'.format(project_id, task_id), 
                    headers={'Authorization': 'JWT {}'.format(token)}).json()
        try:
            if res['status'] == 40:
                print("Task has completed!")
                break
            elif res['status'] == 30:
                print("Task failed: {}".format(res))
                cursor.execute("UPDATE whole_data SET status = 4 WHERE uid = " + SQLid)
                mydb.commit()
                cursor.close()
                mydb.close()
                shutil.rmtree(temp_dir)
                return "UPDATE whole_data SET status = 2 WHERE uid = " + str(SQLid)
            else:
                print("Processing, hold on...")
                time.sleep(30)
        except:
            print("Task failed: {}".format(res))
            cursor.execute("UPDATE whole_data SET status = 4 WHERE uid = " + SQLid)
            mydb.commit()
            cursor.close()
            mydb.close()
            shutil.rmtree(temp_dir)
            return "UPDATE whole_data SET status = 2 WHERE uid = " + str(SQLid)
            
    
    update_query = "UPDATE whole_data SET status = 4, project_id = %s, task_id = %s, whole_las_path = %s, all_files = %s, whole_glb_path = %s WHERE uid = %s"
    tm_str = getFilePath(token, project_id, task_id, "texturemap")  
    all_str = getFilePath(token, project_id, task_id, "all")  
    pc_str = getFilePath(token, project_id, task_id, "pointcloud")  
    update_data = (project_id, task_id, pc_str, all_str, tm_str, SQLid)
    cursor.execute(update_query, update_data)
    mydb.commit()
    
    color = TypeColor.BLUE_SPALLS.value
    filter_from_webodm(project_id, task_id, color)
    create_components(project_id, task_id, SQLid, color)
    
    cursor.close()
    mydb.close()
    shutil.rmtree(temp_dir)
    return "update done"
        

def authenticate():
    url = "http://localhost:8000/api/token-auth/"
    data = {
        "username": "authentication",
        "password": "authkeyword"
    }
    response = requests.post(url, data=data)
    return response.json()['token']

def getFilePath(headers, project_id, task_id, request_type):  
    
    headers = {'Authorization': 'JWT {}'.format(headers)}

    task = requests.get('http://localhost:8000/api/projects/{}/tasks/{}'.format(project_id, task_id), 
            headers=headers).json()        
    available_assets = task['available_assets']
    
    if request_type == "texturemap":
        if "textured_model.zip" in available_assets:
            return 'webodm.boshang.online/api/projects/{}/tasks/{}/download/textured_model.glb'.format(project_id, task_id)
        else:
            return "textured zip file not found"
    elif request_type == "pointcloud":
        if "georeferenced_model.laz" in available_assets:
            return 'webodm.boshang.online/api/projects/{}/tasks/{}/download/georeferenced_model.laz'.format(project_id, task_id)
        else:
            return "laz file not found"
    else:
        if "all.zip" in available_assets:
            return 'webodm.boshang.online/api/projects/{}/tasks/{}/download/all.zip'.format(project_id, task_id)
        else:
            return "all.zip file not found"
        
def test_db():
    token = authenticate()    
    project_id = 123
    task_id = "1423cc6e-0218-495a-9818-e10114997b9e"
    
    tm_str = getFilePath(token, project_id, task_id, "texturemap")  
    pc_str = getFilePath(token, project_id, task_id, "pointcloud")  
    
    result = tm_str + " " + pc_str
    print(tm_str + " " + pc_str)
    
    return result

def unzip_folder(file):
    with tempfile.TemporaryDirectory() as temp_dir:
        zip_filepath = os.path.join(temp_dir, file.filename)
        file.save(zip_filepath)
        
        # Extract the contents of the zip file
        extract_dir = os.path.join(temp_dir, 'extracted_folder')
        with zipfile.ZipFile(zip_filepath, 'r') as zip_ref:
            zip_ref.extractall(extract_dir)
        
        # Now you can process the contents of the extracted folder
        # For example, print the list of files extracted
        extracted_files = os.listdir(extract_dir)
        print(extract_dir)
        print(f"Extracted files: {extracted_files}")
        return extract_dir
    

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
    
    processed_data = create_task(file)

    return processed_data

# API endpoint
@app.route('/test', methods=['POST'])
def test_api():
    
    project_id = 152
    task_id = "dc089eca-32e5-4580-b567-8846f9c1a4a2"
    uid = 15
    color = TypeColor.BLUE_SPALLS.value
    
    filter_from_webodm(project_id, task_id, color)
    create_components(project_id, task_id, uid, color)
        
    return test_db()

@app.route('/download/<project_id>/<task_id>/<filename>', methods=['GET'])
def download(project_id, task_id, filename):
    
    # Assuming files are stored in a directory named 'files' under the app root directory
    task = os.path.join(app.root_path, 'tasks/task_{}_{}'.format(project_id, task_id))
    
    uploads = os.path.join(task, 'tests/test_10_0.2_10000/component_las_10_0.2_10000')

    # Use send_file function to send the file
    return send_file(os.path.join(uploads, filename), as_attachment=True)

@app.route('/downloadwebodm/<project_id>/<task_id>/<filename>', methods=['GET'])
def downloadwebodm(project_id, task_id, filename):
    
    url = 'https://' + getFilePath(authenticate(), project_id, task_id, filename)
    token = authenticate()
    headers = {'Authorization': 'JWT {}'.format(token)}
    # Send a GET request to the URL
    response = requests.get(url, headers=headers)

    if response.status_code == 200:
        # If the request is successful, create a BytesIO object to hold the file contents
        file_stream = BytesIO(response.content)
        file_stream.seek(0)  # Move pointer to the beginning of the stream
        
        # Send the file to the client
        return send_file(file_stream, as_attachment=True, download_name='textured_model.glb')
    else:
        return Response('Failed to fetch file from URL', status=response.status_code)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=2000, debug=True)