# Редактор блок-схем

## Что сделано

- Перетаскивание блоков, изменение размера, правка текста, приближение.
- Совместная работа на сокетах: все видят правки сразу, блоки двигаются плавно.
- Сохранение в PostgreSQL, автоматическое переподключение при обрыве.
- Работа на компьютере и телефоне.

## Стек

- Python 3.13, FastAPI, Uvicorn
- WebSocket
- PostgreSQL 17, asyncpg
- JavaScript, HTML, CSS, Konva
- Docker, Docker Compose

## Структура

```text
flowchart/
  app/
    __init__.py
    db.py
    main.py
  static/
    app.js
    index.html
    style.css
  Dockerfile
  docker-compose.yml
  requirements.txt
```