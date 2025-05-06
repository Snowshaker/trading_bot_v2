# src/telegram_bot/handlers/control_handlers.py
import logging

from telegram import Update
from telegram.ext import ContextTypes, CommandHandler
# Импортируем TELEGRAM_ADMINS из указанного пути
from src.core.settings.telegram_config import TELEGRAM_ADMINS

logger = logging.getLogger(__name__)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # В python-telegram-bot информация о пользователе доступна через update.effective_user
    user = update.effective_user
    if user and user.id in TELEGRAM_ADMINS:
        await update.message.reply_html(
            f"🚀 Привет, {user.mention_html()}! Я ваш торговый бот.\n\n"
            "Доступные команды:\n"
            "/balance - Показать баланс\n"
            "/analysis - Показать анализ рынка\n"
            "/history [N] - История сделок (последние N записей)\n"
            "/buy - Купить актив\n"
            "/sell - Продать актив"
        )
    elif user: # Если пользователь не админ, но есть информация о пользователе
        logger.info(f"Пользователь {user.id} ({user.username}) попытался использовать команду /start, но не является админом.")
        await update.message.reply_text(
            "Извините, у вас нет доступа к этому боту."
        )
    else: # На случай, если по какой-то причине нет update.effective_user
        logger.warning("Команда /start вызвана без информации о пользователе.")
        await update.message.reply_text(
            "Не удалось определить пользователя. Попробуйте позже."
        )


def get_control_handlers():
    return [CommandHandler("start", start)]