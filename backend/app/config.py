"""Voice agent backend settings, read from backend/.env. This service has NO database access:
all sales data comes from the Sales MCP server (MCP_SERVER_URL)."""
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # ---- LLM (OpenAI-compatible API; Groq for now) ----
    llm_base_url: str = "https://api.groq.com/openai/v1"
    llm_api_key: str = ""
    llm_model: str = "openai/gpt-oss-120b"
    llm_reasoning_effort: str = "low"        # gpt-oss: low / medium / high (low = fast)
    llm_temperature: float = 0.2
    max_tool_rounds: int = 6

    # ---- Speech-to-Text (Groq Whisper) ----
    stt_model: str = "whisper-large-v3-turbo"
    stt_language: str = ""                    # "" = auto detect, "hi" = Hindi, "en" = English

    # ---- Sales MCP server (deployed separately) ----
    mcp_server_url: str = "http://127.0.0.1:8001/mcp"
    mcp_auth_token: str = ""                  # same value as MCP_AUTH_TOKEN in mcp-server/.env
    mcp_timeout_seconds: float = 60

    # ---- Business ----
    timezone: str = "Asia/Kolkata"
    business_day_start_hour: int = 5          # keep the same value as in mcp-server/.env
    restaurant_name: str = "Restaurant"
    support_contact: str = ""                 # shown when the help library has no answer, e.g. "call 98xxxxxx or support@..."
    as_of_date: str = ""                      # testing only: treat this date (YYYY-MM-DD) as "today"

    # ---- Logging / monitoring ----
    log_level: str = "INFO"
    log_format: str = "text"                  # "json" = one JSON object per line (best for Application Insights queries)
    log_file: str = ""                        # e.g. logs/backend.log for local runs; leave empty on Azure (use Application Insights)
    log_questions: bool = True                # include the user's question text in logs
    slow_request_ms: int = 15000              # requests slower than this are logged as WARNING

    # ---- API ----
    cors_origins: str = "http://localhost:5173,http://127.0.0.1:5173"


settings = Settings()
