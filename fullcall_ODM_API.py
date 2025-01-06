from flask import Flask, request, send_file, jsonify, Response
from flask_cors import CORS
from filter import filter_from_webodm
# from pdal_script import create_components
from remote_masks import remote_masks
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
from flask import render_template
import logging
from typing import Optional, List, Tuple


logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler('upload_debug.log')
    ]
)


def is_docker():
    return os.path.exists("/.dockerenv") or os.getenv("DOCKER_ENV") == "true"


if is_docker():
    print("Running inside Docker")
else:
    print("Running outside Docker")


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
        (enum_member.name for enum_member in enum_class if enum_member.value == value),
        None,
    )


laimatt_app = Flask(__name__)
laimatt_app.config["MAX_CONTENT_LENGTH"] = 4 * 1024 * 1024 * 1024  # 4 gb limit

# Update allowed origins to include null for file:// protocol
ALLOWED_ORIGINS = [
    "http://localhost:3000",
    "https://webodm.boshang.online",
    "http://boshang.online:37354",
    "null",
]

CORS(
    laimatt_app,
    supports_credentials=True,
    resources={
        r"/*": {
            "origins": ALLOWED_ORIGINS,
            "methods": ["GET", "POST", "OPTIONS"],
            "allow_headers": [
                "Content-Type",
                "Authorization",
                "Origin",
                "Content-Length",
            ],
        }
    },
)


@laimatt_app.after_request
def add_cors_headers(response):
    origin = request.headers.get("Origin", "null")
    if origin == "null":
        response.headers["Access-Control-Allow-Origin"] = "null"
    elif origin in ALLOWED_ORIGINS:
        response.headers["Access-Control-Allow-Origin"] = origin
    response.headers["Access-Control-Allow-Credentials"] = "true"
    response.headers["Access-Control-Allow-Methods"] = "GET, POST, OPTIONS"
    response.headers["Access-Control-Allow-Headers"] = (
        "Content-Type, Authorization, Origin"
    )
    return response


@laimatt_app.route("/<path:path>", methods=["OPTIONS"])
def options_handler(path):
    response = Response()
    origin = request.headers.get("Origin", "null")
    if origin == "null":
        response.headers["Access-Control-Allow-Origin"] = "null"
    elif origin in ALLOWED_ORIGINS:
        response.headers["Access-Control-Allow-Origin"] = origin
    response.headers["Access-Control-Allow-Credentials"] = "true"
    response.headers["Access-Control-Allow-Methods"] = "GET, POST, OPTIONS"
    response.headers["Access-Control-Allow-Headers"] = (
        "Content-Type, Authorization, Origin"
    )
    return response


