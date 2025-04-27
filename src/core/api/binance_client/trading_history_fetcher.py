# src/core/api/binance_client/trading_history_fetcher.py
from binance import Client, exceptions
from datetime import datetime, timedelta
from typing import List, Dict, Optional
from src.core.settings.config import BINANCE_API_KEY, BINANCE_SECRET_KEY, TESTNET


class BinanceTradingHistoryFetcher:
  MAX_LIMIT = 1000  # Максимальное значение по Binance API

  def __init__(self):
    self._client = Client(
      api_key=BINANCE_API_KEY,
      api_secret=BINANCE_SECRET_KEY,
      testnet=TESTNET
    )

  def get_trade_history(
    self,
    symbol: str,
    start_time: Optional[datetime] = None,
    end_time: Optional[datetime] = None,
    limit: int = 500
  ) -> List[Dict]:
    """
    Возвращает историю сделок с фильтрацией по времени и количеству

    :param symbol: Торговая пара (например: 'BTCUSDT')
    :param start_time: Начало временного диапазона
    :param end_time: Конец временного диапазона
    :param limit: Максимальное количество сделок (1-1000)
    :return: Список сделок в формате:
        [{
            'id': int,
            'symbol': str,
            'price': float,
            'qty': float,
            'quote_qty': float,
            'time': datetime,
            'is_buyer': bool,
            'commission': float,
            'commission_asset': str
        }, ...]
    """
    try:
      # Валидация параметров
      self._validate_params(symbol, limit)

      # Конвертация времени в миллисекунды
      params = {'symbol': symbol}
      if start_time:
        params['startTime'] = int(start_time.timestamp() * 1000)
      if end_time:
        params['endTime'] = int(end_time.timestamp() * 1000)

      # Ограничение лимита
      params['limit'] = min(limit, self.MAX_LIMIT)

      # Запрос к API
      raw_trades = self._client.get_my_trades(**params)

      return self._process_trades(raw_trades)

    except exceptions.BinanceAPIException as e:
      raise BinanceHistoryError(f"API Error: {e.message}")
    except Exception as e:
      raise BinanceHistoryError(f"Unexpected error: {str(e)}")

  def _validate_params(self, symbol: str, limit: int):
    """Валидация входных параметров"""
    if limit < 1 or limit > self.MAX_LIMIT:
      raise ValueError(f"Limit must be between 1 and {self.MAX_LIMIT}")

    # Проверка существования символа
    if not self._client.get_symbol_info(symbol):
      raise ValueError(f"Invalid symbol: {symbol}")

  def _process_trades(self, raw_trades: List[Dict]) -> List[Dict]:
    """Преобразование сырых данных в удобный формат"""
    processed = []
    for trade in raw_trades:
      processed.append({
        'id': trade['id'],
        'symbol': trade['symbol'],
        'price': float(trade['price']),
        'qty': float(trade['qty']),
        'quote_qty': float(trade['quoteQty']),
        'time': datetime.fromtimestamp(trade['time'] / 1000),
        'is_buyer': trade['isBuyer'],
        'commission': float(trade['commission']),
        'commission_asset': trade['commissionAsset']
      })
    return processed


class BinanceHistoryError(Exception):
  pass