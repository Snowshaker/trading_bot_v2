# src/telegram_bot/bot.py
import logging
from telegram.ext import ApplicationBuilder
from src.core.settings.telegram_config import TELEGRAM_BOT_TOKEN
from src.core.paths import COLLECTED_DATA
from src.telegram_bot.handlers import (
  info_handlers,
  control_handlers,
  config_handlers,
  trade_handlers
)

logging.basicConfig(
  format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
  level=logging.INFO
)

class TradingBot:
    def __init__(self):
        # Проверка путей
        print(f"Data storage: {COLLECTED_DATA.absolute()}")

def setup_handlers(application):
  # Основные команды управления
  for handler in control_handlers.get_control_handlers():
    application.add_handler(handler)

  # Информационные команды
  for handler in info_handlers.get_info_handlers():
    application.add_handler(handler)

  # Торговые команды
  for handler in trade_handlers.get_trade_handlers():
    application.add_handler(handler)


def main():
  try:
    application = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).build()
    setup_handlers(application)
    logging.info("Starting telegram bot")
    application.run_polling()

  except Exception as e:
    logging.critical(f"Start error: {str(e)}", exc_info=True)


if __name__ == '__main__':
  main()