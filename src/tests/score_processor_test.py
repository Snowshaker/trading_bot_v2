# tests/score_processor_test.py
from src.core.data_logic.score_processor import ScoreProcessor
from src.core.settings.config import (
  RECOMMENDATION_SCORE_MAP,
  TIMEFRAMES,
  test_timeframes
)
from src.core.data_logic.timeframe_weights_calculator import calculate_timeframe_weights


def test_score_processor_demo():
  print("\n=== ДЕМО ОБРАБОТКИ СКОРИНГА ===")

  # 1. Рассчет весов
  weights = calculate_timeframe_weights(TIMEFRAMES)

  # 2. Инициализация процессора
  processor = ScoreProcessor(weights)

  # 3. Тестовые данные анализа
  test_analysis = {
    "1m": {"recommendation": "STRONG_BUY", "score": 0.9},
    "5m": {"recommendation": "BUY", "score": 0.7},
    "15m": {"recommendation": "NEUTRAL", "score": 0.2},
    "30m": {"recommendation": "SELL", "score": -0.3},
    "1h": {"recommendation": "STRONG_SELL", "score": -1.1},
    "2h": {"recommendation": "NEUTRAL", "score": 0.1},
    "4h": {"recommendation": "BUY", "score": 0.6}
  }

  # 4. Обработка данных
  result = processor.process(test_analysis)

  # 5. Вывод результатов
  print("\n[1] Веса таймфреймов:")
  for tf, w in weights.items():
    print(f"  - {tf.rjust(4)}: {w:.2%}")

  print("\n[2] Входные данные анализа:")
  for tf, data in test_analysis.items():
    print(f"  - {tf.rjust(4)}: {data['recommendation'].ljust(12)} (score: {data['score']})")

  print("\n[3] Результаты обработки:")
  print(f"  Общий score: {result['score']}")
  print(f"  Сигнал: {result['signal']}")

  print("\n[4] Детализация вкладов:")
  for tf, detail in result['details'].items():
    print(f"  - {tf.rjust(4)}: {detail['contribution']:7.3f} "
          f"| weight: {detail['weight']:.3f} "
          f"| rec: {detail['recommendation']}")


if __name__ == "__main__":
  test_score_processor_demo()