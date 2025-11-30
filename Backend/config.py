from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    NEXTCLOUD_URL: str
    NC_USERNAME: str
    NC_PASSWORD: str

    class Config:
        env_file = ".env"

settings = Settings()