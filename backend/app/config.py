from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    DATABASE_URL: str = "mysql+mysqlconnector://root:devpassword@mysql:3306/layover_lens"
    DATA_SOURCE: str = "mock"

    class Config:
        env_file = ".env"


settings = Settings()
