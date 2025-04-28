# src/core/api/tradingview_client/analysis_fetcher.py
import logging
import time
from typing import Dict, Optional
from tradingview_ta import TA_Handler, Exchange
from src.core.settings.config import (
  SYMBOLS,
  TIMEFRAMES,
  RECOMMENDATION_SCORE_MAP,
  TV_FETCH_DELAY
)


class TradingViewFetcher:
  def __init__(self, rate_limit_delay: float = TV_FETCH_DELAY):
    self.rate_limit_delay = rate_limit_delay
    self.logger = logging.getLogger(__name__)

  def _fetch_single(self, symbol: str, timeframe: str) -> Optional[dict]:
    """Получение данных для одного символа и таймфрейма"""
    for attempt in range(3):
      try:
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
        self.logger.error(f"Failed to fetch {symbol} {timeframe}: {str(e)}")
        time.sleep(1.5 ** attempt)
    return None

  def fetch_all_data(self) -> Dict[str, Dict[str, dict]]:
    """Основной метод получения данных"""
    results = {}
    for symbol in SYMBOLS:
      symbol_data = {}
      for timeframe in TIMEFRAMES:
        if data := self._fetch_single(symbol, timeframe):
          symbol_data[timeframe] = data
        time.sleep(self.rate_limit_delay)

      if symbol_data:
        results[symbol] = symbol_data
      else:
        self.logger.warning(f"No data for {symbol}")

      time.sleep(self.rate_limit_delay * 2)
    return results