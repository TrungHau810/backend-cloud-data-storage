from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    NEXTCLOUD_URL: str
    NC_USERNAME: str
    NC_PASSWORD: str

    VNPAY_TMNCODE: str
    VNPAY_HASH_SECRET_KEY: str
    VNPAY_PAYMENT_URL: str
    VNPAY_RETURN_URL: str

    PARTNER_CODE: str
    MOMO_ACCESS_KEY: str
    MOMO_SECRET_KEY: str
    ENDPOINT: str
    MOMO_RETURN_URL: str

    class Config:
        env_file = ".env"

settings = Settings()