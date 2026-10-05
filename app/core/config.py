from dotenv import load_dotenv
from pydantic_settings import BaseSettings, SettingsConfigDict

load_dotenv()  # populates os.environ for boto3 and anything else that reads it


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Postgres
    pg_host: str
    pg_port: int
    pg_user: str
    pg_password: str
    pg_database: str

    # AWS Bedrock
    aws_region: str
    aws_bearer_token_bedrock: str

    # Embeddings
    embedding_model: str
    embedding_dimension: int

    # LLM
    llm_model: str

    @property
    def conninfo(self) -> str:
        return (
            f"host={self.pg_host} port={self.pg_port} "
            f"user={self.pg_user} password={self.pg_password} "
            f"dbname={self.pg_database}"
        )


settings = Settings()
