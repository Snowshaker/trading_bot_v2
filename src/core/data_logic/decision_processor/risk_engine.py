# src/core/data_logic/decision_processor/risk_engine.py
from decimal import Decimal, ROUND_DOWN
import logging
import json
from typing import Optional, Dict
from src.core.api.binance_client.info_fetcher import BinanceInfoFetcher


class RiskEngine:
  def __init__(
    self,
    symbol: str,
    info_fetcher: BinanceInfoFetcher,
    position_manager
  ):
    self.symbol = symbol
    self.info_fetcher = info_fetcher
    self.position_manager = position_manager
    self.logger = logging.getLogger(self.__class__.__name__)
    self._cache = {
      "symbol_info": None,
      "price": None
    }

  def _log_data_structure(self, data: Dict, name: str = "Data"):
    """Логирование структуры данных для отладки"""
    try:
      self.logger.debug(f"{name} structure:\n{json.dumps(data, indent=2, default=str)}")
    except Exception as e:
      self.logger.error(f"Failed to log {name} structure: {str(e)}")

  def _get_symbol_info(self) -> Optional[Dict]:
    """Получение и кэширование информации о символе"""
    if not self._cache["symbol_info"]:
      self._cache["symbol_info"] = self.info_fetcher.get_symbol_info(self.symbol)
      if self._cache["symbol_info"]:
        self._log_data_structure(self._cache["symbol_info"], "Symbol Info")
    return self._cache["symbol_info"]

  def _get_current_price(self) -> Optional[Decimal]:
    """Получение и кэширование текущей цены"""
    if not self._cache["price"]:
      price = self.info_fetcher.get_current_price(self.symbol)
      if price:
        self._cache["price"] = Decimal(str(price)).normalize()
      else:
        self.logger.warning("Failed to get current price")
    return self._cache["price"]

  def _validate_structure(self, data: Dict) -> bool:
    """Валидация структуры данных символа"""
    required_structure = {
      'filters': {
        'LOT_SIZE': ['min_qty', 'step_size'],
        'PRICE_FILTER': ['tick_size'],
        'MIN_NOTIONAL': ['min_notional']
      },
      'base_asset': None,
      'quote_asset': None
    }

    def check_nested(data, structure, path=""):
      for key, expected in structure.items():
        full_path = f"{path}{key}"
        if key not in data:
          self.logger.error(f"Missing key: {full_path}")
          return False

        if isinstance(expected, dict):
          if not isinstance(data[key], dict):
            self.logger.error(f"Expected dict at {full_path}, got {type(data[key])}")
            return False
          if not check_nested(data[key], expected, f"{full_path}."):
            return False
        elif isinstance(expected, list):
          for item in expected:
            if item not in data[key]:
              self.logger.error(f"Missing item {item} in {full_path}")
              return False
      return True

    return check_nested(data, required_structure)

  def validate_quantity(self, quantity: Decimal, action: str) -> Optional[Decimal]:
    """Основной метод валидации количества"""
    try:
      # Валидация входных параметров
      if not isinstance(quantity, Decimal):
        self.logger.error("Invalid quantity type, expected Decimal")
        return None

      if quantity <= Decimal(0):
        self.logger.warning("Non-positive quantity")
        return None

      # Получение информации о символе
      symbol_info = self._get_symbol_info()
      if not symbol_info:
        self.logger.error("Symbol info unavailable")
        return None

      # Проверка структуры данных
      if not self._validate_structure(symbol_info):
        self.logger.error("Invalid symbol info structure")
        self._log_data_structure(symbol_info, "Invalid Symbol Info")
        return None

      # Извлечение параметров
      filters = symbol_info['filters']
      lot_size = filters['LOT_SIZE']
      price_filter = filters['PRICE_FILTER']
      min_notional = filters['MIN_NOTIONAL']['min_notional']

      # Преобразование параметров
      min_qty = Decimal(str(lot_size['min_qty']))
      step_size = Decimal(str(lot_size['step_size']))
      tick_size = Decimal(str(price_filter['tick_size']))
      min_notional_val = Decimal(str(min_notional))

      # Проверка минимального количества
      if quantity < min_qty:
        self.logger.warning(f"Quantity below minimum: {quantity} < {min_qty}")
        return None

      # Приведение к шагу размера
      try:
        valid_qty = quantity.quantize(step_size, rounding=ROUND_DOWN)
      except Exception as e:
        self.logger.error(f"Quantization error: {str(e)}")
        return None

      # Проверка минимальной стоимости ордера
      current_price = self._get_current_price()
      if not current_price or current_price <= Decimal(0):
        self.logger.error("Invalid price for notional calculation")
        return None

      notional_value = valid_qty * current_price
      if notional_value < min_notional_val:
        self.logger.warning(
          f"Notional value too low: {notional_value:.4f} < {min_notional_val:.4f}"
        )
        return None

      # Проверка баланса
      asset_type = 'quote_asset' if action == "BUY" else 'base_asset'
      asset = symbol_info[asset_type]
      balance_info = self.info_fetcher.get_asset_balance(asset)

      if not balance_info:
        self.logger.error(f"Balance check failed for {asset}")
        return None

      available = Decimal(str(balance_info['free']))
      if valid_qty > available:
        self.logger.warning(
          f"Insufficient funds: {valid_qty} > {available} {asset}"
        )
        return None

      self.logger.info(f"Validated quantity: {valid_qty} for {action}")
      return valid_qty

    except Exception as e:
      self.logger.error(f"Validation error: {str(e)}", exc_info=True)
      return None