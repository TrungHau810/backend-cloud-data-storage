import requests
from fastapi import FastAPI, Form
from fastapi.responses import JSONResponse

from config import settings

app = FastAPI()


# def connect_db():
#     return mysql.connector.connect(**DB_CONFIG)


@app.post("/register")
def register(username: str = Form(...), password: str = Form(...)):
    api_url = f"{settings.NEXTCLOUD_URL}/ocs/v1.php/cloud/users"

    payload = {"userid": username, "password": password}
    headers = {"OCS-APIRequest": "true"}

    res = requests.post(
        api_url,
        auth=(settings.NC_USERNAME, settings.NC_PASSWORD),
        data=payload,
        headers=headers
    )

    if res.status_code not in (200, 201):
        return JSONResponse({"status": "error", "msg": "Failed to create user"}, status_code=400)

    return {"status": "success", "msg": "User created successfully!"}


@app.post("/login")
def login(username: str = Form(...), password: str = Form(...)):
    res = requests.request(
        "PROPFIND",
        f"{settings.NEXTCLOUD_URL}/remote.php/dav/files/{username}/",
        auth=(username, password)
    )

    if res.status_code == 207:
        return {"status": "success", "token": f"mock-token-{username}"}

    return JSONResponse({"status": "error", "msg": "Invalid credentials"}, status_code=401)


@app.get("/usage")
def usage(username: str):
    api_url = f"{settings.NEXTCLOUD_URL}/ocs/v2.php/apps/files/api/v1/storage?format=json"

    res = requests.get(
        api_url,
        auth=(username, ""),  # Nextcloud chỉ validate username ở API này
        headers={"OCS-APIRequest": "true"}
    )

    if res.status_code != 200:
        return JSONResponse({"error": "User not found"}, status_code=404)

    data = res.json()

    if "ocs" not in data:
        return JSONResponse({"error": "Invalid response"}, status_code=500)

    return data["ocs"]["data"]


# @app.post("/payment")
# def payment(data: PaymentRequest):
#     username = data.username
#     amount = data.amount
#
#     try:
#         db = connect_db()
#         cursor = db.cursor()
#
#         cursor.execute(
#             "INSERT INTO payments (username, amount) VALUES (%s, %s)",
#             (username, amount)
#         )
#         db.commit()
#
#         return {"status": "success", "msg": "Payment recorded!"}
#
#     except Exception as e:
#         return JSONResponse({"db_error": str(e)}, status_code=500)


@app.get('/')
def home():
    return {"message": "Welcome to the Cloud Storage Service API"}
