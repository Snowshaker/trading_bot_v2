# src/telegram_bot/services/formatters.py
from decimal import Decimal
from datetime import datetime
from pathlib import Path
from datetime import datetime

from tabulate import tabulate

from src.core.paths import TW_ANALYSIS

class AnalysisPrinter:
    def __init__(self, data_dir: Path = TW_ANALYSIS):
        self.data_dir = data_dir
        print(f"Analysis data path: {self.data_dir.absolute()}")


def format_balance(balance_data: list, total_usd: Decimal) -> str:
  """Форматирование таблицы баланса с сортировкой"""
  headers = ["Валюта", "Количество", "Стоимость (USD)"]
  rows = []

  # Обрабатываем список кортежей (asset, amount, value)
  for asset, amount, value in balance_data:
    # Форматирование количества
    amount_str = f"{amount.normalize():.8f}".rstrip('0').rstrip('.')
    # Форматирование стоимости
    value_str = f"${value.quantize(Decimal('0.01')):,.2f}"

    rows.append([asset, amount_str, value_str])

  table = tabulate(
    rows,
    headers=headers,
    tablefmt="presto",
    stralign="right",
    numalign="decimal"
  )

  return f"<code>{table}\n\nИтого: ${total_usd:,.2f}</code>"


def format_analysis(analysis_data: dict) -> str:
  if not analysis_data:
    return "<b>Нет данных анализа</b>"

  tf_order = ["1m", "5m", "15m", "30m", "1h", "2h", "4h", "1D", "1W", "1M"]

  message = ["<b>📈 Анализ TradingView:</b>\n"]

  for symbol, data in analysis_data.items():
    if not data or "timeframes" not in data:
      continue

    message.append(f"\n<b>{symbol}</b>")
    timeframes = data.get("timeframes", {})

    for tf in tf_order:
      if tf not in timeframes:
        continue

      rec = timeframes[tf].get("recommendation", "NEUTRAL")
      score = timeframes[tf].get("score", 0)

      # Определение цвета
      if score >= 2:
        color = "🔵"
      elif score >= 1:
        color = "🟢"
      elif score <= -2:
        color = "🟣"
      elif score <= -1:
        color = "🔴"
      else:
        color = "⚪"

      message.append(f"{color} {tf}: {rec.split('_')[-1]}")

  return "\n".join(message)


from decimal import Decimal
from tabulate import tabulate

from decimal import Decimal
from tabulate import tabulate


def format_trade_history(trades: list) -> str:
  """Форматирование истории сделок с использованием tabulate"""

  headers = ["  Дата  ", " Пара ", "  Тип  ", "  Кол-во  ", "    Цена    ",
             "  Сумма  "]  # Добавлено пространство вокруг заголовков
  rows = []

  for trade in trades:
    # Форматирование количества
    qty = Decimal(str(trade['qty']))
    qty_str = f"{qty.normalize():.8f}".rstrip('0').rstrip('.')[:8]

    # Форматирование типа
    side = "🟢  BUY" if trade['is_buyer'] else "🔴 SELL"

    # Форматирование цены
    price = Decimal(str(trade['price']))
    price_str = f"${price:12,.4f}".replace(",", " ")

    # Форматирование суммы
    total = Decimal(str(trade['quote_qty']))
    total_str = f"${total:9,.2f}"

    rows.append([
      trade['time'].strftime('%d.%m.%Y %H:%M'),
      trade['symbol'],
      side.center(9),
      qty_str,
      price_str,
      total_str
    ])

  table = tabulate(
    rows,
    headers=headers,
    tablefmt="simple",
    stralign="right",
    numalign="right"
  )

  return f"<code>📜 История сделок:\n\n{table}</code>"