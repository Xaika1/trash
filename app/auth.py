import asyncio
import hashlib
import hmac
import re
import secrets
import time

from fastapi import HTTPException, Request

from app import db

COOKIE = "session"
SESSION_DAYS = 30
LOGIN_PATTERN = re.compile(r"^[A-Za-z0-9_.-]{3,32}$")
MIN_PASSWORD = 8

attempts = {}


def make_hash(password):
    salt = secrets.token_bytes(16)
    digest = hashlib.scrypt(password.encode(), salt=salt, n=2**14, r=8, p=1)
    return f"{salt.hex()}${digest.hex()}"


def check_hash(password, stored):
    salt, digest = stored.split("$")
    new_digest = hashlib.scrypt(password.encode(), salt=bytes.fromhex(salt), n=2**14, r=8, p=1)
    return hmac.compare_digest(new_digest.hex(), digest)


async def hash_password(password):
    return await asyncio.to_thread(make_hash, password)


async def verify_password(password, stored):
    return await asyncio.to_thread(check_hash, password, stored)


def token_hash(token):
    return hashlib.sha256(token.encode()).hexdigest()


def check_login(login):
    if not LOGIN_PATTERN.match(login):
        raise HTTPException(422, "Логин: от 3 до 32 латинских букв, цифр и знаков _ . -")


def check_password(password, confirm):
    if len(password) < MIN_PASSWORD:
        raise HTTPException(422, f"Пароль должен быть не короче {MIN_PASSWORD} символов")
    if len(password) > 128:
        raise HTTPException(422, "Пароль слишком длинный")
    if password != confirm:
        raise HTTPException(422, "Пароли не совпадают")


def too_many_attempts(ip):
    now = time.time()
    recent = [moment for moment in attempts.get(ip, []) if now - moment < 60]
    attempts[ip] = recent
    if len(recent) >= 10:
        return True
    recent.append(now)
    return False


async def start_session(response, user_id):
    token = secrets.token_urlsafe(32)
    await db.add_session(token_hash(token), user_id, SESSION_DAYS)
    response.set_cookie(COOKIE, token, max_age=SESSION_DAYS * 86400, httponly=True, samesite="lax")


async def end_session(request, response):
    token = request.cookies.get(COOKIE)
    if token:
        await db.delete_session(token_hash(token))
    response.delete_cookie(COOKIE)


async def find_user(token):
    if not token:
        return None
    return await db.get_session_user(token_hash(token))


async def current_user(request: Request):
    user = await find_user(request.cookies.get(COOKIE))
    if not user:
        raise HTTPException(401, "Нужно войти")
    return user
