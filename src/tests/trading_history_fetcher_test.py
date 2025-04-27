from src.core.api.binance_client.trading_history_fetcher import (
  BinanceTradingHistoryFetcher,
  BinanceHistoryError
)
from src.core.settings.config import SYMBOLS
from datetime import datetime, timedelta
import time


def test_history_fetcher_demo():
  print("\n=== ДЕМО РАБОТЫ TRADING HISTORY FETCHER ===")
  print("Цель: показать получение истории сделок с Binance\n")

  try:
    # Инициализация
    print("[1] Инициализация клиента...")
    start_time = time.time()
    fetcher = BinanceTradingHistoryFetcher()
    print(f"✓ Клиент создан за {time.time() - start_time:.2f} сек")

    # Тестовый символ
    symbol = SYMBOLS[0]
    print(f"\nИспользуемый символ: {symbol}")

    # Последние 3 сделки
    print("\n[2] Запрос последних 3 сделок...")
    trades = fetcher.get_trade_history(
      symbol=symbol,
      limit=3
    )
    print_trades(trades, "Последние 3 сделки")  # Исправлено здесь

    # Сделки за последний час
    print("\n[3] Сделки за последний час...")
    hour_ago = datetime.now() - timedelta(hours=1)
    trades = fetcher.get_trade_history(
      symbol=symbol,
      start_time=hour_ago,
      limit=10
    )
    print_trades(trades, f"Сделки с {hour_ago:%H:%M}")  # Исправлено здесь

    # Проверка ошибок
    print("\n[4] Тест обработки ошибок...")
    try:
      fetcher.get_trade_history(symbol="INVALID_SYMBOL123")
    except BinanceHistoryError as e:
      print(f"✓ Корректная обработка неверного символа: {str(e)}")

    try:
      fetcher.get_trade_history(symbol=symbol, limit=1500)
    except BinanceHistoryError as e:
      print(f"✓ Корректная обработка превышения лимита: {str(e)}")

  except BinanceHistoryError as e:
    print(f"\n❌ Ошибка: {e}")
  except Exception as e:
    print(f"\n❌ Неожиданная ошибка: {str(e)}")


# Вынесем функцию отдельно (без self)
def print_trades(trades: list, title: str):
  """Вспомогательная функция для вывода сделок"""
  print(f"\n{title}:")
  if not trades:
    print("  Нет сделок в указанном диапазоне")
    return

  print(f"Найдено сделок: {len(trades)}")
  print("\nПример последней сделки:")
  last_trade = trades[-1]
  print(f"ID: {last_trade['id']}")
  print(f"Время: {last_trade['time']:%Y-%m-%d %H:%M:%S}")
  print(f"Тип: {'Покупка' if last_trade['is_buyer'] else 'Продажа'}")
  print(f"Количество: {last_trade['qty']:.6f}")
  print(f"Цена: {last_trade['price']:.2f}")
  print(f"Комиссия: {last_trade['commission']:.6f} {last_trade['commission_asset']}")


def _print_trades(trades: list, title: str):
  """Вспомогательная функция для вывода сделок"""
  print(f"\n{title}:")
  if not trades:
    print("  Нет сделок в указанном диапазоне")
    return

  print(f"Найдено сделок: {len(trades)}")
  print("\nПример последней сделки:")
  last_trade = trades[-1]
  print(f"ID: {last_trade['id']}")
  print(f"Время: {last_trade['time']:%Y-%m-%d %H:%M:%S}")
  print(f"Тип: {'Покупка' if last_trade['is_buyer'] else 'Продажа'}")
  print(f"Количество: {last_trade['qty']:.6f}")
  print(f"Цена: {last_trade['price']:.2f}")
  print(f"Комиссия: {last_trade['commission']:.6f} {last_trade['commission_asset']}")


if __name__ == "__main__":
  test_history_fetcher_demo()