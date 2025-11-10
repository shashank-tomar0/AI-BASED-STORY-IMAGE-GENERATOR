import requests
r = requests.post('http://127.0.0.1:5000/api/auth/register', json={'username':'testuser','password':'testpass'})
print(r.status_code, r.text)
