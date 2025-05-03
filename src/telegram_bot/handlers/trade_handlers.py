# src/telegram_bot/handlers/trade_handlers.py
import logging
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import (
  ContextTypes,
  CommandHandler,
  MessageHandler,
  filters,
  ConversationHandler,
  CallbackQueryHandler
)
from decimal import Decimal
from src.core.settings.telegram_config import TELEGRAM_ADMINS
from src.core.api.binance_client.transactions_executor import TransactionsExecutor
from src.core.api.binance_client.info_fetcher import BinanceInfoFetcher
from src.telegram_bot.services.formatters import format_balance
from src.core.settings.config import SYMBOLS, BINANCE_API_KEY, BINANCE_SECRET_KEY, TESTNET

logger = logging.getLogger(__name__)

# Состояния для ConversationHandler
SELECT_SYMBOL, ENTER_QUANTITY, CONFIRM_TRADE = range(3)


class TradeHandlers:
  def __init__(self):
    self.executor = TransactionsExecutor()
    self.info_fetcher = BinanceInfoFetcher(
          api_key=BINANCE_API_KEY,
          api_secret=BINANCE_SECRET_KEY,
          testnet=TESTNET
    )
    self.current_action = None

  async def check_admin(self, update: Update) -> bool:
    user = update.effective_user
    if user.id not in TELEGRAM_ADMINS:
      await update.message.reply_text("⛔ У вас нет прав для выполнения этой операции")
      return False
    return True

  async def start_trade(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if not await self.check_admin(update):
      return ConversationHandler.END

    self.current_action = update.message.text[1:].lower()
    symbols = self._get_available_symbols()

    keyboard = [
      [InlineKeyboardButton(symbol, callback_data=symbol)]
      for symbol in symbols
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await update.message.reply_text(
      "Выберите торговую пару:",
      reply_markup=reply_markup
    )
    return SELECT_SYMBOL

  async def select_symbol(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()

    context.user_data['symbol'] = query.data
    await query.edit_message_text(
      f"Выбрана пара: {query.data}\nВведите количество для {self.current_action}:"
    )
    return ENTER_QUANTITY

  async def enter_quantity(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    try:
      quantity = Decimal(update.message.text)
      context.user_data['quantity'] = quantity

      symbol = context.user_data['symbol']
      current_price = self.info_fetcher.get_current_price(symbol)

      await update.message.reply_text(
        f"Подтвердите операцию:\n"
        f"Символ: {symbol}\n"
        f"Количество: {quantity}\n"
        f"Примерная стоимость: {quantity * current_price:.2f} USDT\n\n"
        "Отправить ордер?",
        reply_markup=InlineKeyboardMarkup([
          [InlineKeyboardButton("✅ Да", callback_data="confirm"),
           InlineKeyboardButton("❌ Отмена", callback_data="cancel")]
        ])
      )
      return CONFIRM_TRADE
    except Exception as e:
      await update.message.reply_text("❌ Некорректное количество. Попробуйте снова")
      return ENTER_QUANTITY

  async def confirm_trade(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()

    if query.data == "cancel":
      await query.edit_message_text("❌ Операция отменена")
      return ConversationHandler.END

    try:
      symbol = context.user_data['symbol']
      quantity = context.user_data['quantity']
      action = self.current_action.upper()

      result = self.executor.execute_order(
        symbol=symbol,
        side="BUY" if action == "BUY" else "SELL",
        quantity=float(quantity),
        order_type="MARKET"
      )

      if result:
        await query.edit_message_text(
          f"✅ Успешный {action}:\n"
          f"Исполнено: {result['executedQty']} {symbol}\n"
          f"Средняя цена: {result['fills'][0]['price']}"
        )
        # Показываем обновленный баланс
        balance = self.info_fetcher.get_asset_balance(symbol.replace("USDT", ""))
        await query.message.reply_text(
          f"Новый баланс:\nСвободно: {balance['free']}\nЗаблокировано: {balance['locked']}"
        )
      else:
        await query.edit_message_text("❌ Не удалось исполнить ордер")

    except Exception as e:
      logger.error(f"Trade error: {str(e)}", exc_info=True)
      await query.edit_message_text(f"❌ Ошибка: {str(e)}")

    return ConversationHandler.END

  async def cancel(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await update.message.reply_text("Операция отменена")
    return ConversationHandler.END

  def _get_available_symbols(self):
    return [s for s in SYMBOLS if self._has_balance(s)]

  def _has_balance(self, symbol: str) -> bool:
    if "buy" in self.current_action.lower():
        # Получаем quote_asset (USDT для пар вида XXXUSDT)
        if symbol.endswith("USDT"):
            quote_asset = "USDT"
        else:
            # Обработка других форматов пар (если есть)
            quote_asset = symbol.split("/")[1]  # Для формата BTC/USDT

        balance = self.info_fetcher.get_asset_balance(quote_asset)
        return balance is not None and balance['free'] > Decimal(0)
    return True


def get_trade_handlers():
  handler = TradeHandlers()

  conv_handler = ConversationHandler(
    entry_points=[
      CommandHandler("buy", handler.start_trade),
      CommandHandler("sell", handler.start_trade)
    ],
    states={
      SELECT_SYMBOL: [CallbackQueryHandler(handler.select_symbol)],
      ENTER_QUANTITY: [MessageHandler(filters.TEXT & ~filters.COMMAND, handler.enter_quantity)],
      CONFIRM_TRADE: [CallbackQueryHandler(handler.confirm_trade)]
    },
    fallbacks=[CommandHandler("cancel", handler.cancel)],
  )

  return [conv_handler]