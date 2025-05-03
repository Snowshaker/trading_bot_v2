# src/core/api/binance_client/info_fetcher.py
import json
from binance import Client, exceptions
from decimal import Decimal
import logging
from typing import Optional, Dict, Any
from pathlib import Path


class BinanceInfoFetcher:
  def __init__(self, api_key: str, api_secret: str, testnet: bool = True):
    self.client = Client(
      api_key=api_key,
      api_secret=api_secret,
      testnet=testnet
    )
    self.symbols_info = {}
    self.logger = logging.getLogger(self.__class__.__name__)
    self._load_symbols_info()

  def _load_symbols_info(self) -> None:
    """Загрузка и обработка информации о торговых парах"""
    try:
      exchange_info = self.client.get_exchange_info()
      self.symbols_info = {}

      for symbol_info in exchange_info['symbols']:
        processed = self._process_symbol(symbol_info)
        if processed:
          self.symbols_info[symbol_info['symbol']] = processed

      self.logger.info(f"Loaded info for {len(self.symbols_info)} symbols")

    except exceptions.BinanceAPIException as e:
      self.logger.critical(f"API Error: {e.status_code} {e.message}")
      raise
    except Exception as e:
      self.logger.critical(f"Symbols load failed: {str(e)}")
      raise

  def _process_symbol(self, raw_info: Dict) -> Optional[Dict]:
    try:
      filters = {f['filterType']: f for f in raw_info['filters']}

      return {
        'symbol': raw_info['symbol'],
        'base_asset': raw_info['baseAsset'],
        'quote_asset': raw_info['quoteAsset'],
        'filters': {
          'LOT_SIZE': {
            'min_qty': Decimal(filters['LOT_SIZE']['minQty']),
            'step_size': Decimal(filters['LOT_SIZE']['stepSize'])
          },
          'PRICE_FILTER': {
            'tick_size': Decimal(filters['PRICE_FILTER']['tickSize'])
          },
          'MIN_NOTIONAL': {
            'min_notional': self._get_min_notional(filters, raw_info['symbol'])
          }
        }
      }
    except KeyError as e:
      self.logger.error(f"Missing key in symbol data: {e}")
      return None

  def _get_min_notional(self, filters: Dict, symbol: str) -> Decimal:
    """Получение минимальной суммы ордера с фолбэком"""
    try:
      if 'MIN_NOTIONAL' in filters:
        return Decimal(filters['MIN_NOTIONAL']['minNotional'])
      if 'NOTIONAL' in filters:  # Для новых версий API
        return Decimal(filters['NOTIONAL']['minNotional'])

      # Фолбэк значение
      self.logger.info(f"Using default MIN_NOTIONAL=5 for {symbol}")
      return Decimal('5')

    except Exception as e:
      self.logger.warning(f"MinNotional error for {symbol}: {str(e)}")
      return Decimal('5')

  def get_symbol_info(self, symbol: str) -> Optional[Dict]:
    """Получение информации о символе"""
    return self.symbols_info.get(symbol)

  def get_current_price(self, symbol: str) -> Optional[Decimal]:
    """Получение текущей цены"""
    try:
      ticker = self.client.get_symbol_ticker(symbol=symbol)
      return Decimal(ticker['price'])
    except exceptions.BinanceAPIException as e:
      self.logger.error(f"Price error: {e.status_code} {e.message}")
      return None
    except Exception as e:
      self.logger.error(f"Price fetch failed: {str(e)}")
      return None

  def get_asset_balance(self, asset: str) -> Optional[Dict[str, Decimal]]:
    """Получение баланса актива"""
    try:
      account = self.client.get_account()
      for balance in account['balances']:
        if balance['asset'] == asset:
          return {
            'free': Decimal(balance['free']),
            'locked': Decimal(balance['locked'])
          }
      return None
    except exceptions.BinanceAPIException as e:
      self.logger.error(f"Balance error: {e.status_code} {e.message}")
      return None
    except Exception as e:
      self.logger.error(f"Balance check failed: {str(e)}")
      return None

  def get_exchange_info(self) -> Dict[str, Any]:
    """Получение полной информации о бирже (для дебага)"""
    return self.client.get_exchange_info()