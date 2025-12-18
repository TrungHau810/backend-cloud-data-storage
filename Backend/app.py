import datetime
import io
import json
import string
import time
import urllib
import xml.etree.ElementTree as ET
import random

from fastapi import FastAPI, UploadFile, File, Form, Request, HTTPException
from fastapi.responses import JSONResponse
import requests
from starlette.responses import PlainTextResponse, StreamingResponse

from config import settings
from fastapi.middleware.cors import CORSMiddleware

from momo import create_momo_signature
from vnpay import create_vnpay_signature

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # or list domain Vercel
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

with open("plans.json", "r", encoding="utf-8") as f:
    PLANS = json.load(f)["plans"]


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


@app.get("/view-file")
def view_file(
        username: str = Form(...),
        password: str = Form(...),
        filepath: str = Form(...)
):
    auth = (username, password)

    # Normalize input
    # 1) Decode %20 -> space
    filepath = requests.utils.unquote(filepath)

    # 2) Remove any prefix before the user's actual file path
    # Example: /remote.php/dav/files/test/Templates credits.md
    prefix = f"/remote.php/dav/files/{username}/"

    if filepath.startswith(prefix):
        filepath = filepath[len(prefix):]

    # 3) Remove extra "/"
    filepath = filepath.lstrip("/")

    # Build real WebDAV URL
    url = f"{settings.NEXTCLOUD_URL}/remote.php/dav/files/{username}/{filepath}"

    r = requests.get(url, auth=auth)

    if r.status_code != 200:
        return JSONResponse(status_code=400, content={"error": r.text})

    return PlainTextResponse(content=r.text)


@app.post("/download-file")
def download_file(
        username: str = Form(...),
        password: str = Form(...),
        filepath: str = Form(...)
):
    auth = (username, password)

    # 1) Decode URL encoding (vd: %20 -> space)
    filepath = requests.utils.unquote(filepath)

    # 2) Prefix WebDAV đầy đủ nếu user gửi nguyên đường dẫn
    webdav_prefix = f"/remote.php/dav/files/{username}/"
    if filepath.startswith(webdav_prefix):
        filepath = filepath[len(webdav_prefix):]

    # 3) Xóa dấu "/" thừa
    filepath = filepath.lstrip("/")

    # 4) Build URL gửi tới Nextcloud
    nc_url = f"{settings.NEXTCLOUD_URL}/remote.php/dav/files/{username}/{filepath}"

    # 5) Gửi request dạng stream để không load toàn bộ file vào RAM
    r = requests.get(nc_url, auth=auth, stream=True)

    if r.status_code != 200:
        return JSONResponse(status_code=400, content={"error": r.text})

    # 6) Tách tên file
    filename = filepath.split("/")[-1]

    # 7) Trả về StreamingResponse để client tải file trực tiếp
    return StreamingResponse(
        r.iter_content(chunk_size=8192),  # stream từng phần
        media_type="application/octet-stream",
        headers={
            "Content-Disposition": f"attachment; filename={filename}"
        }
    )


# -----------------------
# DELETE FILE OR FOLDER
# -----------------------
@app.post("/delete")
def delete_file_or_folder(
        username: str = Form(...),
        password: str = Form(...),
        filepath: str = Form(...)
):
    auth = (username, password)

    # 1) Decode URL encoding (%20 -> space)
    filepath = requests.utils.unquote(filepath)

    # 2) Nếu client gửi full path WebDAV thì cắt prefix
    webdav_prefix = f"/remote.php/dav/files/{username}/"
    if filepath.startswith(webdav_prefix):
        filepath = filepath[len(webdav_prefix):]

    # 3) Bỏ dấu "/" dư
    filepath = filepath.lstrip("/")

    # 4) Build URL WebDAV
    url = f"{settings.NEXTCLOUD_URL}/remote.php/dav/files/{username}/{filepath}"

    # 5) Gửi DELETE request
    r = requests.delete(url, auth=auth)

    if r.status_code in [200, 204]:
        return {
            "status": "success",
            "message": f"Deleted successfully: {filepath}"
        }

    return JSONResponse(
        status_code=400,
        content={
            "status": "error",
            "message": r.text
        }
    )


