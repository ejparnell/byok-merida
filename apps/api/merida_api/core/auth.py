import secrets

from fastapi import Header, HTTPException

from .settings import Settings


def capture_token_dependency(settings: Settings):
    async def require_capture_token(
        x_capture_token: str = Header(alias="X-Capture-Token"),
    ) -> None:
        if not settings.capture_token_configured or not x_capture_token or not secrets.compare_digest(
            x_capture_token, settings.capture_token
        ):
            raise HTTPException(
                status_code=401,
                detail={
                    "code": "invalid_capture_token",
                    "message": "A valid X-Capture-Token header is required.",
                },
            )

    return require_capture_token
