from fastapi import Request, Response


async def json_only(request: Request, call_next):
    if request.method in ("POST", "PATCH") and request.url.path.startswith("/api/"):
        if not request.headers.get("content-type", "").startswith("application/json"):
            return Response("Нужен JSON", status_code=415)
    return await call_next(request)
