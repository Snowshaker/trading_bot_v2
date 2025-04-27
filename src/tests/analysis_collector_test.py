from src.core.api.tradingview_client.analysis_collector import AnalysisCollector
from src.core.api.tradingview_client.analysis_saver import AnalysisSaver
from pathlib import Path
import json
from datetime import datetime


def test_collector_demo():
  print("=== ДЕМО РАБОТЫ COLLECTOR ===")
  test_dir = Path("test_collector_data")

  # 1. Инициализация
  print("\n[1] Подготовка тестовой среды...")
  saver = AnalysisSaver(test_dir)
  collector = AnalysisCollector(test_dir)

  # 2. Генерация тестовых данных
  print("\n[2] Создание тестовых записей...")
  test_records = {
    "BTCUSDT": [
      {
        "timestamp": "2023-10-10T12:00:00Z",
        "timeframes": {"1m": {"score": 1, "recommendation": "BUY"}}
      },
      {
        "timestamp": "2023-10-10T12:01:00Z",
        "timeframes": {"1m": {"score": -1, "recommendation": "SELL"}}
      }
    ]
  }

  # Сохранение тестовых данных
  for symbol, records in test_records.items():
    for record in records:
      saver.save(symbol, record["timeframes"])

  # 3. Тестирование основных функций
  print("\n[3] Тестирование методов collector:")

  print("\n• get_latest() для BTCUSDT:")
  latest = collector.get_latest("BTCUSDT")
  if latest:
    print(f"Последняя запись ({latest['timestamp']}):")
    print(f"Рекомендация: {latest['timeframes']['1m']['recommendation']}")
    print(f"Score: {latest['timeframes']['1m']['score']}")
  else:
    print("❌ Данные не найдены")

  print("\n• get_history() для BTCUSDT (limit=2):")
  history = collector.get_history("BTCUSDT", 2)
  print(f"Найдено записей: {len(history)}")
  if history:
    print("Пример временных меток:")
    for idx, record in enumerate(history, 1):
      print(f"{idx}. {record['timestamp']}")

  # 4. Проверка ошибок
  print("\n[4] Тестирование обработки ошибок:")
  print("\n• Запрос несуществующего символа:")
  missing = collector.get_latest("UNKNOWN")
  print(f"Результат: {'пусто' if not missing else 'данные найдены'}")

  # 5. Рекомендации
  print("\n[5] Рекомендации по формату данных:")
  if latest:
    required_fields = {"timestamp", "symbol", "timeframes"}
    actual_fields = set(latest.keys())
    missing = required_fields - actual_fields
    print(f"Отсутствующие поля: {missing if missing else 'нет'}")

    try:
      datetime.fromisoformat(latest["timestamp"].replace("Z", ""))
      print("✅ Формат времени корректен")
    except:
      print("❌ Ошибка в формате времени")


if __name__ == "__main__":
  test_collector_demo()
  print("\nДля очистки выполните: rm -rf test_collector_data/")