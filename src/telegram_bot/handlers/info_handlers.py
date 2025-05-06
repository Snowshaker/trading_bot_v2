# src/telegram_bot/handlers/info_handlers.py
import logging

from tabulate import tabulate
from telegram import Update
from telegram.ext import ContextTypes, CommandHandler
from decimal import Decimal
from typing import Optional

from src.core.api.binance_client.info_fetcher import BinanceInfoFetcher
from src.core.api.tradingview_client.analysis_collector import AnalysisCollector
from src.telegram_bot.services.formatters import format_balance, format_analysis, format_trade_history
from src.core.settings.telegram_config import TELEGRAM_ADMINS
from src.core.paths import TW_ANALYSIS
from src.core.settings.config import (
  SYMBOLS,
  MIN_BALANCE_TO_SHOW,
  MAX_HISTORY_LIMIT,
  DEFAULT_HISTORY_LIMIT,
  BINANCE_API_KEY,
  BINANCE_SECRET_KEY,
  TESTNET
)

logger = logging.getLogger(__name__)

info_fetcher = BinanceInfoFetcher(
    api_key=BINANCE_API_KEY,
    api_secret=BINANCE_SECRET_KEY,
    testnet=TESTNET
)
analysis_collector = AnalysisCollector(storage_path=TW_ANALYSIS)


async def check_admin_access(update: Update) -> bool:
  user = update.effective_user
  if not user or user.id not in TELEGRAM_ADMINS:
    await update.message.reply_text("⛔ Доступ запрещен")
    return False
  return True


async def show_balance(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
  if not await check_admin_access(update):
    return

  try:
    # Инициализация клиента с авторизацией
    info_fetcher = BinanceInfoFetcher(
      api_key=BINANCE_API_KEY,
      api_secret=BINANCE_SECRET_KEY,
      testnet=TESTNET
    )

    balance_list = []
    total_usd = Decimal(0)
    processed_assets = set()

    # Сбор всех связанных активов
    for symbol in SYMBOLS:
      symbol_info = info_fetcher.get_symbol_info(symbol)
      if symbol_info:
        processed_assets.add(symbol_info['base_asset'])
        processed_assets.add(symbol_info['quote_asset'])

    # Обработка балансов
    for asset in sorted(processed_assets):
      # Получение баланса
      balance = info_fetcher.get_asset_balance(asset)
      if not balance:
        continue

      total = balance['free'] + balance['locked']
      if total < MIN_BALANCE_TO_SHOW:
        continue

      # Получение цены только для прямых пар
      if asset == "USDT":
        price = Decimal(1)
      else:
        price = info_fetcher.get_current_price(f"{asset}USDT")
        if not price:
          continue

      value = total * price
      total_usd += value
      balance_list.append((asset, total, value))

    # Сортировка по убыванию стоимости
    balance_list.sort(key=lambda x: x[2], reverse=True)

    # Форматирование и отправка
    message = (
      "<b>💰 Ваш портфель</b>\n\n"
      f"{format_balance(balance_list, total_usd)}"
    )
    await update.message.reply_text(message, parse_mode='HTML')

  except Exception as e:
    logger.error(f"Balance error: {str(e)}", exc_info=True)
    await update.message.reply_text("⚠️ Ошибка при получении баланса")


# Обновленная функция форматирования
def format_balance(balance_data: list, total_usd: Decimal) -> str:
  """Форматирование таблицы баланса"""
  headers = ["Валюта", "Количество", "Стоимость (USD)"]
  rows = []

  for asset, amount, value in balance_data:
    rows.append([
      asset,
      f"{amount.normalize():.8f}".rstrip('0').rstrip('.'),
      f"${value.quantize(Decimal('0.01')):,.2f}"
    ])

  table = tabulate(
    rows,
    headers=headers,
    tablefmt="presto",
    stralign="right",
    numalign="decimal"
  )

  return f"<code>{table}\n\nИтого: ${total_usd:,.2f}</code>"


def _get_asset_price(asset: str, info_fetcher: BinanceInfoFetcher) -> Optional[Decimal]:
  """Получение цены актива в USDT"""
  try:
    if asset == "USDT":
      return Decimal(1)

    # Пытаемся получить прямую пару
    price = info_fetcher.get_current_price(f"{asset}USDT")
    if price:
      return Decimal(str(price))

    # Если прямой пары нет, используем цепочку через BTC
    btc_price = info_fetcher.get_current_price("BTCUSDT")
    asset_btc_price = info_fetcher.get_current_price(f"{asset}BTC")
    if btc_price and asset_btc_price:
      return Decimal(str(asset_btc_price)) * Decimal(str(btc_price))

    return None
  except Exception as e:
    logger.warning(f"Price fetch error for {asset}: {str(e)}")
    return None


async def show_analysis(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
  if not await check_admin_access(update):
    return

  try:
    logger.info("Starting analysis processing...")

    analysis_data = analysis_collector.get_all_latest()

    if not analysis_data:
      logger.warning("No analysis data found")
      await update.message.reply_text("📭 Данные анализа отсутствуют")
      return

    message = format_analysis(analysis_data)

    if not message or len(message.strip()) < 10:
      logger.error("Empty analysis message generated!")
      message = "⚠️ Ошибка форматирования анализа"

    await update.message.reply_text(message, parse_mode='HTML')

  except Exception as e:
    logger.critical(f"Critical analysis error: {str(e)}", exc_info=True)
    await update.message.reply_text("🔥 Критическая ошибка при загрузке анализа")


from src.core.api.binance_client.trading_history_fetcher import BinanceTradingHistoryFetcher


async def show_history(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
  if not await check_admin_access(update):
    return

  try:
    args = context.args
    limit = int(args[0]) if args else DEFAULT_HISTORY_LIMIT
    limit = min(max(limit, 1), MAX_HISTORY_LIMIT)

    history_fetcher = BinanceTradingHistoryFetcher()
    trades = history_fetcher.get_all_trades_history(limit=limit)  # Используем новый метод

    if not trades:
      await update.message.reply_text("📭 История торгов пуста")
      return

    message = format_trade_history(trades)
    await update.message.reply_text(message, parse_mode='HTML')

  except ValueError:
    await update.message.reply_text(f"❌ Некорректное число. Используйте от 1 до {MAX_HISTORY_LIMIT}")
  except Exception as e:
    logger.error(f"History error: {str(e)}", exc_info=True)
    await update.message.reply_text("⚠️ Ошибка при получении истории")


def get_info_handlers():
  return [
    CommandHandler("balance", show_balance),
    CommandHandler("analysis", show_analysis),
    CommandHandler("history", show_history)
  ]