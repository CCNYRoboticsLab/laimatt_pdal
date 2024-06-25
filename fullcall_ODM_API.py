from flask import Flask, request, send_file, jsonify
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

SUCCESS = 0
NO_IMAGES = -1
NO_PROJECT = 1
NO_TASK = 2
NO_FILE = 3
NO_JSON = 4

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
    
    temp_dir = tempfile.mkdtemp()
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
    
    images = glob.glob(extract_dir + "/*.JPG") + glob.glob(extract_dir + "/*.jpg") + glob.glob(extract_dir + "/*.png") + glob.glob(extract_dir + "/*.PNG")
    SQLid = -1
            
    files = []
    for image_path in images:
        files.append(('images', (image_path, open(image_path, 'rb'), 'image/png')))
        
    print("images: " + str(files))
    if len(files) < 2:
        json_data = {
            "task_id": "",
            "project_id": NO_IMAGES, 
            "authentication": token
        }
        with open("data.json", "w") as json_file:
            json.dump(json_data, json_file)
        print("INSERT INTO whole_data (status) VALUES (1)")
        cursor.execute("INSERT INTO whole_data (status) VALUES (1)")
        mydb.commit()
        return json_data

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
    
    project_id = 151
    task_id = "c9c7deff-e46b-4ed5-8316-79ddf9d19352"
    
    filter_from_webodm(project_id, task_id)
    
    folder_path = 'tasks/task_{}_{}/'.format(project_id, task_id)
    
    # create_components(folder_path)
        
    return test_db()

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=2000, debug=True)