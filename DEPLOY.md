# Инструкция по деплою на VPS

## Подготовка

1. **Создайте файл `.env`** на основе `.env.example`:
```bash
cp .env.example .env
nano .env
```

Заполните значения:
- `BOT_TOKEN` - токен бота от @BotFather
- `CHAT_ID` - ID чата для заявок (отрицательное число)
- `ADMIN_IDS` - ID админов через запятую

## Вариант 1: Автоматический деплой (рекомендуется)

1. Загрузите файлы на VPS:
```bash
scp -r bot.py requirements.txt .env.example domastroi-bot.service deploy.sh user@your-vps:/tmp/
```

2. На VPS выполните:
```bash
chmod +x /tmp/deploy.sh
sudo /tmp/deploy.sh
```

## Вариант 2: Ручной деплой

### 1. Подключитесь к VPS
```bash
ssh user@your-vps
```

### 2. Установите зависимости системы
```bash
sudo apt update
sudo apt install -y python3 python3-pip python3-venv
```

### 3. Создайте директорию для бота
```bash
sudo mkdir -p /opt/domastroi-bot
cd /opt/domastroi-bot
```

### 4. Загрузите файлы проекта
```bash
# Через scp с локальной машины:
scp bot.py requirements.txt .env user@your-vps:/opt/domastroi-bot/
```

### 5. Создайте виртуальное окружение
```bash
sudo python3 -m venv venv
sudo venv/bin/pip install --upgrade pip
sudo venv/bin/pip install -r requirements.txt
```

### 6. Создайте файл `.env`
```bash
sudo nano .env
```

Вставьте:
```
BOT_TOKEN=ваш_токен
CHAT_ID=-1003650005079
ADMIN_IDS=765740972,6933111964
```

### 7. Установите systemd service
```bash
sudo nano /etc/systemd/system/domastroi-bot.service
```

Вставьте содержимое из `domastroi-bot.service` (обновите пути если нужно).

### 8. Запустите бота
```bash
sudo systemctl daemon-reload
sudo systemctl enable domastroi-bot.service
sudo systemctl start domastroi-bot.service
```

### 9. Проверьте статус
```bash
sudo systemctl status domastroi-bot.service
```

## Управление ботом

### Просмотр логов
```bash
sudo journalctl -u domastroi-bot -f
```

### Перезапуск
```bash
sudo systemctl restart domastroi-bot.service
```

### Остановка
```bash
sudo systemctl stop domastroi-bot.service
```

### Статус
```bash
sudo systemctl status domastroi-bot.service
```

## Обновление бота

1. Загрузите новый `bot.py`:
```bash
scp bot.py user@your-vps:/opt/domastroi-bot/
```

2. Перезапустите:
```bash
sudo systemctl restart domastroi-bot.service
```

## Устранение проблем

### Бот не запускается
```bash
# Проверьте логи
sudo journalctl -u domastroi-bot -n 50

# Проверьте .env файл
sudo cat /opt/domastroi-bot/.env

# Проверьте права доступа
sudo ls -la /opt/domastroi-bot/
```

### Ошибки с правами доступа
```bash
sudo chown -R root:root /opt/domastroi-bot/
sudo chmod +x /opt/domastroi-bot/bot.py
```

### Бот не отвечает
- Проверьте токен в `.env`
- Убедитесь что бот запущен: `sudo systemctl status domastroi-bot`
- Проверьте логи на ошибки