class WebODM_API:

    def __init__(self):
        self.task_id = ["", "", "", ""]
        self.SQLid = -1
        self.temp_dir = None  # Initialize temp_dir as None
        self.extract_dir = None
        try:
            self.mydb = mysql.connector.connect(
                # host="172.18.0.1",
                host="127.0.0.1",
                # user="phpMyAdmin",  # Your MySQL username
                user="phpMyAdminRoot",  # Your MySQL username
                password="roboticslab",  # Your MySQL password (if any)
                port=3306,  # Your MySQL port
                unix_socket="/opt/lampp/var/mysql/mysql.sock"
                # port=80,
                # unix_socket="/app/mysql.sock",
            )
            print("Database connected.")
            self.cursor = self.mydb.cursor()
            self.cursor.execute("USE sample")
        except:
            # self.cleanup()
            raise DatabaseException("database exception error")

    def __del__(self):
        try:
            self.cleanup()
        except Exception as e:
            print(f"Error in __del__: {e}", file=sys.stderr)

    SUCCESS = 0
    NO_IMAGES = -1

    def cleanup(self):
        """Clean up resources if they exist"""
        try:
            if hasattr(self, "cursor") and self.cursor:
                self.cursor.close()
                logging.debug("Closed database cursor")
        except Exception as e:
            logging.error(f"Error closing cursor: {e}")

        try:
            if hasattr(self, "mydb") and self.mydb:
                self.mydb.close()
                logging.debug("Closed database connection")
        except Exception as e:
            logging.error(f"Error closing database: {e}")

        try:
            if self.temp_dir and os.path.exists(self.temp_dir):
                shutil.rmtree(self.temp_dir)
                logging.debug(f"Removed temporary directory: {self.temp_dir}")
        except Exception as e:
            logging.error(f"Error removing temp directory: {e}")

        self.temp_dir = None

    def extract_files(self, zip_filepath) -> Optional[List[Tuple[str, tuple]]]:
        """
        Extract and validate files from uploaded zip archive
        Returns list of files or None if extraction fails
        """
        try:
            # Log zip file details
            zip_size = os.path.getsize(zip_filepath)
            logging.info(f"Processing zip file: {zip_filepath}, size: {zip_size} bytes")

            # Extract the contents of the zip file
            self.extract_dir = os.path.join(self.temp_dir, "extracted_folder")
            os.makedirs(self.extract_dir, exist_ok=True)
            
            # Extract and flatten directory structure
            with zipfile.ZipFile(zip_filepath, "r") as zip_ref:
                # Log zip contents before extraction
                for info in zip_ref.filelist:
                    logging.info(f"Zip contains: {info.filename}, size: {info.file_size} bytes")
                    
                    # Skip directories
                    if info.filename.endswith('/'):
                        continue
                        
                    # Get just the filename without path
                    filename = os.path.basename(info.filename)
                    
                    # Only extract image files
                    if filename.lower().endswith(('.jpg', '.jpeg', '.png')):
                        # Extract to flattened directory
                        source = zip_ref.read(info.filename)
                        target_path = os.path.join(self.extract_dir, filename)
                        with open(target_path, 'wb') as f:
                            f.write(source)
                        logging.debug(f"Extracted {info.filename} to {target_path}")

            # Log extracted contents
            extracted_files = os.listdir(self.extract_dir)
            logging.info(f"Extracted {len(extracted_files)} files: {extracted_files}")

            files = self.file_list(self.extract_dir)
            logging.info(f"Found {len(files)} valid image files")
            return files

        except zipfile.BadZipFile as e:
            logging.error(f"Invalid zip file: {str(e)}")
            return None
        except Exception as e:
            logging.error(f"Error extracting zip file: {str(e)}")
            logging.error(traceback.format_exc())
            return None

    def file_list(self, file_dir):
        """
        Find all image files in directory (no need for recursion since directory is flat now)
        Returns list of tuples formatted for WebODM upload
        """
        images = []
        for file in os.listdir(file_dir):
            if file.lower().endswith(('.jpg', '.jpeg', '.png')):
                image_path = os.path.join(file_dir, file)
                try:
                    with open(image_path, "rb") as img_file:
                        images.append(
                            (
                                "images",
                                (file, img_file.read(), "image/png"),
                            )
                        )
                        # logging.debug(f"Added image: {image_path}")
                except Exception as e:
                    logging.error(f"Error reading image {image_path}: {str(e)}")
                    continue

        logging.info(f"Found {len(images)} total images in {file_dir}")
        return images

    # def init_nodeODM(self, project_id, files, color, node):
    #     index = color - 1

    #     taskurl = f"https://webodm.boshang.online/api/projects/{project_id}/tasks/"
    #     data = {
    #         "name": getName(TypeColor, color),
    #         "processing_node": node
    #     }
    #     try:
    #         response = requests.post(taskurl, headers=self.headers, files=files, data=data)
    #         response.raise_for_status()  # Raises an HTTPError for bad responses
    #         self.task_id[index] = response.json()['id']
    #     except requests.exceptions.RequestException as e:
    #         print(f"Error in init_nodeODM: {str(e)}", flush=True)
    #         raise

    #     if node == 1:
    def init_nodeODM(self, project_id, files, color):
        index = color - 1

        taskurl = f"https://webodm.boshang.online/api/projects/{project_id}/tasks/"
        data = {"name": getName(TypeColor, color), "processing_node": 1}
        try:
            response = requests.post(
                taskurl, headers=self.headers, files=files, data=data
            )
            response.raise_for_status()  # Raises an HTTPError for bad responses
            self.task_id[index] = response.json()["id"]
        except requests.exceptions.RequestException as e:
            print(f"Error in init_nodeODM: {str(e)}", flush=True)
            raise

        if color == 1:
            print(
                f"INSERT INTO whole_data (status) VALUES (3) for {getName(TypeColor, color)}",
                flush=True,
            )
            self.cursor.execute("INSERT INTO whole_data (status) VALUES (3)")
            self.mydb.commit()
            self.SQLid = self.cursor.lastrowid

    def post_task(self, project_id, color):
        index = color - 1

        self.cursor.execute(
            f"UPDATE whole_data SET status = {color + 4} WHERE uid = {self.SQLid}"
        )
        self.mydb.commit()

        while True:
            res = requests.get(
                f"https://webodm.boshang.online/api/projects/{project_id}/tasks/{self.task_id[index]}/",
                headers=self.headers,
            ).json()
            try:
                if res["status"] == 40:
                    print(
                        f"Task for {getName(TypeColor, color)} has completed!",
                        flush=True,
                    )
                    break
                elif res["status"] == 30:
                    print(f"{getName(TypeColor, color)} Task failed: {res}", flush=True)
                    self.cursor.execute(
                        f"UPDATE whole_data SET status = 2 WHERE uid = {self.SQLid}"
                    )
                    self.mydb.commit()
                    return f"{getName(TypeColor, color)} Task failed: {res}"
                else:
                    print(
                        f"Currently processing: {getName(TypeColor, color)}, hold on...",
                        flush=True,
                    )
                    time.sleep(30)
            except Exception as error:
                print(f"{getName(TypeColor, color)} Task failed: {res}", flush=True)
                self.cursor.execute(
                    f"UPDATE whole_data SET status = 2 WHERE uid = {self.SQLid}"
                )
                self.mydb.commit()
                print(error, flush=True)
                return f"{getName(TypeColor, color)} Task failed: {res}"

        colorName = getName(TypeColor, color)

        update_query = "UPDATE whole_data SET project_id = %s, %s = '%s', %s = '%s', %s = '%s', %s = '%s' WHERE uid = %s"
        tm_str = f"https://laimatt.boshang.online/downloadwebodm/{project_id}/{self.task_id[index]}/textured_model.glb"
        all_str = f"https://laimatt.boshang.online/downloadwebodm/{project_id}/{self.task_id[index]}/all.zip"
        pc_str = f"https://laimatt.boshang.online/downloadwebodm/{project_id}/{self.task_id[index]}/georeferenced_model.laz"
        update_data = (
            str(project_id),
            "task_id_" + colorName,
            self.task_id[index],
            "all_file_" + colorName,
            all_str,
            "las_file_" + colorName,
            pc_str,
            "glb_file_" + colorName,
            tm_str,
            str(self.SQLid),
        )
        toUpdate = update_query % update_data
        print(toUpdate)
        self.cursor.execute(toUpdate)
        self.mydb.commit()

        # if not color == 1:
        #     filter_from_webodm(project_id, self.task_id[index], color)
        #     create_components(project_id, self.task_id[index], self.SQLid, color)

        return None

    def create_task(self, file):
        self.temp_dir = None
        try:
            self.temp_dir = tempfile.mkdtemp()
            logging.info(f"Created temporary directory: {self.temp_dir}")

            # Save and validate uploaded file
            filename = secure_filename(file.filename)
            temp_path = os.path.join(self.temp_dir, filename)
            file.save(temp_path)
            
            file_size = os.path.getsize(temp_path)
            logging.info(f"Saved uploaded file: {filename}, size: {file_size} bytes")

            # Extract files into a list
            files = self.extract_files(temp_path)
            if files is None:
                return "Failed to process zip file - see logs for details\n"
            elif len(files) < 2:
                return f"Not enough images, images found: {len(files)}\n"

            projecturl = "https://webodm.boshang.online/api/projects/"
            data = {"name": "API_Call_threecolor"}
            project_id = requests.post(
                projecturl, headers=self.headers, data=data
            ).json()["id"]

            project_folder = f"projID_{project_id}"
            task_path = os.path.join("tasks", project_folder)
            if os.path.exists(task_path):
                print(task_path + " already exists, remaking", flush=True)
                shutil.rmtree(task_path)
            os.makedirs(task_path)

            og_image_path = os.path.join(task_path, "images")
            os.makedirs(og_image_path)

            pc_path = os.path.join(task_path, "pointclouds")
            subdirs = ["blue_spalls", "red_stains", "green_cracks"]
            for subdir in subdirs:
                os.makedirs(os.path.join(pc_path, subdir), exist_ok=True)

            shutil.copytree(self.extract_dir, og_image_path, dirs_exist_ok=True)

            remote_masks(project_folder)

            files_green_crack = f"/home/roboticslab/Developer/laimatt/laimatt_pdal/tasks/{project_folder}/images_out/filteredCrackOverlays/images"
            files_blue_spall = f"/home/roboticslab/Developer/laimatt/laimatt_pdal/tasks/{project_folder}/images_out/filteredSpallOverlays/images"
            files_red_stain = f"/home/roboticslab/Developer/laimatt/laimatt_pdal/tasks/{project_folder}/images_out/filteredStainOverlays/images"

            tasks = [
                (TypeColor.original.value, files),
                (TypeColor.green_cracks.value, self.file_list(files_green_crack)),
                (TypeColor.red_stains.value, self.file_list(files_red_stain)),
                (TypeColor.blue_spalls.value, self.file_list(files_blue_spall)),
            ]

            for color, files in tasks:
                self.init_nodeODM(project_id, files, color)
                result = self.post_task(project_id, color)
                if result is not None:
                    return f"Error processing task for {getName(TypeColor, color)}: {result}"
                time.sleep(10)  # Add a short delay between tasks

            self.cursor.execute(
                f"UPDATE whole_data SET status = 4 WHERE uid = {self.SQLid}"
            )
            self.mydb.commit()
            return "All tasks completed and clustered\n"
        except Exception as e:
            logging.error(f"Error in create_task: {str(e)}")
            logging.error(traceback.format_exc())
            # Don't cleanup on error to preserve files for debugging
            self.temp_dir = None  # Prevent cleanup in finally block
            raise
        finally:
            if self.temp_dir:  # Only cleanup if no errors occurred
                self.cleanup()

    def authenticate(self):
        url = "https://webodm.boshang.online/api/token-auth/"
        data = {"username": "authentication", "password": "authkeyword"}
        response = requests.post(url, data=data)

        self.headers = {"Authorization": f"JWT {response.json()['token']}"}
        return self.headers

    def getFilePath(self, project_id, task_id, request_type):
        try:
            task = requests.get(
                f"https://webodm.boshang.online/api/projects/{project_id}/tasks/{task_id}",
                headers=self.headers,
            ).json()
            available_assets = task["available_assets"]
        except:
            raise GetFileException("task or project not found")

        if request_type == "textured_model.glb":
            if "textured_model.zip" in available_assets:
                return f"https://webodm.boshang.online/api/projects/{project_id}/tasks/{task_id}/download/textured_model.glb"
            else:
                raise GetFileException("task found, but textured zip file not found")
        elif request_type == "georeferenced_model.laz":
            if "georeferenced_model.laz" in available_assets:
                return f"https://webodm.boshang.online/api/projects/{project_id}/tasks/{task_id}/download/georeferenced_model.laz"
            else:
                raise GetFileException("task found, but laz file not found")
        elif request_type == "all.zip":
            if "all.zip" in available_assets:
                return f"https://webodm.boshang.online/api/projects/{project_id}/tasks/{task_id}/download/all.zip"
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
        columns = [
            "center_lat",
            "center_long",
            "center_alt",
            "box_length",
            "box_width",
            "box_height",
            "uid",
        ]  # Replace with your actual column names

        query = f"SELECT {', '.join(columns)} FROM patch_crack LIMIT %s OFFSET %s"

        limit = end_row - start_row + 1
        offset = start_row - 1

        self.cursor.execute(query, (limit, offset))

        results = []
        for row in self.cursor:
            try:
                float_values = [float(value) for value in row]
                results.append(float_values)
            except ValueError as e:
                print(f"Error converting value to float: {e}", flush=True)

        return results


