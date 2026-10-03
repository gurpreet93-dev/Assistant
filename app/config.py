import os
from dataclasses import dataclass

from dotenv import load_dotenv

load_dotenv()  # reads .env from the working directory; real environment variables win


@dataclass(frozen=True)
class Settings:
    anthropic_api_key: str = os.getenv("ANTHROPIC_API_KEY", "")
    agent_model: str = os.getenv("AGENT_MODEL", "claude-haiku-4-5")
    pinecone_api_key: str = os.getenv("PINECONE_API_KEY", "")
    pinecone_index: str = os.getenv("PINECONE_INDEX", "call-agent-kb")
    pinecone_cloud: str = os.getenv("PINECONE_CLOUD", "aws")
    pinecone_region: str = os.getenv("PINECONE_REGION", "us-east-1")
    # Knowledge bases at or below this size go straight into the prompt (cached);
    # above it the contractor is switched to Pinecone retrieval automatically.
    kb_full_context_max_tokens: int = int(os.getenv("KB_FULL_CONTEXT_MAX_TOKENS", "30000"))
    session_secret: str = os.getenv("SESSION_SECRET", "dev-only-secret-change-me")
    public_base_url: str = os.getenv("PUBLIC_BASE_URL", "http://localhost:8000")
    twilio_auth_token: str = os.getenv("TWILIO_AUTH_TOKEN", "")
    ms_tenant_id: str = os.getenv("MS_TENANT_ID", "")
    ms_client_id: str = os.getenv("MS_CLIENT_ID", "")
    ms_client_secret: str = os.getenv("MS_CLIENT_SECRET", "")
    database_path: str = os.getenv("DATABASE_PATH", "data/app.db")

    @property
    def graph_enabled(self) -> bool:
        return bool(self.ms_tenant_id and self.ms_client_id and self.ms_client_secret)


settings = Settings()
