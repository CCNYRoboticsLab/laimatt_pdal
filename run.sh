#!/bin/sh
exec gunicorn -c gunicorn.conf.py fullcall_ODM_API:laimatt_app

# echo "I am running on a container"
# echo "attempting conda activate"
# python fullcall_ODM_API.py
# sleep 100000
# # conda init
# # ~/.bashrc
# # conda activate .conda
# python fullcall_ODM_API.py