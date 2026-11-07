from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app.database import connection, schema
from app.middleware import json_only
from app.routes import auth, canvases, health, pages, websocket


@asynccontextmanager
async def lifespan(app):
    await connection.connect()
    await schema.create()
    yield
    await connection.disconnect()


app = FastAPI(lifespan=lifespan, docs_url=None, redoc_url=None, openapi_url=None)
app.mount("/static", StaticFiles(directory="static"), name="static")
app.middleware("http")(json_only)

for module in (pages, health, auth, canvases, websocket):
    app.include_router(module.router)
