from __future__ import annotations

from fastapi import HTTPException, status


class AppError(HTTPException):
    def __init__(
        self,
        code: str,
        message: str,
        http_status: int = status.HTTP_400_BAD_REQUEST,
        extra: dict[str, object] | None = None,
    ):
        super().__init__(
            status_code=http_status,
            detail={"code": code, "message": message, **(extra or {})},
        )


def upstream_unconfigured(provider: str) -> AppError:
    return AppError(
        code=f"{provider.upper()}_UNCONFIGURED",
        message=f"{provider} credentials or endpoint are not configured.",
        http_status=status.HTTP_503_SERVICE_UNAVAILABLE,
    )
