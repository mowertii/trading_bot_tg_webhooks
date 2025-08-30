FROM python:3.11-slim

WORKDIR /app

# Устанавливаем системные зависимости
RUN apt-get update && apt-get install -y \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Копируем и устанавливаем Python зависимости
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Копируем код приложения
COPY . .

# Устанавливаем переменные окружения
ENV PYTHONPATH="${PYTHONPATH}:/app"
ENV PYTHONUNBUFFERED=1

# Создаем non-root пользователя для безопасности
RUN useradd --create-home --shell /bin/bash app && chown -R app:app /app
USER app

# Открываем порт
EXPOSE 8080

# ИСПРАВЛЕННАЯ команда запуска - используем объект app вместо функции init_app
CMD ["python", "-m", "gunicorn", "--bind", "0.0.0.0:8080", "--worker-class", "aiohttp.GunicornWebWorker", "--workers", "1", "--access-logfile", "-", "--error-logfile", "-", "--log-level", "info", "webhook_server:app"]