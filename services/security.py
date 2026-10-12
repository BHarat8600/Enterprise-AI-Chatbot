from datetime import UTC, datetime, timedelta
from typing import Any

from jose import jwt

from config.settings import Settings


def create_access_token(subject: str, settings: Settings, minutes: int = 60) -> str:
    payload: dict[str, Any] = {
        "sub": subject,
        "exp": datetime.now(UTC) + timedelta(minutes=minutes),
        "iat": datetime.now(UTC),
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm="HS256")


def decode_access_token(token: str, settings: Settings) -> dict[str, Any]:
    return jwt.decode(token, settings.jwt_secret, algorithms=["HS256"])

