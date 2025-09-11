from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    app_name: str = "InflectionCurator"

    # AI/LLM API Keys
    openai_apikey: str = ""
    anthropic_api_key: str = ""
    gemini_api_key: str = ""

    # Product Search APIs
    unwrangle_apikey: str = ""
    unwrangle_url: str = ""
    unwrangle_search_url: str = ""
    keepa_api_key: str = ""

    class Config:
        env_file = ".env"  # optional: load from .env file


settings = Settings()

if __name__ == "__main__":
    print(settings)
