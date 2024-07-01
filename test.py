import requests

def authenticate():
    url = "http://localhost:8000/api/token-auth/"
    data = {
        "username": "laimatt",
        "password": "WA30Bj4Tam20"
    }
    response = requests.post(url, data=data)
    
    return {'Authorization': 'JWT {}'.format(response.json()['token'])}


headers = authenticate()
task = requests.get('http://localhost:8000/api/processingnodes',
                    headers=headers).json()['id']  
print(task)