# API endpoint
@laimatt_app.route("/task", methods=["POST"])
def task_api():
    try:
        if "file" not in request.files:
            return jsonify({"error": "No file part in the request"}), 400

        file = request.files["file"]
        if file.filename == "":
            return jsonify({"error": "No file selected for uploading"}), 400

        # Log request details
        logging.info(f"Received file upload: {file.filename}")
        
        api.authenticate()
        result = api.create_task(file)
        return result

    except Exception as e:
        logging.error(f"Error processing upload: {str(e)}")
        logging.error(traceback.format_exc())
        return jsonify({
            "error": "An internal server error occurred",
            "details": str(e),
            "stack_trace": traceback.format_exc()
        }), 500


@laimatt_app.errorhandler(500)
def internal_error(error):
    print(f"500 error occurred: {str(error)}", file=sys.stderr)
    return (
        jsonify({"error": "An internal server error occurred", "details": str(error)}),
        500,
    )


@laimatt_app.route("/test", methods=["POST"])
def test_api():
    api.authenticate()

    project_id = 181
    task_id = "57e7cde0-c2d4-48d0-918b-f71b09702faf"
    uid = 23
    color = TypeColor.blue_spalls.value

    print("test)")

    return "clustering done\n"


@laimatt_app.route("/download/<project_id>/<type>/<filename>", methods=["GET"])
def download(project_id, type, filename):
    api.authenticate()

    task = os.path.join(laimatt_app.root_path, f"tasks/projID_{project_id}")
    uploads = os.path.join(
        task, f"tests/{type}_test_10_0.2_10000/component_las_10_0.2_10000"
    )

    if not (os.path.isfile(os.path.join(uploads, filename))):
        return "requested file does not exist"
    return send_file(os.path.join(uploads, filename), as_attachment=True)


