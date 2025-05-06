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
        'LOT_SIZE': {'minQty': Decimal, 'stepSize': Decimal},  # camelCase
        'PRICE_FILTER': {'tickSize': Decimal},
        'NOTIONAL': {'minNotional': Decimal}
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

  def _get_min_notional(self, symbol_info: Dict) -> Decimal:
    """Получение минимальной суммы ордера с учетом фильтров"""
    try:
      filters = symbol_info.get('filters', {})
      notional_filter = filters.get('NOTIONAL') or filters.get('MIN_NOTIONAL')

      if not notional_filter:
        self.logger.warning("Using fallback MIN_NOTIONAL=5")
        return Decimal('5')

      min_notional = Decimal(str(notional_filter.get('minNotional', '5')))
      apply_to_market = notional_filter.get('applyToMarket', False)

      self.logger.debug(f"MinNotional config: {min_notional} (applyToMarket: {apply_to_market})")

      return min_notional if apply_to_market else Decimal(0)

    except Exception as e:
      self.logger.error(f"MinNotional error: {str(e)}")
      return Decimal('5')

  def _calculate_buy(self, score: Decimal, symbol_info: Dict) -> Optional[Dict]:
    """Расчет объема для покупки с актуальными параметрами Binance"""
    try:
      # Константы и проверка порога
      BUY_THRESHOLD_DEC = Decimal(str(BUY_THRESHOLD))
      if score < BUY_THRESHOLD_DEC:
        return None

      # Получение параметров с защитой от отсутствия ключей
      filters = symbol_info.get('filters', {})
      lot_size = filters.get('LOT_SIZE', {'minQty': '0.001', 'stepSize': '0.001'})
      notional_filter = filters.get('NOTIONAL', {'minNotional': '5.0', 'applyToMarket': True})

      # Параметры символа
      min_qty = Decimal(lot_size.get('minQty', '0.001'))
      step_size = Decimal(lot_size.get('stepSize', '0.001'))
      min_notional = Decimal(notional_filter.get('minNotional', '5.0'))
      apply_to_market = notional_filter.get('applyToMarket', False)
      quote_asset = symbol_info.get('quote_asset', 'USDT')

      # Получение цены
      price = self.info_fetcher.get_current_price(self.symbol)
      if not price or price <= Decimal(0):
        self.logger.error("Invalid price")
        return None

      # Расчет рискового капитала
      balance = self.info_fetcher.get_asset_balance(quote_asset)
      if not balance or balance['free'] <= Decimal(0):
        return None

      free_balance = balance['free']
      risk_capital = free_balance * (ALLOCATION_MAX_PERCENT / Decimal('100'))
      allocation = risk_capital * score

      # Проверка минимального объема
      if allocation < MIN_ORDER_SIZE:
        return None

      # Расчет количества
      raw_quantity = allocation / price
      quantity = raw_quantity.quantize(step_size, rounding=ROUND_DOWN)

      # Проверка минимальной стоимости
      final_notional = quantity * price
      if apply_to_market and final_notional < min_notional:
        self.logger.debug(f"Adjusting to min notional {min_notional}")
        min_quantity = (min_notional / price).quantize(step_size, rounding=ROUND_UP)
        if min_quantity * price > free_balance:
          return None
        quantity = min_quantity

      # Финальные проверки
      if quantity < min_qty or quantity * price < min_notional:
        return None

      return {
        'action': 'BUY',
        'quantity': float(quantity),
        'calculated_notional': float(quantity * price),
        'min_notional': float(min_notional)
      }

    except Exception as e:
      self.logger.error(f"Buy calculation error: {str(e)}", exc_info=True)
      return None

  def _calculate_sell(self, score: Decimal, symbol_info: Dict) -> Optional[Dict]:
    """Расчет объема для продажи с полной диагностикой"""
    try:
      self.logger.debug(f"[SELL] Starting calculation for {self.symbol}")
      self.logger.debug(f"[SELL] Raw score: {score}")

      # 1. Проверка порога
      SELL_THRESHOLD_DEC = Decimal(str(SELL_THRESHOLD))
      if score > SELL_THRESHOLD_DEC:
        self.logger.debug(f"[SELL] Score {score} > threshold {SELL_THRESHOLD_DEC}")
        return None

      # 2. Получение параметров символа
      filters = symbol_info.get('filters', {})
      lot_size = filters.get('LOT_SIZE', {})
      base_asset = symbol_info.get('base_asset', "").upper()

      if not base_asset:
        self.logger.error("[SELL] Missing base_asset in symbol info")
        return None

      # 3. Параметры фильтров
      min_qty = Decimal(lot_size.get('minQty', '0.001'))
      step_size = Decimal(lot_size.get('stepSize', '0.001'))
      self.logger.debug(f"[SELL] MinQty: {min_qty} | StepSize: {step_size}")

      # 4. Получение баланса
      balance_info = self.info_fetcher.get_asset_balance(base_asset)
      self.logger.debug(f"[SELL] Raw balance response: {balance_info}")

      if not balance_info:
        self.logger.error("[SELL] Failed to fetch balance")
        return None

      available_qty = balance_info.get('free', Decimal(0))
      self.logger.info(f"[SELL] Available {base_asset}: {available_qty}")

      # 5. Проверка доступного количества
      if available_qty <= Decimal(0):
        self.logger.warning(f"[SELL] Zero balance for {base_asset}")
        return None

      # 6. Расчет объема
      raw_quantity = available_qty * abs(score)
      quantity = raw_quantity.quantize(step_size, rounding=ROUND_DOWN)
      self.logger.debug(f"[SELL] Raw: {raw_quantity} | Quantized: {quantity}")

      # 7. Проверка минимального объема
      if quantity < min_qty:
        self.logger.warning(
          f"[SELL] Quantity {quantity} < min {min_qty} | "
          f"Available: {available_qty} | Score: {score}"
        )
        return None

      # 8. Проверка минимальной стоимости
      price = self.info_fetcher.get_current_price(self.symbol)
      if not price:
        self.logger.error("[SELL] Failed to get current price")
        return None

      notional_value = quantity * price
      self.logger.debug(f"[SELL] Notional value: {notional_value}")

      # 9. Формирование результата
      self.logger.info(
        f"[SELL] Calculated: {quantity} {self.symbol} "
        f"(Value: {notional_value:.2f} USDT)"
      )

      return {
        'action': 'SELL',
        'quantity': float(quantity),
        'calculated_notional': float(notional_value),
        'available': float(available_qty),
        'current_price': float(price)
      }

    except Exception as e:
      self.logger.error(f"[SELL] Critical error: {str(e)}", exc_info=True)
      return None