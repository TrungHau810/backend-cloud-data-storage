# Dùng FastAPI và các thành phần trong requirements.txt chỉnh lại app.py (cấu hình Flask khá cũ)
# Do server dùng sẵn MariaDB và Nextcloud nên không cần lo database MySQL

# Tạo file .env lưu thông tin sau:
NEXTCLOUD_URL=https://sentoru.qzz.io
NC_USERNAME=sentoru
NC_PASSWORD=binkiller1

# Dùng thư viện dưới để bắt đầu file app.py, tạm thời bỏ phần GET /quota nha
from fastapi import FastAPI, UploadFile, File, Form
from fastapi.responses import JSONResponse
import requests
from config import settings

app = FastAPI()
