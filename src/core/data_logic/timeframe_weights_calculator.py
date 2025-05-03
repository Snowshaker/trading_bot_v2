# src/core/data_logic/timeframe_weights_calculator.py
import re
from typing import Dict


def parse_timeframe(timeframe: str) -> int:
  """
  Конвертирует строку таймфрейма в количество минут.
  Поддерживает форматы: 1m, 5m, 15m, 1h, 4h, D, 2D, W, M и т.д.
  """
  match = re.match(r"^(\d*)([mhDWM])$", timeframe)
  if not match:
    raise ValueError(f"Invalid timeframe format: {timeframe}")

  num_str, unit = match.groups()
  num = int(num_str) if num_str else 1

  conversion = {
    'm': 1,
    'h': 60,
    'D': 1440,  # 24*60
    'W': 10080,  # 7*24*60
    'M': 43200  # 30*24*60 (условно)
  }

  return num * conversion[unit]


def calculate_timeframe_weights(timeframes: list[str]) -> Dict[str, float]:
  """
  Рассчитывает веса для таймфреймов на основе их длительности.
  Возвращает словарь: {таймфрейм: вес}
  """
  durations = {}
  total = 0

  for tf in timeframes:
    duration = parse_timeframe(tf)
    durations[tf] = duration
    total += duration

  if total == 0:
    raise ValueError("Total duration cannot be zero")

  return {tf: (dur / total) for tf, dur in durations.items()}