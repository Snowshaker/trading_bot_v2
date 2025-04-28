# src/core/data_logic/decision_processor/risk_engine.py
from decimal import Decimal
from typing import Optional
from src.core.data_logic.decision_processor.position_manager import PositionManager
from src.core.api.binance_client.info_fetcher import BinanceInfoFetcher


class RiskEngine:
  def __init__(
    self,
    symbol: str,
    info_fetcher: BinanceInfoFetcher,
    position_manager: PositionManager  # Добавляем параметр
  ):
    self.symbol = symbol
    self.info_fetcher = info_fetcher
    self.position_manager = position_manager  # Используем переданный объект

  def update_risk_parameters(self):
    """Обновление параметров риска (заглушка)"""
    # Реальная реализация будет добавлена позже
    pass

  def validate_quantity(self, quantity: Decimal, action: str) -> Optional[Decimal]:
    """Проверка объема с учетом всех ограничений"""
    symbol_info = self.info_fetcher.get_symbol_info(self.symbol)

    # 1. Проверка минимального размера лота
    min_lot = Decimal(str(symbol_info['min_lot']))
    if quantity < min_lot:
      return None

    # 2. Проверка шага лота
    step_size = Decimal(str(symbol_info['step_size']))
    valid_quantity = (quantity // step_size) * step_size
    if valid_quantity <= 0:
      return None

    # 3. Проверка баланса
    if action == "BUY":
      quote_balance = self.info_fetcher.get_available_balance(
        symbol_info['quote_asset']
      )
      current_price = self.info_fetcher.get_current_price(self.symbol)
      max_affordable = quote_balance / current_price
      valid_quantity = min(valid_quantity, max_affordable)
    else:
      base_balance = self.info_fetcher.get_available_balance(
        symbol_info['base_asset']
      )
      valid_quantity = min(valid_quantity, base_balance)

    return valid_quantity.quantize(step_size)