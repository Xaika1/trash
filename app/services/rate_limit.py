import time

from fastapi import HTTPException

from app import config

attempts = {}


def too_many_attempts(ip):
    now = time.time()
    recent = [moment for moment in attempts.get(ip, []) if now - moment < config.LOGIN_WINDOW]
    attempts[ip] = recent
    if len(recent) >= config.LOGIN_ATTEMPTS:
        return True
    recent.append(now)
    return False


def guard(ip):
    if too_many_attempts(ip):
        raise HTTPException(429, "Слишком много попыток, подождите минуту")
