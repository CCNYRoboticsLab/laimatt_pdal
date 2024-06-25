import subprocess
import csv
import pandas as pd
import laspy
import glob
import mysql.connector
import os
import sys
import shutil
from flask import Flask, request, send_file

def add_files(project_id, task_id):
    webodm_path = '/var/lib/docker/volumes/webodm_appmedia/_data/project/{}/task/{}/assets/'.format(project_id, task_id) + 'ccny_postprocessing'
    os.makedirs(webodm_path, exist_ok=True)
    
