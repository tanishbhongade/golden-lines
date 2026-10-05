from langchain_aws import BedrockEmbeddings

from app.core.config import settings


def get_embeddings() -> BedrockEmbeddings:
    return BedrockEmbeddings(
        model_id=settings.embedding_model,
        region_name=settings.aws_region,
    )