from src.core.api.tradingview_client.analysis_saver import AnalysisSaver
from pathlib import Path
import json
import shutil
from datetime import datetime


def test_saver_demo():
  print("=== ДЕМО СОХРАНЕНИЯ ДАННЫХ ===")
  test_dir = Path("test_saver_data")

  # 1. Подготовка
  print("\n[1] Инициализация компонентов...")
  saver = AnalysisSaver(test_dir)
  print(f"Директория для теста: {test_dir.resolve()}")

  # 2. Тестовые данные
  print("\n[2] Генерация тестовых данных...")
  test_data = {
    "BTCUSDT": {
      "1m": {"score": 1, "recommendation": "BUY"},
      "5m": {"score": -1, "recommendation": "SELL"}
    },
    "ETHUSDT": {
      "15m": {"score": 0, "recommendation": "NEUTRAL"}
    }
  }

  # 3. Сохранение
  print("\n[3] Сохранение данных...")
  saver.batch_save(test_data)

  # 4. Проверка файлов
  print("\n[4] Проверка результатов:")
  for symbol in test_data.keys():
    file_path = test_dir / f"{symbol}.jsonl"
    print(f"\nФайл {file_path.name}:")
    print(f"• Существует: {file_path.exists()}")
    print(f"• Размер: {file_path.stat().st_size} байт" if file_path.exists() else "")

    if file_path.exists():
      with open(file_path, "r") as f:
        content = json.loads(f.read())
        print("• Содержимое:")
        print(f"  Временная метка: {content['timestamp']}")
        print(f"  Символ: {content['symbol']}")
        print(f"  Таймфреймы: {len(content['timeframes'])} шт")

        # Проверка временной метки
        try:
          datetime.fromisoformat(content['timestamp'].replace("Z", ""))
          print("  ✅ Формат времени корректен")
        except ValueError:
          print("  ❌ Ошибка в формате времени")

  # 5. Пример данных
  print("\n[5] Пример полной записи:")
  sample_file = test_dir / "BTCUSDT.jsonl"
  if sample_file.exists():
    with open(sample_file) as f:
      print(json.dumps(json.loads(f.read()), indent=2))
  else:
    print("Пример недоступен - файл не создан")

  # Очистка
  shutil.rmtree(test_dir, ignore_errors=True)
  print("\nДля повторного запуска удалите директорию: rm -rf test_saver_data")


if __name__ == "__main__":
  test_saver_demo()