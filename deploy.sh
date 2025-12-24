#!/bin/bash

# Скрипт для деплоя бота на VPS

set -e

echo "🚀 Начинаем деплой Domastroi Bot..."

# Проверяем Python
if ! command -v python3 &> /dev/null; then
    echo "❌ Python3 не установлен. Установите Python3."
    exit 1
fi

# Создаем директорию для бота
BOT_DIR="/opt/domastroi-bot"
echo "📁 Создаем директорию $BOT_DIR..."
sudo mkdir -p $BOT_DIR

# Копируем файлы
echo "📋 Копируем файлы..."
sudo cp bot.py requirements.txt $BOT_DIR/
sudo cp .env $BOT_DIR/ 2>/dev/null || echo "⚠️  Файл .env не найден. Создайте его вручную."

# Создаем виртуальное окружение
echo "🐍 Создаем виртуальное окружение..."
cd $BOT_DIR
sudo python3 -m venv venv
sudo $BOT_DIR/venv/bin/pip install --upgrade pip
sudo $BOT_DIR/venv/bin/pip install -r requirements.txt

# Устанавливаем systemd service
echo "⚙️  Устанавливаем systemd service..."
sudo cp domastroi-bot.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable domastroi-bot.service

# Запускаем бота
echo "▶️  Запускаем бота..."
sudo systemctl start domastroi-bot.service

# Проверяем статус
sleep 2
if sudo systemctl is-active --quiet domastroi-bot.service; then
    echo "✅ Бот успешно запущен!"
    echo "📊 Статус: sudo systemctl status domastroi-bot"
    echo "📝 Логи: sudo journalctl -u domastroi-bot -f"
else
    echo "❌ Ошибка при запуске бота. Проверьте логи: sudo journalctl -u domastroi-bot -n 50"
    exit 1
fi

