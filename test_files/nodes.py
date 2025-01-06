import requests

def authenticate():
    url = "http://localhost:8000/api/token-auth/"
    data = {
        "username": "laimatt",
        "password": "WA30Bj4Tam20"
    }
    response = requests.post(url, data=data)
    return response.json()['token']



url = 'http://localhost:8000/api/processingnodes/'
token = authenticate()
headers = {'Authorization': 'JWT {}'.format(token)}
    # Send a GET request to the URL
response = requests.get(url, headers=headers)
print(response.content)