@app.post("/payment/vnpay/create")
def create_vnpay_payment(
        request: Request,
        username: str = Form(...),
        plan: str = Form(...)
):
    if plan not in PLANS:
        return JSONResponse(status_code=400, content={"error": "Invalid plan"})

    # Tạo order_id
    order_id = "".join(random.choices(string.digits, k=10))

    # Thời gian hiện tại
    now = datetime.datetime.now()
    create_date = now.strftime("%Y%m%d%H%M%S")
    expire_date = (now + datetime.timedelta(minutes=15)).strftime("%Y%m%d%H%M%S")

    # Số tiền (VNPay yêu cầu nhân 100)
    amount = int(PLANS[plan]["amount"] * 100)

    vnp_params = {
        "vnp_Version": "2.1.0",
        "vnp_Command": "pay",
        "vnp_TmnCode": settings.VNPAY_TMNCODE,
        "vnp_Amount": amount,
        "vnp_CurrCode": "VND",
        "vnp_TxnRef": f"{order_id}-{int(now.timestamp())}",  # order_id + timestamp
        "vnp_OrderInfo": f"Thanh toan goi {plan} cho nguoi dung {username}",
        "vnp_OrderType": "other",
        "vnp_Locale": "vn",
        "vnp_ReturnUrl": settings.VNPAY_RETURN_URL,
        "vnp_IpAddr": request.client.host if request.client else "127.0.0.1",
        "vnp_CreateDate": create_date,
        "vnp_ExpireDate": expire_date,
    }

    # Tạo chữ ký bảo mật
    secure_hash = create_vnpay_signature(vnp_params)
    vnp_params["vnp_SecureHash"] = secure_hash

    # Tạo URL thanh toán
    payment_url = (
            settings.VNPAY_PAYMENT_URL
            + "?"
            + urllib.parse.urlencode(vnp_params)
    )

    return {
        "payment_url": payment_url,
        "order_id": order_id
    }


@app.post("/payment/momo/create")
def create_momo_payment(
        username: str = Form(...),
        plan: str = Form(...)
):
    if plan not in PLANS:
        raise HTTPException(status_code=400, detail="Invalid plan")

    order_id = f"MOMO{int(time.time())}"
    request_id = order_id
    amount = str(PLANS[plan]["amount"])

    order_info = f"Thanh toan goi {plan} cho nguoi dung {username}"
    extra_data = ""

    raw_signature = (
        f"accessKey={settings.MOMO_ACCESS_KEY}"
        f"&amount={amount}"
        f"&extraData={extra_data}"
        f"&ipnUrl={settings.MOMO_RETURN_URL}"
        f"&orderId={order_id}"
        f"&orderInfo={order_info}"
        f"&partnerCode={settings.PARTNER_CODE}"
        f"&redirectUrl={settings.MOMO_RETURN_URL}"
        f"&requestId={request_id}"
        f"&requestType=captureWallet"
    )

    signature = create_momo_signature(
        raw_signature,
        settings.MOMO_SECRET_KEY
    )

    payload = {
        "partnerCode": settings.PARTNER_CODE,
        "accessKey": settings.MOMO_ACCESS_KEY,
        "requestId": request_id,
        "amount": amount,
        "orderId": order_id,
        "orderInfo": order_info,
        "redirectUrl": settings.MOMO_RETURN_URL,
        "ipnUrl": settings.MOMO_RETURN_URL,
        "extraData": extra_data,
        "requestType": "captureWallet",
        "signature": signature,
        "lang": "vi"
    }

    response = requests.post(settings.ENDPOINT, json=payload, timeout=10)
    result = response.json()

    if result.get("resultCode") != 0:
        return JSONResponse(status_code=400, content=result)

    return {
        "payUrl": result["payUrl"],
        "orderId": order_id
    }


@app.post("/payment/notify")
async def momo_notify(request: Request):
    data = await request.json()

    raw_signature = (
        f"accessKey={data['accessKey']}"
        f"&amount={data['amount']}"
        f"&extraData={data['extraData']}"
        f"&message={data['message']}"
        f"&orderId={data['orderId']}"
        f"&orderInfo={data['orderInfo']}"
        f"&orderType={data['orderType']}"
        f"&partnerCode={data['partnerCode']}"
        f"&payType={data['payType']}"
        f"&requestId={data['requestId']}"
        f"&responseTime={data['responseTime']}"
        f"&resultCode={data['resultCode']}"
        f"&transId={data['transId']}"
    )

    signature = hmac.new(
        SECRET_KEY.encode(),
        raw_signature.encode(),
        hashlib.sha256
    ).hexdigest()

    if signature != data["signature"]:
        return {"status": "invalid signature"}

    if data["resultCode"] == 0:
        # TODO: nâng dung lượng Nextcloud
        pass

    return {"status": "ok"}