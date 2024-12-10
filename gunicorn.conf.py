import os
from datetime import datetime

def is_docker():
    return os.path.exists('/.dockerenv') or os.getenv('DOCKER_ENV') == 'true'

# Print startup debug information
print(f"[{datetime.now().isoformat()}] Starting Gunicorn server")
if is_docker():
    print("[CONFIG] Running inside Docker")
else:
    print("[CONFIG] Running outside Docker")

bind = '0.0.0.0:57902'
print(f"[CONFIG] Binding to: {bind}")

workers = 4
print(f"[CONFIG] Number of workers: {workers}")

worker_memory_limit = 20 * 1024 * 1024  # 20mb
print(f"[CONFIG] Worker memory limit: {worker_memory_limit} bytes ({worker_memory_limit/1024/1024}MB)")

timeout = 86400
graceful_timeout = 86400  # 24 hours
print(f"[CONFIG] Timeout settings: {timeout}s ({timeout/3600}h)")

# Set up logging paths
errorlog = '/app/gunicorn_logs/gunicorn-error.log' if is_docker() else '/home/roboticslab/Developer/laimatt/laimatt_pdal/gunicorn_logs/gunicorn-error.log'
accesslog = '/app/gunicorn_logs/gunicorn-access.log' if is_docker() else '/home/roboticslab/Developer/laimatt/laimatt_pdal/gunicorn_logs/gunicorn-access.log'

print(f"[CONFIG] Error log path: {errorlog}")
print(f"[CONFIG] Access log path: {accesslog}")

# Verify log directories exist
log_dir = os.path.dirname(errorlog)
if not os.path.exists(log_dir):
    print(f"[WARNING] Log directory does not exist: {log_dir}")
    try:
        os.makedirs(log_dir)
        print(f"[CONFIG] Created log directory: {log_dir}")
    except Exception as e:
        print(f"[ERROR] Failed to create log directory: {str(e)}")

loglevel = 'debug'
print(f"[CONFIG] Log level: {loglevel}")

capture_output = True
print(f"[CONFIG] Capture output: {capture_output}")

# Print system information
print(f"[CONFIG] Current working directory: {os.getcwd()}")
print(f"[CONFIG] Python executable: {os.sys.executable}")
print(f"[CONFIG] Python version: {os.sys.version}")
