# src/core/data_logic/decision_processor/allocation_strategy.py
import logging
from decimal import Decimal, ROUND_DOWN
from typing import Optional, Dict
from src.core.api.binance_client.info_fetcher import BinanceInfoFetcher
from src.core.settings.config import (
    ALLOCATION_MAX_PERCENT,
    ALLOCATION_SCALE_FACTOR,
    MIN_ORDER_SIZE
)

class AllocationStrategy:
    def __init__(self, symbol: str, info_fetcher: BinanceInfoFetcher, position_manager):
        self.symbol = symbol
        self.info_fetcher = info_fetcher
        self.position_manager = position_manager

    def calculate_allocation(self, score: Decimal, signal: str) -> Optional[Dict]:
        try:
            if signal not in ("BUY", "SELL"):
                return None

            symbol_info = self.info_fetcher.get_symbol_info(self.symbol)
            if not symbol_info:
                return None

            if signal == "BUY":
                current_price = Decimal(str(self.info_fetcher.get_current_price(self.symbol)))
                return self._calculate_buy_size(score, symbol_info, current_price)
            return self._calculate_sell_size(score, symbol_info)

        except Exception as e:
            logging.error(f"Allocation error: {str(e)}")
            return None

    def _calculate_buy_size(self, score: Decimal, symbol_info: Dict, current_price: Decimal) -> Optional[Dict]:
      try:
        # Получаем базовый и котируемый активы (например, BTC/USDT)
        quote_asset = symbol_info.get('quote_asset')  # USDT
        if not quote_asset:
          raise ValueError("Quote asset not found in symbol info")

        # Получаем доступный баланс котируемого актива
        balance_data = self.info_fetcher.get_asset_balance(quote_asset)
        free_balance = Decimal(str(balance_data.get('free', 0.0)))

        logging.info(f"Available {quote_asset} balance: {free_balance}")

        # Если баланс нулевой - сделка невозможна
        if free_balance <= 0:
          logging.warning("Insufficient balance")
          return None

        # Рассчитываем сумму риска
        risk_amount = (
          free_balance
          * (ALLOCATION_MAX_PERCENT / Decimal("100"))  # Конвертируем % в долю
          * score  # Учитываем силу сигнала
          * ALLOCATION_SCALE_FACTOR
        )

        # Проверяем минимальный размер ордера
        if risk_amount < MIN_ORDER_SIZE:
          logging.warning(f"Risk amount {risk_amount} < min order {MIN_ORDER_SIZE}")
          return None

        # Рассчитываем количество базового актива
        quantity = risk_amount / current_price

        # Применяем правила округления биржи
        step_size = Decimal(str(symbol_info['filters']['LOT_SIZE']['stepSize']))
        quantity = (quantity // step_size) * step_size  # Округление вниз

        # Проверяем минимальный размер лота
        min_qty = Decimal(str(symbol_info['filters']['LOT_SIZE']['minQty']))
        if quantity < min_qty:
          logging.warning(f"Quantity {quantity} < min lot {min_qty}")
          return None

        return {"action": "BUY", "quantity": quantity}

      except Exception as e:
        logging.error(f"Buy calculation failed: {str(e)}", exc_info=True)
        return None

    def _calculate_sell_size(self, score: Decimal, symbol_info: Dict) -> Optional[Dict]:
        positions = self.position_manager.get_active_positions()
        total_quantity = sum(p['quantity'] for p in positions)

        if total_quantity <= 0:
            return None

        quantity = total_quantity * (abs(score) / 2)
        quantity *= ALLOCATION_SCALE_FACTOR

        step_size = Decimal(str(symbol_info['filters']['LOT_SIZE']['stepSize']))
        quantity = (quantity // step_size) * step_size

        min_qty = Decimal(str(symbol_info['filters']['LOT_SIZE']['minQty']))
        if quantity < min_qty:
            return None

        return {"action": "SELL", "quantity": quantity}