FROM python:3.13-slim
WORKDIR /srv
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt && useradd --system app
COPY app ./app
COPY static ./static
ADD --chmod=644 https://cdn.jsdelivr.net/npm/konva@10.0.2/konva.min.js ./static/konva.min.js
USER app
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--ws-max-size", "16384", "--no-access-log"]
