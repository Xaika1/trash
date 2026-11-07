FROM python:3.13-slim
WORKDIR /srv
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt && useradd --system app
COPY app ./app
COPY static ./static
ADD --chmod=644 https://cdn.jsdelivr.net/npm/konva@10.0.2/konva.min.js ./static/konva.min.js
ADD --chmod=644 https://cdn.jsdelivr.net/npm/jspdf@4.2.1/dist/jspdf.umd.min.js ./static/jspdf.min.js
USER app
CMD ["sh", "-c", "exec uvicorn app.main:app --host 0.0.0.0 --port \"$APP_PORT\" --ws-max-size \"$WS_MAX_SIZE\" --no-access-log --proxy-headers --forwarded-allow-ips '*'"]
