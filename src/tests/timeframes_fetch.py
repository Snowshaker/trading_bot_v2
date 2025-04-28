from tradingview_ta import TA_Handler, Exchange
import time


def get_supported_timeframes(symbol: str = "BTCUSDT", exchange: str = "BINANCE") -> list:
  """Возвращает список поддерживаемых таймфреймов для указанной пары"""
  test_timeframes = [
    "1m", "3m", "5m", "15m", "30m", "40m",
    "1h", "2h", "3h", "4h", "6h",
    "8h", "12h", "1D", "3D", "1W",
    "1M", "3M", "6M", "1Y", "1000Y"
  ]

  supported = []

  for timeframe in test_timeframes:
    try:
      handler = TA_Handler(
        symbol=symbol,
        exchange=exchange,
        screener="crypto",
        interval=timeframe
      )
      # Делаем тестовый запрос
      analysis = handler.get_analysis()

      # Проверяем наличие данных в анализе
      if analysis.summary and analysis.indicators:
        supported.append(timeframe)
        print(f"✅ {timeframe} поддерживается")
      else:
        print(f"⚠️  {timeframe} возвращает пустые данные")

      # Пауза для избежания блокировки
      time.sleep(1)

    except Exception as e:
      print(f"❌ {timeframe} не поддерживается: {str(e)}")
      continue

  return sorted(supported, key=lambda x: parse_timeframe(x))


def parse_timeframe(tf: str) -> int:
  """Вспомогательная функция для сортировки таймфреймов"""
  unit = tf[-1]
  value = int(tf[:-1]) if tf[:-1] else 1
  multipliers = {'m': 1, 'h': 60, 'D': 1440, 'W': 10080, 'M': 43200, 'Y': 525600}
  return value * multipliers[unit]


if __name__ == "__main__":
  print("\n🔍 Проверяем доступные таймфреймы для BTC/USDT...")
  timeframes = get_supported_timeframes()

  print("\n📋 Поддерживаемые таймфреймы:")
  for tf in timeframes:
    print(f" - {tf}")

  print(f"\nВсего найдено: {len(timeframes)} таймфреймов")