from pydantic import BaseModel, Field

from app import config


class Account(BaseModel):
    login: str = Field(max_length=64)
    password: str = Field(max_length=200)
    password_confirm: str = Field(default="", max_length=200)


class CanvasData(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=config.CANVAS_TITLE_MAX)
    access: int | None = Field(default=None, ge=0, le=2)
