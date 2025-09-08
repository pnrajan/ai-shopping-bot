from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    app_name: str = "InflectionCurator"
    openai_apikey: str = ''
    unwrangle_apikey: str = ''
    unwrangle_url: str = ''
    keepa_api_key: str = ''

    class Config:
        env_file = ".env"  # optional: load from .env file


settings = Settings()

if __name__ == '__main__':
    print(settings)
