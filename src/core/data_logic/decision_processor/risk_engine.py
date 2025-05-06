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
            'LOT_SIZE': {'minQty': Decimal, 'stepSize': Decimal},
            'PRICE_FILTER': {'tickSize': Decimal},
            'minNotional': {'minNotional': Decimal}
        },
        'base_asset': str,
        'quote_asset': str
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
    logger = self.logger.getChild("QuantityValidator")

    try:
      # Валидация базовых параметров
      if not isinstance(quantity, Decimal):
        logger.error("Invalid quantity type. Expected Decimal")
        return None

      if quantity <= Decimal(0):
        logger.warning("Non-positive quantity")
        return None

      # Получение информации о символе
      symbol_info = self._get_symbol_info()
      if not symbol_info:
        logger.error("Symbol info not available")
        return None

      # Извлечение фильтров со значениями по умолчанию
      filters = symbol_info.get('filters', {})
      lot_size = filters.get('LOT_SIZE', {'minQty': '0.001', 'stepSize': '0.001'})
      price_filter = filters.get('PRICE_FILTER', {'tickSize': '0.01'})
      notional_filter = filters.get('NOTIONAL', {'minNotional': '5.0', 'applyToMarket': True})

      # Параметры символа
      min_qty = Decimal(lot_size.get('minQty', '0.001'))
      step_size = Decimal(lot_size.get('stepSize', '0.001'))
      tick_size = Decimal(price_filter.get('tickSize', '0.01'))
      min_notional = Decimal(notional_filter.get('minNotional', '5.0'))
      apply_to_market = notional_filter.get('applyToMarket', False)

      logger.debug(
        f"Validation params for {self.symbol}: "
        f"minQty={min_qty}, stepSize={step_size}, "
        f"minNotional={min_notional}, applyToMarket={apply_to_market}"
      )

      # Проверка минимального количества
      if quantity < min_qty:
        logger.warning(f"Quantity {quantity} < minQty {min_qty}")
        return None

      # Квантование количества
      try:
        valid_qty = quantity.quantize(step_size, rounding=ROUND_DOWN)
        logger.debug(f"Quantized quantity: {quantity} → {valid_qty}")
      except Exception as e:
        logger.error(f"Quantization error: {str(e)}")
        return None

      # Получение текущей цены
      current_price = self._get_current_price()
      if not current_price or current_price <= Decimal(0):
        logger.error("Invalid current price")
        return None

      # Проверка минимальной стоимости для BUY
      if action == "BUY" and apply_to_market:
        notional_value = valid_qty * current_price
        if notional_value < min_notional:
          logger.warning(
            f"Notional value {notional_value:.4f} < min {min_notional:.4f}"
          )
          return None

      # Проверка баланса
      asset_type = 'quote_asset' if action == "BUY" else 'base_asset'
      asset = symbol_info[asset_type].upper()

      balance_info = self.info_fetcher.get_asset_balance(asset)
      if not balance_info:
        logger.error(f"Balance check failed for {asset}")
        return None

      available = Decimal(str(balance_info['free']))
      if valid_qty > available:
        logger.warning(
          f"Insufficient funds: {valid_qty} {asset} > {available} available"
        )
        return None

      logger.info(
        f"Validation passed: {valid_qty} {self.symbol} "
        f"(Notional: {valid_qty * current_price:.2f})"
      )
      return valid_qty

    except KeyError as e:
      logger.error(f"Key error: {str(e)}", exc_info=True)
      return None
    except Exception as e:
      logger.error(f"Unexpected error: {str(e)}", exc_info=True)
      return None