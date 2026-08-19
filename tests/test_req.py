import requests

url = "http://127.0.0.1:8000/urls/"
headers = {
    "accept": "application/json",
    "Authorization": "Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiJ0ZXN0MDEiLCJleHAiOjE3ODY5NzcwNzh9.fKXhfYLoyyfeWAsTlbFKG9ntvUl7mS1r4AHM4OqYutw"  # 这里替换成你刚才拿到的 token
}
data = {
    "original_url": "https://www.baidu.com"
}

response = requests.post(url, headers=headers, json=data)
print(response.status_code)
print(response.json())