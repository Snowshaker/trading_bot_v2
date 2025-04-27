from src.core.api.tradingview_client.analysis_fetcher import TradingViewFetcher
from src.core.api.tradingview_client.analysis_collector import AnalysisCollector
from src.core.settings.config import SYMBOLS, TIMEFRAMES
from pathlib import Path
import time


def test_fetcher_demo():
  print("=== ДЕМО РАБОТЫ АНАЛИЗАТОРА ===")
  print("Цель: показать базовый цикл работы (запрос -> сохранение)\n")

  # Инициализация
  print("[1] Инициализация компонентов...")
  fetcher = TradingViewFetcher(rate_limit_delay=1.5)
  collector = AnalysisCollector(Path("test_data"))

  # Сбор данных
  print("\n[2] Запрос данных с TradingView...")
  print(f"Конфигурация:")
  print(f"- Символы: {', '.join(SYMBOLS)}")
  print(f"- Таймфреймы: {', '.join(TIMEFRAMES)}")
  print(f"- Задержка: {fetcher.rate_limit_delay} сек")

  start_time = time.time()
  data = fetcher.fetch_all_data()
  elapsed = time.time() - start_time

  print(f"\nРезультаты сбора:")
  print(f"- Время выполнения: {elapsed:.1f} сек")
  print(f"- Успешно собрано: {len(data)}/{len(SYMBOLS)} символов")

  # Валидация данных
  if not data:
    print("\n❌ Ошибка: данные не получены!")
    return

  print("\n[3] Пример данных для первого символа:")
  first_symbol = next(iter(data.values()))
  for tf, values in first_symbol.items():
    print(f"  {tf}: {values['recommendation']} (score: {values['score']})")


if __name__ == "__main__":
  test_fetcher_demo()