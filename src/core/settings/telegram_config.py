# src/settings/telegram_config.py
import os
from dotenv import load_dotenv

# Загружаем переменные окружения из файла .env (если он есть)
load_dotenv()

# Получаем токен из переменных окружения или напрямую
TELEGRAM_BOT_TOKEN: str = os.getenv("TELEGRAM_BOT_TOKEN", "замените_меня")  # ВАЖНО: замените на токен вашего телеграм бота

# ID администраторов (получи свой ID у @userinfobot в Telegram)
# Можно также брать из переменных окружения, если нужно
TELEGRAM_ADMINS: list[int] = [1111111111111111111111111] # ВАЖНО: замените 1111111111111111111111111 на свой телеграм id

# Настройки логирования для Telegram бота
LOGGING_CONFIG_TG = {
    'filename': 'logs/telegram_logs/telegram_bot.log',
    'level': 'INFO', # Уровень логирования (DEBUG, INFO, WARNING, ERROR, CRITICAL)
    'format': '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
}

if TELEGRAM_BOT_TOKEN == "замените_меня":
    print("!!! ВНИМАНИЕ: Укажите ваш TELEGRAM_BOT_TOKEN в src/settings/telegram_config.py или через переменную окружения !!!")

if not TELEGRAM_ADMINS or TELEGRAM_ADMINS == [1111111111111111111111111]:
     print("!!! ВНИМАНИЕ: Укажите ваш TELEGRAM_ADMIN_ID в src/settings/telegram_config.py !!!")