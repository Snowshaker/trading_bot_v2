# src/core/data_logic/decision_processor/allocation_strategy.py
import json
from decimal import Decimal, ROUND_DOWN, ROUND_UP
import logging
from typing import Dict, Optional
from src.core.settings.config import (
    BUY_THRESHOLD,
    SELL_THRESHOLD,
    ALLOCATION_MAX_PERCENT,
    MIN_ORDER_SIZE
)


class AllocationStrategy:
  def __init__(self, symbol: str, info_fetcher, position_manager):
    self.symbol = symbol
    self.info_fetcher = info_fetcher
    self.position_manager = position_manager
    self.logger = logging.getLogger(self.__class__.__name__)

  def _validate_symbol_info(self, symbol_info: Dict) -> bool:
    required_structure = {
      'filters': {
        'LOT_SIZE': {'min_qty': Decimal, 'step_size': Decimal},
        'PRICE_FILTER': {'tick_size': Decimal},
        'MIN_NOTIONAL': {'min_notional': Decimal}
      },
      'base_asset': str,
      'quote_asset': str,
      'symbol': str
    }

    def check_structure(data, structure, path=""):
      for key, expected in structure.items():
        current_path = f"{path}.{key}" if path else key
        if key not in data:
          self.logger.error(f"Missing key: {current_path}")
          return False

        if isinstance(expected, dict):
          if not isinstance(data[key], dict):
            self.logger.error(f"Expected dict at {current_path}")
            return False
          if not check_structure(data[key], expected, current_path):
            return False
        elif isinstance(expected, type):
          if not isinstance(data[key], expected):
            self.logger.error(
              f"Type mismatch in {current_path}. "
              f"Expected {expected}, got {type(data[key])}"
            )
            return False
      return True

    return check_structure(symbol_info, required_structure)

  def calculate_allocation(self, score: Decimal, signal: str) -> Optional[Dict]:
    try:
        # Валидация входных параметров
        if signal not in ("BUY", "SELL"):
            self.logger.error(f"Invalid signal type received: {signal}")
            return None

        if not isinstance(score, Decimal):
            self.logger.error(f"Invalid score type: {type(score)}")
            return None

        # Получение информации о символе
        symbol_info = self.info_fetcher.get_symbol_info(self.symbol)
        if not symbol_info:
            self.logger.error(f"Symbol info not found for {self.symbol}")
            return None

        # Валидация структуры данных
        if not self._validate_symbol_info(symbol_info):
            self.logger.error("Invalid symbol structure. Actual data:\n" 
                f"{json.dumps(symbol_info, indent=2, default=str)}")
            return None

        self.logger.debug(f"Processing {signal} signal for {self.symbol} "
                         f"with score: {score:.2f}")

        # Выбор стратегии
        if signal == "BUY":
            result = self._calculate_buy(score, symbol_info)
        else:
            result = self._calculate_sell(score, symbol_info)

        if result:
            self.logger.info(f"Allocation calculated: {result}")
            return result

        self.logger.warning("No allocation could be calculated")
        return None

    except KeyError as e:
        self.logger.error(f"Key error in allocation calculation: {str(e)}")
        return None
    except ValueError as e:
        self.logger.error(f"Value error in allocation calculation: {str(e)}")
        return None
    except Exception as e:
        self.logger.error(f"Unexpected error in allocation calculation: "
                         f"{str(e)}", exc_info=True)
        return None

  def _calculate_buy(self, score: Decimal, symbol_info: Dict) -> Optional[Dict]:
    """Расчет объема для покупки с нормализацией score [-2, 2]"""
    try:
      # Конвертация параметров в Decimal
      BUY_THRESHOLD_DEC = Decimal(str(BUY_THRESHOLD))
      TWO_DEC = Decimal('2')
      ZERO_DEC = Decimal('0')
      ONE_DEC = Decimal('1')
      HUNDRED_DEC = Decimal('100')

      if score < BUY_THRESHOLD_DEC:
        self.logger.debug(f"Score {score} < buy threshold {BUY_THRESHOLD_DEC}")
        return None

      # Получение цены
      price = self.info_fetcher.get_current_price(self.symbol)
      if not price or price <= ZERO_DEC:
        self.logger.error("Invalid price")
        return None

      # Извлечение параметров символа
      filters = symbol_info['filters']
      lot_size = filters['LOT_SIZE']
      step_size = Decimal(str(lot_size['step_size']))
      min_qty = Decimal(str(lot_size['min_qty']))
      min_notional = Decimal(str(filters['MIN_NOTIONAL']['min_notional']))
      quote_asset = symbol_info['quote_asset']

      # Получение баланса
      balance = self.info_fetcher.get_asset_balance(quote_asset)
      if not balance or balance['free'] <= ZERO_DEC:
        self.logger.warning(f"No balance for {quote_asset}")
        return None
      free_balance = balance['free']

      # Нормализация score
      buy_range = TWO_DEC - BUY_THRESHOLD_DEC
      if buy_range <= ZERO_DEC:
        self.logger.error("Invalid buy range calculation")
        return None

      normalized_score = (score - BUY_THRESHOLD_DEC) / buy_range
      normalized_score = max(min(normalized_score, ONE_DEC), ZERO_DEC)

      # Расчет рискового капитала
      risk_capital = free_balance * (ALLOCATION_MAX_PERCENT / HUNDRED_DEC)
      allocation = risk_capital * normalized_score

      if allocation < MIN_ORDER_SIZE:
        self.logger.debug(f"Allocation {allocation} < MIN_ORDER_SIZE {MIN_ORDER_SIZE}")
        return None

      # Расчет количества
      raw_quantity = allocation / price
      quantity = raw_quantity.quantize(step_size, rounding=ROUND_DOWN)

      # Корректировка под MIN_NOTIONAL
      calculated_notional = quantity * price
      if calculated_notional < min_notional:
        self.logger.info("Adjusting to min notional")
        min_quantity = (min_notional / price).quantize(step_size, rounding=ROUND_UP)

        if min_quantity * price > free_balance:
          self.logger.error("Insufficient funds after adjustment")
          return None

        quantity = min_quantity

      if quantity < min_qty:
        self.logger.warning(f"Quantity {quantity} < min {min_qty}")
        return None

      return {
        'action': 'BUY',
        'quantity': float(quantity),
        'score': float(score),
        'normalized_score': float(normalized_score),
        'risk_percent': float(ALLOCATION_MAX_PERCENT)
      }

    except Exception as e:
      self.logger.error(f"Buy calculation failed: {str(e)}", exc_info=True)
      return None

  def _calculate_sell(self, score: Decimal, symbol_info: Dict) -> Optional[Dict]:
    """Расчет объема для продажи с нормализацией score [-2, 2]"""
    try:
      # Конвертация параметров в Decimal
      SELL_THRESHOLD_DEC = Decimal(str(SELL_THRESHOLD))
      TWO_DEC = Decimal('2')
      ZERO_DEC = Decimal('0')
      ONE_DEC = Decimal('1')

      if score > SELL_THRESHOLD_DEC:
        self.logger.debug(f"Score {score} > sell threshold {SELL_THRESHOLD_DEC}")
        return None

      # Извлечение параметров символа
      filters = symbol_info['filters']
      lot_size = filters['LOT_SIZE']
      step_size = Decimal(str(lot_size['step_size']))
      min_qty = Decimal(str(lot_size['min_qty']))
      base_asset = symbol_info['base_asset']

      # Нормализация score
      sell_range = abs(SELL_THRESHOLD_DEC - TWO_DEC)
      if sell_range <= ZERO_DEC:
        self.logger.error("Invalid sell range calculation")
        return None

      normalized_score = (abs(score) - abs(SELL_THRESHOLD_DEC)) / sell_range
      normalized_score = max(min(normalized_score, ONE_DEC), ZERO_DEC)

      # Получение баланса
      balance = self.info_fetcher.get_asset_balance(base_asset)
      if not balance or balance['free'] <= ZERO_DEC:
        self.logger.warning(f"No available balance for {base_asset}")
        return None
      available_qty = balance['free']

      # Расчет количества
      raw_quantity = available_qty * normalized_score
      quantity = raw_quantity.quantize(step_size, rounding=ROUND_DOWN)

      if quantity < min_qty:
        self.logger.debug(f"Quantity {quantity} < min {min_qty}")
        return None

      return {
        'action': 'SELL',
        'quantity': float(quantity),
        'score': float(score),
        'normalized_score': float(normalized_score),
        'available_qty': float(available_qty)
      }

    except Exception as e:
      self.logger.error(f"Sell calculation failed: {str(e)}", exc_info=True)
      return None