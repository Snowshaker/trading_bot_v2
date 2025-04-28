# src/core/data_logic/score_processor.py
from typing import Dict, Any
from decimal import Decimal
from src.core.settings.config import (
  RECOMMENDATION_SCORE_MAP,
  BUY_THRESHOLD,
  SELL_THRESHOLD
)


class ScoreProcessor:
  def __init__(self, timeframe_weights: Dict[str, float]):
    """
    Инициализация процессора оценки торговых сигналов

    :param timeframe_weights: Словарь весов временных интервалов
           Пример: {"1m": 0.2, "5m": 0.3, ...}
    """
    self.timeframe_weights = timeframe_weights
    self._validate_weights()

  def _validate_weights(self):
    """Проверка корректности весов таймфреймов"""
    total = sum(self.timeframe_weights.values())
    if not (0.99 < total < 1.01):
      raise ValueError(f"Invalid weights sum: {total:.2f}. Must sum to 1.0")

  def calculate_score(self, analysis_data: Dict[str, Dict[str, Any]]) -> float:
    """
    Расчет общего скоринга на основе анализа

    :param analysis_data: Данные анализа в формате
           {tf: {"recommendation": ..., "score": ...}}
    :return: Итоговый взвешенный score
    """
    total_score = 0.0

    for tf, data in analysis_data.items():
      recommendation = data.get('recommendation', 'NEUTRAL').upper()
      base_score = RECOMMENDATION_SCORE_MAP.get(recommendation, 0.0)
      weight = self.timeframe_weights.get(tf, 0.0)
      total_score += base_score * weight

    return total_score

  def get_signal(self, score: float) -> str:
    """
    Определение торгового сигнала на основе скоринга

    :param score: Рассчитанный общий score
    :return: Строковый сигнал (BUY/SELL/NEUTRAL)
    """
    if score >= BUY_THRESHOLD:
      return "BUY"
    elif score <= SELL_THRESHOLD:
      return "SELL"
    return "NEUTRAL"

  def process(self, analysis_data: Dict[str, Dict[str, Any]]) -> Dict[str, Any]:
    """
    Полный цикл обработки данных анализа

    :return: Словарь с результатами:
        {
            "score": 1.23,
            "signal": "BUY",
            "details": {
                "1m": {
                    "recommendation": "BUY",
                    "weight": 0.2,
                    "contribution": 0.4
                },
                ...
            }
        }
    """
    details = {}
    total_score = 0.0

    for tf, data in analysis_data.items():
      recommendation = data.get('recommendation', 'NEUTRAL').upper()
      base_score = RECOMMENDATION_SCORE_MAP.get(recommendation, 0.0)
      weight = self.timeframe_weights.get(tf, 0.0)
      contribution = base_score * weight

      details[tf] = {
        "recommendation": recommendation,
        "weight": weight,
        "contribution": round(contribution, 4)
      }

      total_score += contribution

    return {
      "score": round(total_score, 4),
      "signal": self.get_signal(total_score),
      "details": details
    }