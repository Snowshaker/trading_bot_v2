from src.core.data_logic.timeframe_weights_calculator import (
  calculate_timeframe_weights,
  parse_timeframe
)
from src.core.settings.config import TIMEFRAMES
from typing import Dict


def test_weights_calculator_demo():
  print("\n=== ДЕМО РАСЧЕТА ВЕСОВ ТАЙМФРЕЙМОВ ===")
  print("Цель: показать принцип расчета весов для разных временных интервалов\n")

  # Тестовые данные
  test_timeframes = ["15m", "30m", "1h", "4h", "D", "3D", "1W"]

  # Шаг 1: Конвертация в минуты
  print("[1] Конвертация таймфреймов в минуты:")
  tf_durations = {tf: parse_timeframe(tf) for tf in test_timeframes}
  for tf, minutes in tf_durations.items():
    print(f"  - {tf.rjust(4)} → {f'{minutes:5d} мин'.ljust(10)} ({minutes // 1440} дней)")

  # Шаг 2: Расчет весов
  print("\n[2] Расчет весовых коэффициентов:")
  weights = calculate_timeframe_weights(test_timeframes)

  # Шаг 3: Валидация и вывод
  total = sum(weights.values())
  print(f"\n[3] Результаты (сумма весов: {total:.2f}):")
  for tf, weight in sorted(weights.items(), key=lambda x: parse_timeframe(x[0])):
    print(f"  - {tf.rjust(4)}: {weight:.2%}".ljust(20) + f"(вклад: {weight * 100:.1f}%)")

  # Шаг 4: Проверка на реальных данных
  print("\n[4] Проверка с конфигурационными таймфреймами:")
  config_weights = calculate_timeframe_weights(TIMEFRAMES)
  print(f"Используемые в конфиге таймфреймы: {', '.join(TIMEFRAMES)}")
  print("Распределение весов:")
  for tf, w in config_weights.items():
    print(f"  - {tf.rjust(4)}: {w:.2%}")


if __name__ == "__main__":
  test_weights_calculator_demo()