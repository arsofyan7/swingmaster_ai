import requests
r = requests.get("http://127.0.0.1:8000/api/v1/portfolios/1/dashboard")
data = r.json()
print("Status:", data.get("status"))
print("IHSG history length:", len(data.get("ihsg_history", [])))
if len(data.get("ihsg_history", [])) > 0:
    print("First item:", data["ihsg_history"][0])
    print("Last item:", data["ihsg_history"][-1])
else:
    print("Error / Empty response:", data)
