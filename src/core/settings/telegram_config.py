# src/settings/telegram_config.py
import os
from dotenv import load_dotenv

# Загружаем переменные окружения из файла .env (если он есть)
load_dotenv()

# Получаем токен из переменных окружения или напрямую
TELEGRAM_BOT_TOKEN: str = os.getenv("TELEGRAM_BOT_TOKEN", "8121531273:AAH4qB0wAgUfTKmyAAp8YoIDLiqmiBDr8bk")

# ID администраторов (получи свой ID у @userinfobot в Telegram)
# Можно также брать из переменных окружения, если нужно
TELEGRAM_ADMINS: list[int] = [1098620579] # Замени на свой ID

# Настройки логирования для Telegram бота
LOGGING_CONFIG_TG = {
    'filename': 'logs/telegram_logs/telegram_bot.log',
    'level': 'INFO', # Уровень логирования (DEBUG, INFO, WARNING, ERROR, CRITICAL)
    'format': '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
}

if TELEGRAM_BOT_TOKEN == "ТВОЙ_БОТ_ТОКЕН_СЮДА":
    print("!!! ВНИМАНИЕ: Укажите ваш TELEGRAM_BOT_TOKEN в src/settings/telegram_config.py или через переменную окружения !!!")

if not TELEGRAM_ADMINS or TELEGRAM_ADMINS == [123456789]:
     print("!!! ВНИМАНИЕ: Укажите ваш TELEGRAM_ADMIN_ID в src/settings/telegram_config.py !!!")