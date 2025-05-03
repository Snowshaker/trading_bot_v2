# src/telegram_bot/handlers/control_handlers.py
import logging

from aiogram.types import user
from telegram import Update
from telegram.ext import ContextTypes, CommandHandler
from src.core.settings.telegram_config import TELEGRAM_ADMINS

logger = logging.getLogger(__name__)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if user.id in TELEGRAM_ADMINS:
        await update.message.reply_html(
            f"🚀 Привет, {user.mention_html()}! Я ваш торговый бот.\n\n"
            "Доступные команды:\n"
            "/balance - Показать баланс\n"
            "/analysis - Показать анализ рынка\n"
            "/history [N] - История сделок (последние N записей)\n"
            "/buy - Купить актив\n"
            "/sell - Продать актив"
        )

def get_control_handlers():
    return [CommandHandler("start", start)]