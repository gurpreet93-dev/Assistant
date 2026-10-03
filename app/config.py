import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Settings:
    anthropic_api_key: str = os.getenv("ANTHROPIC_API_KEY", "")
    agent_model: str = os.getenv("AGENT_MODEL", "claude-opus-5-5")
    agent_effort: str = os.getenv("AGENT_EFFORT", "low")
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
