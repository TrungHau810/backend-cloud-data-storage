import requests
from fastapi import APIRouter, Form
from starlette.responses import JSONResponse

from config import settings

router = APIRouter()

# -----------------------
# USER PROFILE
# -----------------------
@router.post("/me")
def get_my_profile(
        username: str = Form(...),
        password: str = Form(...)
):
    auth = (username, password)

    url = f"{settings.NEXTCLOUD_URL}/ocs/v1.php/cloud/user"
    headers = {
        "OCS-APIRequest": "true",
        "Accept": "application/json"
    }

    r = requests.get(url, auth=auth, headers=headers)

    if r.status_code != 200 or "ocs" not in r.text:
        return JSONResponse(
            status_code=401,
            content={"error": "Invalid credentials"}
        )

    data = r.json()["ocs"]["data"]

    return {
        "id": data["id"],
        "display_name": data["display-name"],
        "email": data["email"],
        "quota": {
            "used": data["quota"]["used"],
            "free": data["quota"]["free"],
            "total": data["quota"]["quota"],
            "relative": data["quota"].get("relative", 0)
        },
        "last_login": data.get("lastlogin")
    }


# -----------------------
# UPDATE USER PROFILE
# -----------------------
@router.post("/me/update")
def update_my_profile(
        username: str = Form(...),
        password: str = Form(...),
        displayname: str = Form(None),
        email: str = Form(None),
        new_password: str = Form(None)
):
    auth = (username, password)

    url = f"{settings.NEXTCLOUD_URL}/ocs/v1.php/cloud/users/{username}"
    headers = {
        "OCS-APIRequest": "true",
        "Accept": "application/json"
    }

    # Map field -> Nextcloud key
    updates = {
        "displayname": displayname,
        "email": email,
        "password": new_password
    }

    for key, value in updates.items():
        if value:
            r = requests.put(
                url,
                auth=auth,
                headers=headers,
                data={
                    "key": key,
                    "value": value
                }
            )

            if r.status_code != 200:
                return JSONResponse(
                    status_code=400,
                    content={
                        "error": f"Failed to update {key}",
                        "detail": r.text
                    }
                )

    return {
        "status": "success",
        "message": "Cập nhật thông tin thành công"
    }