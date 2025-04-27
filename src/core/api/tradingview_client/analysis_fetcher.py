from typing import Dict, Optional
from tradingview_ta import TA_Handler, Exchange
import time
from src.core.settings.config import SYMBOLS, TIMEFRAMES, RECOMMENDATION_SCORE_MAP


class TradingViewFetcher:
  def __init__(self, rate_limit_delay: float = 2.0):  # Уменьшил дефолтную задержку
    self.rate_limit_delay = rate_limit_delay

  def _fetch_single(self, symbol: str, timeframe: str, retries: int = 2) -> Optional[dict]:  # Меньше ретраев
    """Упрощенный метод без RSI"""
    for attempt in range(retries):
      try:
        # Упрощенная инициализация
        analysis = TA_Handler(
          symbol=symbol,
          screener="crypto",
          exchange="BINANCE",
          interval=timeframe
        ).get_analysis()

        recommendation = analysis.summary.get("RECOMMENDATION", "NEUTRAL").upper()

        return {
          "timeframe": timeframe,
          "recommendation": recommendation,
          "score": RECOMMENDATION_SCORE_MAP.get(recommendation, 0)
        }

      except Exception as e:
        if attempt == retries - 1:  # Выводим ошибку только на последней попытке
          print(f"Failed to fetch {symbol} {timeframe}: {str(e)}")
        time.sleep(1.5 ** attempt)  # Уменьшил время ожидания

    return None

  def fetch_all_data(self) -> Dict[str, Dict[str, dict]]:
    """Оптимизированный сбор данных"""
    results = {}

    # Пакетная обработка символов
    for idx, symbol in enumerate(SYMBOLS):
      symbol_data = {}

      # Параллельная обработка таймфреймов (если нужно ускорить - можно через threading)
      for timeframe in TIMEFRAMES:
        if data := self._fetch_single(symbol, timeframe):
          symbol_data[timeframe] = data
        time.sleep(self.rate_limit_delay / 2)  # Уменьшил задержку между запросами

      if symbol_data:
        results[symbol] = symbol_data
      else:
        print(f"Skipping {symbol} - no data")

      # Добавляем паузу между символами
      if idx < len(SYMBOLS) - 1:
        time.sleep(self.rate_limit_delay)

    return results