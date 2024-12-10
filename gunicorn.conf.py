import os

def is_docker():
    return os.path.exists('/.dockerenv') or os.getenv('DOCKER_ENV') == 'true'

if is_docker():
    print("Running inside Docker")
else:
    print("Running outside Docker")

bind = '0.0.0.0:57902'
workers = 4
worker_memory_limit = 20 * 1024 * 1024 # 20mb
timeout = 86400
graceful_timeout = 86400 # 24 hours
import os

# config_file = 'docker_config.yaml' if is_docker() else 'local_config.yaml'
errorlog = '/app/gunicorn_logs/gunicorn-error.log' if is_docker() else '/home/roboticslab/Developer/laimatt/laimatt_pdal/gunicorn_logs/gunicorn-error.log'
accesslog = '/app/gunicorn_logs/gunicorn-access.log' if is_docker() else '/home/roboticslab/Developer/laimatt/laimatt_pdal/gunicorn_logs/gunicorn-access.log'
loglevel = 'debug'
capture_output = True
