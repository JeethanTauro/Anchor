from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):

    database_url: str
    rabbitmq_url: str

    chroma_host: str
    chroma_port: int

    groq_api_key:str
    groq_model:str


settings = Settings()