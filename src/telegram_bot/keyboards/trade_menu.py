# src/telegram_bot/keyboards/trade_menu.py
from telegram import InlineKeyboardButton, InlineKeyboardMarkup

def get_symbols_keyboard(symbols):
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(sym, callback_data=sym)] for sym in symbols
    ])