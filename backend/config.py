from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    db_host: str = "localhost"
    db_port: int = 5432
    db_name: str = "warehouse_db"
    db_user: str = "postgres"
    db_pass: str = "postgres"

    @property
    def database_url(self) -> str:
        return f"postgresql://{self.db_user}:{self.db_pass}@{self.db_host}:{self.db_port}/{self.db_name}"

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8", "extra": "ignore"}

settings = Settings()