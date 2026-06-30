# config.py — pydantic-settings. .env.local > .env. token/chat_id 는 env 에만.
from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # DB (별도 reins DB — D3)
    DB_HOST: str = "127.0.0.1"
    DB_PORT: int = 5432
    DB_NAME: str = "reins"
    DB_USER: str = "reins"
    DB_PASSWORD: str = "changeme"

    PORT: int = 21001
    LOG_LEVEL: str = "info"

    # API token 인증 (로컬/skills 원격). 비어있으면 인증 건너뜀(로컬 개발 편의).
    REINS_API_TOKEN: str = ""

    # Telegram (outbound-only — D5). 미설정 시 dispatcher 스킵.
    TELEGRAM_BOT_TOKEN: str = ""
    # 발신 대상 chat_id. 포럼 그룹 chat_id.
    TELEGRAM_CHAT_ID: str = ""
    # topic 자동생성 폭증 가드. 미설정 시 provisioner 자동생성 無.
    TELEGRAM_DEFAULT_CHAT_ID: str = ""

    # Telegram webhook 수신(/api/telegram/webhook). 미설정 시 secret 검증 스킵(로컬).
    TELEGRAM_WEBHOOK_SECRET: str = ""
    # 콜백 허용 from.id 화이트리스트(콤마 구분). 미설정 시 스킵(로컬). 운영 필수.
    TELEGRAM_ALLOWED_CHAT_IDS: str = ""

    # GitHub 자동 머지(resolve approved + gate merge → PR squash 머지). 토큰 미설정 시 머지 스킵.
    GITHUB_TOKEN: str = ""
    GITHUB_REPO_OWNER: str = "whsanha55"
    GITHUB_REPO_NAME: str = "reins"

    # Watchdog (heartbeat 정체 감지). 0=off.
    WATCHDOG_INTERVAL_SEC: int = 300
    WATCHDOG_STALE_SEC: int = 1800  # 30분 무업데이트 → stalled

    # 아침 다이제스트 cron(로컬 launchd 가 대행 가능). 서버내 스케줄 0=off.
    DIGEST_CRON_HOUR: int = 8  # KST 매일 08시(기본)

    CORS_ORIGINS: str = "http://localhost:21002,http://localhost:3000"

    # 알림 내 티켓 딥링크 base (#27). 운영 보드 URL.
    PUBLIC_BASE_URL: str = "https://reins.gonamu.com"

    model_config = SettingsConfigDict(
        env_file=(".env.local", ".env"), env_file_encoding="utf-8", extra="ignore"
    )

    @property
    def database_url(self) -> str:
        return (
            f"postgresql://{self.DB_USER}:{self.DB_PASSWORD}"
            f"@{self.DB_HOST}:{self.DB_PORT}/{self.DB_NAME}"
        )

    @property
    def cors_origins(self) -> list[str]:
        return [o.strip() for o in self.CORS_ORIGINS.split(",") if o.strip()]


settings = Settings()
