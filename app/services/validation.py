import re

from fastapi import HTTPException

from app import config

LOGIN_PATTERN = re.compile(rf"^[A-Za-z0-9_.-]{{{config.LOGIN_MIN},{config.LOGIN_MAX}}}$")


def check_login(login):
    if not LOGIN_PATTERN.match(login):
        raise HTTPException(
            422, f"Логин: от {config.LOGIN_MIN} до {config.LOGIN_MAX} латинских букв, цифр и знаков _ . -"
        )


def check_password(password, confirm):
    if len(password) < config.PASSWORD_MIN:
        raise HTTPException(422, f"Пароль должен быть не короче {config.PASSWORD_MIN} символов")
    if len(password) > config.PASSWORD_MAX:
        raise HTTPException(422, "Пароль слишком длинный")
    if password != confirm:
        raise HTTPException(422, "Пароли не совпадают")
