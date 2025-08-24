
#!/bin/bash

# deploy.sh - Скрипт для развертывания webhook бота

set -e  # Выходим при первой ошибке

echo "🚀 Начинаем развертывание webhook бота..."

# Проверяем, что мы в правильной директории
if [ ! -f "docker-compose.yml" ]; then
    echo "❌ Файл docker-compose.yml не найден. Убедитесь, что вы в корневой директории проекта."
    exit 1
fi

# Проверяем наличие .env файла
if [ ! -f ".env" ]; then
    echo "❌ Файл .env не найден. Создайте его на основе .env.example"
    exit 1
fi

# Создаем директорию для SSL сертификатов
echo "📁 Создаем директорию для SSL сертификатов..."
mkdir -p ssl

# Останавливаем старые контейнеры
echo "🛑 Останавливаем старые контейнеры..."
docker-compose down --remove-orphans

# Собираем образы
echo "🔨 Собираем Docker образы..."
docker-compose build --no-cache

# Запускаем сервисы
echo "▶️  Запускаем сервисы..."
if [ -f "ssl/fullchain.pem" ] && [ -f "ssl/privkey.pem" ]; then
    echo "🔒 Запускаем с SSL (production режим)"
    docker-compose --profile production up -d
else
    echo "⚠️  Запускаем без SSL (development режим)"
    docker-compose up -d webhook-bot redis db
fi

# Проверяем статус
echo "🔍 Проверяем статус сервисов..."
sleep 5
docker-compose ps

# Проверяем health check
echo "🏥 Проверяем health check..."
if curl -f http://localhost:8080/health > /dev/null 2>&1; then
    echo "✅ Webhook сервер запущен и отвечает!"
else
    echo "❌ Webhook сервер не отвечает. Проверьте логи:"
    echo "   docker-compose logs webhook-bot"
    exit 1
fi

echo ""
echo "🎉 Развертывание завершено!"
echo ""
echo "📡 Webhook URL: https://webhook.mowertii.ru/webhook"
echo "🏥 Health check: https://webhook.mowertii.ru/health"
echo ""
echo "📋 Полезные команды:"
echo "   docker-compose logs -f webhook-bot  # Смотреть логи"
echo "   docker-compose restart webhook-bot  # Перезапустить бот"
echo "   docker-compose down                 # Остановить все"
echo ""

# Показываем пример webhook запроса
echo "📝 Пример webhook запроса:"
echo "curl -X POST https://webhook.mowertii.ru/webhook \\"
echo "  -H 'Content-Type: application/json' \\"
echo "  -d '{\"action\": \"buy\", \"symbol\": \"SBER\", \"risk_percent\": 0.4}'"