@laimatt_app.route("/downloadwebodm/<project_id>/<task_id>/<filename>", methods=["GET"])
def downloadwebodm(project_id, task_id, filename):
    api.authenticate()
    try:
        url = api.getFilePath(project_id, task_id, filename)
    except GetFileException as e:
        return repr(e)

    response = requests.get(url, headers=api.authenticate())
    if response.content < 50:
        response = requests.get(url, headers=api.authenticate())

    if response.status_code == 200:
        file_stream = BytesIO(response.content)
        file_stream.seek(0)

        return send_file(file_stream, as_attachment=True, download_name=filename)
    else:
        return Response("Failed to fetch file from URL", status=response.status_code)


@laimatt_app.route("/")
def hello_geek():
    return render_template("index.html")


@laimatt_app.route("/analyze_crack", methods=["GET"])
def analyze_crack():
    try:
        x = float(request.args.get("x"))
        y = float(request.args.get("y"))
        z = float(request.args.get("z"))
        length = float(request.args.get("length"))
        width = float(request.args.get("width"))
        height = float(request.args.get("height"))

        min_bound, max_bound = api.get_bounding_box_corners(
            x, y, z, length, width, height
        )
        cracks = api.get_cracks()

        diagonal = 0
        for crack in cracks:
            if (
                crack[0] >= min_bound[0]
                and crack[0] <= max_bound[0]
                and crack[1] >= min_bound[1]
                and crack[1] <= max_bound[1]
                and crack[2] >= min_bound[2]
                and crack[2] <= max_bound[2]
            ):

                print(f"uid {crack[6]} chosen", flush=True)
                diagonal += math.sqrt(crack[3] ** 2 + crack[4] ** 2 + crack[5] ** 2)

        return str(diagonal)

    except Exception as e:
        print(f"Error in /analyze_crack: {str(e)}", flush=True)
        return jsonify({"error": "An error occurred during analysis."}), 500


api = WebODM_API()
if __name__ == "__main__":
    # run_gunicorn()

    # run as a flask app instead
    laimatt_app.run(host="0.0.0.0", port=57902, debug=True)
    # laimatt_app.run()
