import hashlib
import secrets

from fastapi import HTTPException, Request

from app import config
from app.database import sessions


def token_hash(token):
    return hashlib.sha256(token.encode()).hexdigest()


async def start(request, response, user_id):
    token = secrets.token_urlsafe(32)
    await sessions.add(token_hash(token), user_id, config.SESSION_DAYS)
    secure = request.headers.get("x-forwarded-proto") == "https"
    response.set_cookie(
        config.SESSION_COOKIE,
        token,
        max_age=config.SESSION_DAYS * 86400,
        httponly=True,
        samesite="lax",
        secure=secure,
    )


async def end(request, response):
    token = request.cookies.get(config.SESSION_COOKIE)
    if token:
        await sessions.delete(token_hash(token))
    response.delete_cookie(config.SESSION_COOKIE)


async def find_user(token):
    if not token:
        return None
    return await sessions.get_user(token_hash(token))


async def current_user(request: Request):
    user = await find_user(request.cookies.get(config.SESSION_COOKIE))
    if not user:
        raise HTTPException(401, "Нужно войти")
    return user
