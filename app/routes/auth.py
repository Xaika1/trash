from fastapi import APIRouter, Depends, HTTPException, Request, Response

from app.database import users
from app.schemas import Account
from app.services import passwords, rate_limit, sessions, validation

router = APIRouter(prefix="/api")


@router.post("/register")
async def register(data: Account, request: Request, response: Response):
    rate_limit.guard(request.client.host)
    validation.check_login(data.login)
    validation.check_password(data.password, data.password_confirm)
    user = await users.add(data.login, await passwords.hash_password(data.password))
    if not user:
        raise HTTPException(409, "Такой логин уже занят")
    await sessions.start(request, response, user["id"])
    return {"login": user["login"]}


@router.post("/login")
async def login(data: Account, request: Request, response: Response):
    rate_limit.guard(request.client.host)
    user = await users.get_by_login(data.login)
    if not user or not await passwords.verify_password(data.password, user["password_hash"]):
        raise HTTPException(401, "Неверный логин или пароль")
    await sessions.start(request, response, user["id"])
    return {"login": user["login"]}


@router.post("/logout")
async def logout(request: Request, response: Response):
    await sessions.end(request, response)
    return {"status": "ok"}


@router.get("/me")
async def me(user=Depends(sessions.current_user)):
    return {"login": user["login"]}
