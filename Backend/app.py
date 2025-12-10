import xml.etree.ElementTree as ET
from fastapi import FastAPI, UploadFile, File, Form
from fastapi.responses import JSONResponse
import requests
from config import settings
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # or list domain Vercel
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
def home():
    return {"message": "Backend running successfully!"}


# -----------------------
# REGISTER USER
# -----------------------
@app.post("/register")
def register(username: str = Form(...), password: str = Form(...)):
    url = f"{settings.NEXTCLOUD_URL}/ocs/v1.php/cloud/users"
    headers = {
        "OCS-APIRequest": "true"
    }

    payload = {"userid": username, "password": password, "format": "json"}
    auth = (settings.NC_USERNAME, settings.NC_PASSWORD)

    r = requests.post(url, auth=auth, headers=headers, data=payload)

    if r.status_code in [200, 201]:
        return {"message": f"User {username} created successfully!"}
    return JSONResponse(status_code=400, content={"error": r.text})


# -----------------------
# LOGIN USER
# -----------------------
@app.post("/login")
def login(username: str = Form(...), password: str = Form(...)):
    auth = (username, password)
    url = f"{settings.NEXTCLOUD_URL}/ocs/v1.php/cloud/user"
    headers = {
        "OCS-APIRequest": "true"
    }

    r = requests.get(url, auth=auth, headers=headers)

    if r.status_code == 200:
        return {"message": "Login successful"}
    return JSONResponse(status_code=401, content={"error": "Invalid credentials"})


# -----------------------
# UPLOAD FILE
# -----------------------
@app.post("/upload")
async def upload_to_nextcloud(file: UploadFile = File(...), username: str = Form(...), password: str = Form(...)):
    upload_url = f"{settings.NEXTCLOUD_URL}/remote.php/dav/files/{username}/{file.filename}"
    data = await file.read()

    headers = {
        "Content-Type": file.content_type
    }

    r = requests.put(upload_url, data=data, headers=headers, auth=(username, password))

    if r.status_code in [200, 201, 204]:
        return {"status": "success", "file": file.filename}
    return JSONResponse(status_code=400, content={"error": r.text})


# -----------------------
# PAYMENT (FAKE)
# -----------------------
@app.post("/payment")
def payment(username: str = Form(...), amount: float = Form(...)):
    return {"message": f"Payment of {amount}$ recorded for {username}"}


# -----------------------
# QUOTA API
# -----------------------
@app.post("/quota")
def get_quota(username: str = Form(...), password: str = Form(...)):
    auth = (username, password)
    url = f"{settings.NEXTCLOUD_URL}/ocs/v1.php/cloud/user"
    headers = {
        "OCS-APIRequest": "true",
        "Accept": "application/json"
    }

    r = requests.get(url, auth=auth, headers=headers)

    if r.status_code != 200 or "ocs" not in r.text:
        return JSONResponse(status_code=401, content={"error": "Invalid credentials"})

    quota = r.json()["ocs"]["data"]["quota"]

    return {
        "used": quota["used"],
        "available": quota["free"],
        "total": quota["quota"],
        "relative": quota.get("relative", 0)
    }


# -----------------------
# DASHBOARD API
# -----------------------
@app.post("/dashboard")
def get_dashboard(username: str = Form(...), password: str = Form(...)):
    auth = (username, password)

    # 1) Lấy thông tin user
    user_url = f"{settings.NEXTCLOUD_URL}/ocs/v1.php/cloud/user"
    headers = {
        "OCS-APIRequest": "true",
        "Accept": "application/json"
    }

    user_info = requests.get(user_url, auth=auth, headers=headers)

    if user_info.status_code != 200 or "ocs" not in user_info.text:
        return JSONResponse(status_code=401, content={"error": "Invalid credentials"})

    user_data = user_info.json()["ocs"]["data"]
    quota = user_data["quota"]

    # 2) PROPFIND để đếm file
    dav_url = f"{settings.NEXTCLOUD_URL}/remote.php/dav/files/{username}/"
    dav_headers = {
        "Depth": "1",
        "Content-Type": "application/xml"
    }

    propfind_body = """
        <d:propfind xmlns:d="DAV:">
            <d:prop>
                <d:getcontentlength />
            </d:prop>
        </d:propfind>
    """

    dav_response = requests.request("PROPFIND", dav_url, data=propfind_body, headers=dav_headers, auth=auth)

    file_count = 0
    if dav_response.status_code == 207:
        root = ET.fromstring(dav_response.text)
        file_count = len(root.findall("{DAV:}response")) - 1  # trừ folder root

    # 3) Dashboard response
    return {
        "username": user_data["id"],
        "display_name": user_data["display-name"],
        "email": user_data["email"],
        "quota": {
            "used": quota["used"],
            "available": quota["free"],
            "total": quota["quota"],
            "relative": quota.get("relative", 0)
        },
        "file_count": max(file_count, 0),
        "last_login": user_data.get("lastlogin")
    }


@app.post("/list-files")
def list_files(username: str = Form(...), password: str = Form(...)):
    auth = (username, password)

    url = f"{settings.NEXTCLOUD_URL}/remote.php/dav/files/{username}/"

    headers = {
        "Depth": "1",
        "Content-Type": "application/xml"
    }

    propfind_body = """
        <d:propfind xmlns:d="DAV:">
            <d:prop>
                <d:getlastmodified />
                <d:getcontentlength />
                <d:getcontenttype />
            </d:prop>
        </d:propfind>
    """

    response = requests.request("PROPFIND", url, data=propfind_body, headers=headers, auth=auth)

    if response.status_code != 207:
        return JSONResponse(status_code=400, content={"error": response.text})

    root = ET.fromstring(response.text)

    files = []

    # Parse XML
    for resp in root.findall("{DAV:}response"):
        href = resp.find("{DAV:}href").text

        # Bỏ thư mục root user/
        if href.endswith(f"/dav/files/{username}/"):
            continue

        props = resp.find("{DAV:}propstat/{DAV:}prop")

        size = props.find("{DAV:}getcontentlength")
        modified = props.find("{DAV:}getlastmodified")
        ctype = props.find("{DAV:}getcontenttype")

        files.append({
            "path": href,
            "name": href.split("/")[-1],
            "size": int(size.text) if size is not None and size.text else 0,
            "last_modified": modified.text if modified is not None else None,
            "type": ctype.text if ctype is not None else "folder"
        })

    return {"files": files}
