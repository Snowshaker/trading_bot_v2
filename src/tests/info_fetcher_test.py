from src.core.api.binance_client.info_fetcher import BinanceInfoFetcher, BinanceConnectionError
from src.core.settings.config import SYMBOLS
import time


def test_info_fetcher_demo():
  print("\n=== ДЕМО РАБОТЫ INFO FETCHER ===")
  print("Цель: показать получение базовой информации с Binance\n")

  try:
    # Инициализация
    print("[1] Создание клиента...")
    start_time = time.time()
    fetcher = BinanceInfoFetcher()
    init_time = time.time() - start_time
    print(f"✓ Клиент создан за {init_time:.2f} сек")

    # Получение цен
    print("\n[2] Запрос текущих цен...")
    print(f"Запрошены символы: {', '.join(SYMBOLS)}")

    price_start = time.time()
    prices = fetcher.get_current_prices(SYMBOLS)
    elapsed = time.time() - price_start

    print(f"\nРезультаты:")
    print(f"- Время выполнения: {elapsed:.2f} сек")
    print(f"- Получено цен: {len(prices)} из {len(SYMBOLS)}")

    if prices:
      print("\nПример цен:")
      for symbol, price in list(prices.items())[:3]:
        print(f"  {symbol}: {price:.2f}")

    # Получение баланса
    print("\n[3] Запрос баланса...")
    balance_start = time.time()
    usdt_balance = fetcher.get_asset_balance("USDT")
    elapsed = time.time() - balance_start

    print(f"\nБаланс USDT:")
    print(f"- Свободные: {usdt_balance['free']:.2f}")
    print(f"- Заблокированные: {usdt_balance['locked']:.2f}")
    print(f"- Время запроса: {elapsed:.2f} сек")

    # Получение информации о символе
    print("\n[4] Информация о торговой паре:")
    symbol = SYMBOLS[0]
    info = fetcher.get_symbol_info(symbol)

    if info:
      print(f"Детали для {symbol}:")
      print(f"- Базовый актив: {info['base_asset']}")
      print(f"- Котирующий актив: {info['quote_asset']}")
      print(f"- Фильтры: {len(info['filters'])}")

      lot_size = fetcher.get_lot_size(symbol)
      if lot_size:
        print("\nПараметры лота:")
        print(f"- minQty: {lot_size['minQty']}")
        print(f"- maxQty: {lot_size['maxQty']}")
        print(f"- stepSize: {lot_size['stepSize']}")

  except BinanceConnectionError as e:
    print(f"\n❌ Ошибка подключения: {e}")
  except Exception as e:
    print(f"\n❌ Неожиданная ошибка: {str(e)}")


if __name__ == "__main__":
  test_info_fetcher_demo()