from fastapi import APIRouter, Form
from starlette.responses import JSONResponse
import requests
from config import settings

router = APIRouter()

# -----------------------
# Helpers
# -----------------------
def normalize_path(username: str, filepath: str) -> str:
    """
    - Decode URL
    - Remove WebDAV prefix if exists
    - Return path dạng: /Documents/a.pdf
    """
    filepath = requests.utils.unquote(filepath)

    prefix = f"/remote.php/dav/files/{username}/"
    if filepath.startswith(prefix):
        filepath = filepath[len(prefix):]

    filepath = filepath.lstrip("/")
    return f"/{filepath}"


def permissions(can_edit: bool) -> int:
    return 15 if can_edit else 1


def ocs_headers():
    return {
        "OCS-APIRequest": "true",
        "Accept": "application/json"
    }


def ocs_error(resp):
    try:
        data = resp.json()
        return data.get("ocs", {}).get("meta", {}).get("message", resp.text)
    except Exception:
        return resp.text


# -----------------------
# SHARE PUBLIC LINK
# -----------------------
@router.post("/share-file")
def share_file(
    username: str = Form(...),
    password: str = Form(...),
    filepath: str = Form(...),
    share_password: str = Form(None),
    expire_date: str = Form(None),  # YYYY-MM-DD
    can_edit: bool = Form(False)
):
    auth = (username, password)
    path = normalize_path(username, filepath)

    url = f"{settings.NEXTCLOUD_URL}/ocs/v2.php/apps/files_sharing/api/v1/shares"

    payload = {
        "path": path,
        "shareType": 3,  # public link
        "permissions": permissions(can_edit)
    }

    if share_password:
        payload["password"] = share_password
    if expire_date:
        payload["expireDate"] = expire_date

    r = requests.post(url, headers=ocs_headers(), data=payload, auth=auth)

    if r.status_code not in (200, 201):
        return JSONResponse(status_code=400, content={"error": ocs_error(r)})

    data = r.json()["ocs"]["data"]

    return {
        "share_id": data["id"],
        "url": data["url"],
        "token": data["token"],
        "permissions": data["permissions"],
        "expiration": data.get("expiration")
    }


# -----------------------
# SHARE TO USER
# -----------------------
@router.post("/share-to-user")
def share_to_user(
    username: str = Form(...),
    password: str = Form(...),
    filepath: str = Form(...),
    target_user: str = Form(...),
    can_edit: bool = Form(False)
):
    auth = (username, password)
    path = normalize_path(username, filepath)

    url = f"{settings.NEXTCLOUD_URL}/ocs/v2.php/apps/files_sharing/api/v1/shares"

    payload = {
        "path": path,
        "shareType": 0,  # user
        "shareWith": target_user,
        "permissions": permissions(can_edit)
    }

    r = requests.post(url, headers=ocs_headers(), data=payload, auth=auth)

    if r.status_code not in (200, 201):
        return JSONResponse(status_code=400, content={"error": ocs_error(r)})

    return r.json()["ocs"]["data"]


# -----------------------
# LIST SHARES
# -----------------------
@router.post("/list-shares")
def list_shares(
    username: str = Form(...),
    password: str = Form(...),
    filepath: str = Form(...)
):
    auth = (username, password)
    path = normalize_path(username, filepath)

    url = (
        f"{settings.NEXTCLOUD_URL}"
        f"/ocs/v2.php/apps/files_sharing/api/v1/shares"
        f"?path={path}&reshares=true"
    )

    r = requests.get(url, headers=ocs_headers(), auth=auth)

    if r.status_code != 200:
        return JSONResponse(status_code=400, content={"error": ocs_error(r)})

    return r.json()["ocs"]["data"]


# -----------------------
# DELETE SHARE
# -----------------------
@router.post("/delete-share")
def delete_share(
    username: str = Form(...),
    password: str = Form(...),
    share_id: int = Form(...)
):
    auth = (username, password)

    url = (
        f"{settings.NEXTCLOUD_URL}"
        f"/ocs/v2.php/apps/files_sharing/api/v1/shares/{share_id}"
    )

    r = requests.delete(url, headers=ocs_headers(), auth=auth)

    if r.status_code not in (200, 204):
        return JSONResponse(status_code=400, content={"error": ocs_error(r)})

    return {"status": "success"}
