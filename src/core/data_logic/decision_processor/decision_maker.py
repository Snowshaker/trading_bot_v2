import logging
from decimal import Decimal
from typing import Optional, Dict

from src.core.api.binance_client.info_fetcher import BinanceInfoFetcher
from src.core.api.binance_client.transactions_executor import TransactionsExecutor
from src.core.data_logic.decision_processor.allocation_strategy import AllocationStrategy
from src.core.data_logic.decision_processor.position_manager import PositionManager
from src.core.data_logic.decision_processor.risk_engine import RiskEngine


class DecisionMaker:
    def __init__(
      self,
      symbol: str,
      info_fetcher: BinanceInfoFetcher,
      position_manager: PositionManager  # Добавляем новый параметр
    ):
        self.symbol = symbol
        self.info_fetcher = info_fetcher
        self.position_manager = position_manager  # Сохраняем позицию

        self.strategy = AllocationStrategy(
            symbol=symbol,
            info_fetcher=info_fetcher,
            position_manager=position_manager  # Передаем позицию из аргументов
        )

        self.risk_engine = RiskEngine(
            symbol=symbol,
            info_fetcher=info_fetcher,
            position_manager=position_manager  # Передаем position_manager
        )

        self.executor = TransactionsExecutor()
        self.logger = logging.getLogger(__name__)

    def process_signal(self, score: Decimal, signal: str) -> bool:
        """Основной процесс обработки торгового сигнала"""
        try:
            if signal not in ("BUY", "SELL"):
                self.logger.warning(f"Invalid signal: {signal}")
                return False

            allocation = self.strategy.calculate_allocation(score, signal)
            if not allocation:
                self.logger.info("No allocation calculated")
                return False

            validated_quantity = self.risk_engine.validate_quantity(
                allocation["quantity"],
                allocation["action"]
            )
            if not validated_quantity:
                self.logger.warning("Risk validation failed")
                return False

            order_result = self._execute_order(
                action=allocation["action"],
                quantity=validated_quantity
            )

            if order_result:
                self._update_position(
                    action=allocation["action"],
                    quantity=validated_quantity,
                    price=Decimal(str(order_result["price"]))
                )
                return True
            return False

        except Exception as e:
            self.logger.error(f"Decision process failed: {str(e)}", exc_info=True)
            return False

    def _execute_order(self, action: str, quantity: Decimal) -> Optional[Dict]:
        """Исполнение ордера на бирже"""
        try:
            return self.executor.execute_order(
                symbol=self.symbol,
                side=action,
                quantity=float(quantity),
                order_type="MARKET"
            )
        except Exception as e:
            self.logger.error(f"Order execution failed: {str(e)}")
            return None

    def _update_position(self, action: str, quantity: Decimal, price: Decimal):
        """Обновление записей о позициях"""
        try:
            if action == "BUY":
                self.position_manager.create_position(
                    entry_price=price,
                    quantity=quantity,
                    position_type="LONG"
                )
            else:
                for pos in self.position_manager.get_active_positions():
                    if pos['quantity'] >= quantity:
                        self.position_manager.update_position(
                            pos['id'],
                            {"quantity": pos['quantity'] - quantity}
                        )
        except Exception as e:
            self.logger.error(f"Position update failed: {str(e)}")