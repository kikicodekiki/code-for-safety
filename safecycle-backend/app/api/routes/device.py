"""
SafeCycle Sofia — Device token registration.
POST /device-token — register or update an FCM push notification token.
"""
from __future__ import annotations

from typing import Literal

import structlog
from fastapi import APIRouter, Depends, Response, status
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import get_db

logger = structlog.get_logger(__name__)

router = APIRouter(tags=["devices"])


class DeviceTokenCreate(BaseModel):
    token: str
    platform: Literal["ios", "android"]
    user_id: str | None = None


@router.post(
    "/device-token",
    status_code=status.HTTP_204_NO_CONTENT,
    response_class=Response,
    summary="Register FCM device token",
    description="""
Register or update a Firebase Cloud Messaging (FCM) device token.
Used to send push notifications for nearby hazards, crossroad alerts,
and awareness zone warnings.

This endpoint is idempotent — re-registering an existing token updates
the platform and timestamp without creating a duplicate.
""",
)
async def register_device_token(
    payload: DeviceTokenCreate,
    db: AsyncSession = Depends(get_db),
) -> Response:
    stmt = text("""
        INSERT INTO device_tokens (token, platform, user_id, created_at, updated_at)
        VALUES (:token, :platform, :user_id, NOW(), NOW())
        ON CONFLICT (token)
        DO UPDATE SET
            platform   = EXCLUDED.platform,
            user_id    = EXCLUDED.user_id,
            updated_at = NOW()
    """)

    await db.execute(
        stmt,
        {
            "token": payload.token,
            "platform": payload.platform,
            "user_id": payload.user_id,
        },
    )
    await db.commit()

    logger.info(
        "device_token_registered",
        platform=payload.platform,
        has_user_id=payload.user_id is not None,
    )

    return Response(status_code=status.HTTP_204_NO_CONTENT)