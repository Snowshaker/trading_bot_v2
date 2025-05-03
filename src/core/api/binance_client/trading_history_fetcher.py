# src/core/api/binance_client/trading_history_fetcher.py
from binance import Client, exceptions
from datetime import datetime, timedelta
from typing import List, Dict, Optional
from src.core.settings.config import (
  BINANCE_API_KEY,
  BINANCE_SECRET_KEY,
  TESTNET,
  SYMBOLS,
  MAX_HISTORY_LIMIT
)
import logging

logger = logging.getLogger(__name__)


class BinanceTradingHistoryFetcher:
  MAX_LIMIT = 1000  # Максимальное значение по Binance API

  def __init__(self):
    self._client = Client(
      api_key=BINANCE_API_KEY,
      api_secret=BINANCE_SECRET_KEY,
      testnet=TESTNET
    )
    self.logger = logging.getLogger(self.__class__.__name__)

  def get_trade_history(
    self,
    symbol: str,
    start_time: Optional[datetime] = None,
    end_time: Optional[datetime] = None,
    limit: int = 500
  ) -> List[Dict]:
    """
    Возвращает историю сделок для конкретного символа
    """
    try:
      self._validate_params(symbol, limit)

      params = {
        'symbol': symbol,
        'limit': min(limit, self.MAX_LIMIT)
      }

      if start_time:
        params['startTime'] = int(start_time.timestamp() * 1000)
      if end_time:
        params['endTime'] = int(end_time.timestamp() * 1000)

      raw_trades = self._client.get_my_trades(**params)
      return self._process_trades(raw_trades)

    except exceptions.BinanceAPIException as e:
      raise BinanceHistoryError(f"API Error: {e.message}")
    except Exception as e:
      raise BinanceHistoryError(f"Unexpected error: {str(e)}")

  def get_all_trades_history(self, limit: int = 10) -> List[Dict]:
    """Получение истории по всем символам"""
    if not 1 <= limit <= MAX_HISTORY_LIMIT:
      raise ValueError(f"Limit must be between 1 and {MAX_HISTORY_LIMIT}")

    all_trades = []

    for symbol in SYMBOLS:
      try:
        trades = self.get_trade_history(symbol=symbol, limit=limit)
        all_trades.extend(trades)
      except Exception as e:
        self.logger.error(
          f"Error getting history for {symbol}",
          exc_info=True,
          stack_info=False
        )

    # Сортировка по времени (новые сначала)
    all_trades.sort(key=lambda x: x['time'], reverse=True)
    return all_trades[:limit]

  def _validate_params(self, symbol: str, limit: int):
    """Валидация входных параметров"""
    if symbol not in SYMBOLS:
      raise ValueError(f"Symbol {symbol} not in configured SYMBOLS")

    if limit < 1 or limit > self.MAX_LIMIT:
      raise ValueError(f"Limit must be between 1 and {self.MAX_LIMIT}")

    # Дополнительная проверка существования символа на бирже
    if not self._client.get_symbol_info(symbol):
      raise ValueError(f"Invalid symbol: {symbol}")

  def _process_trades(self, raw_trades: List[Dict]) -> List[Dict]:
    """Преобразование сырых данных в удобный формат"""
    processed = []
    for trade in raw_trades:
      try:
        processed_trade = {
          'id': trade['id'],
          'symbol': trade['symbol'],
          'price': float(trade['price']),
          'qty': float(trade['qty']),
          'quote_qty': float(trade['quoteQty']),
          'time': datetime.utcfromtimestamp(trade['time'] / 1000),  # UTC
          'is_buyer': trade['isBuyer'],
          'commission': float(trade['commission']),
          'commission_asset': trade['commissionAsset']
        }
        processed.append(processed_trade)
      except KeyError as e:
        self.logger.warning(f"Missing key in trade data: {e}")
      except Exception as e:
        self.logger.error(f"Error processing trade: {str(e)}")
    return processed


class BinanceHistoryError(Exception):
  """Класс для ошибок работы с историей"""
  pass