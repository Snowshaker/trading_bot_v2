# src/core/data_logic/decision_processor/decision_maker.py
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
      position_manager: PositionManager
    ):
        self.symbol = symbol
        self.info_fetcher = info_fetcher
        self.position_manager = position_manager

        self.strategy = AllocationStrategy(
            symbol=symbol,
            info_fetcher=info_fetcher,
            position_manager=position_manager
        )

        self.risk_engine = RiskEngine(
            symbol=symbol,
            info_fetcher=info_fetcher,
            position_manager=position_manager
        )

        self.executor = TransactionsExecutor()
        self.logger = logging.getLogger(self.__class__.__name__)

    def process_signal(self, score: Decimal, signal: str) -> bool:
        """Основной процесс обработки торгового сигнала"""
        try:
            if signal not in ("BUY", "SELL"):
                self.logger.warning(f"Invalid signal: {signal} for {self.symbol}")
                return False

            allocation = self.strategy.calculate_allocation(score, signal)
            if not allocation:
                self.logger.info(f"No allocation calculated for {self.symbol} with signal {signal} and score {score}")
                return False

            validated_quantity = self.risk_engine.validate_quantity(
                Decimal(str(allocation["quantity"])), # Конвертируем обратно в Decimal, т.к. allocation может содержать float
                allocation["action"]
            )
            if not validated_quantity: # validated_quantity уже Decimal
                self.logger.warning(f"Risk validation failed for {self.symbol}. Allocation: {allocation}")
                return False

            order_result = self._execute_order(
                action=allocation["action"],
                quantity=validated_quantity # validated_quantity уже Decimal
            )

            if order_result and order_result.get('success', False):
                # Получаем avg_price, если есть, иначе используем 0.0
                avg_execution_price_str = str(order_result.get("avg_price", "0.0"))
                avg_execution_price = Decimal(avg_execution_price_str)

                # Для ордеров на покупку цена должна быть > 0 для создания позиции
                # Для ордеров на продажу цена может быть 0, если мы просто закрываем позицию
                # Но PositionManager.update_position не использует цену, поэтому для SELL это не критично
                if allocation["action"] == "BUY" and avg_execution_price <= Decimal(0):
                    self.logger.error(
                        f"Order for {self.symbol} {allocation['action']} executed, "
                        f"but average price is {avg_execution_price}. Skipping position update."
                    )
                else:
                    self._update_position(
                        action=allocation["action"],
                        quantity=validated_quantity, # validated_quantity уже Decimal
                        price=avg_execution_price    # avg_execution_price теперь Decimal
                    )
                return True
            else:
                self.logger.error(f"Order execution did not return a successful result for {self.symbol}. Result: {order_result}")
                return False

        except Exception as e:
            self.logger.error(f"Decision process failed for {self.symbol}: {str(e)}", exc_info=True)
            return False

    def _execute_order(self, action: str, quantity: Decimal) -> Optional[Dict]:
        """Исполнение ордера на бирже"""
        try:
            return self.executor.execute_order(
                symbol=self.symbol,
                side=action.upper(), # Убедимся, что side в верхнем регистре (BUY/SELL)
                quantity=float(quantity), # TransactionsExecutor ожидает float
                order_type="MARKET"
            )
        except Exception as e:
            self.logger.error(f"Order execution failed for {self.symbol} {action} {quantity}: {str(e)}")
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
                self.logger.info(f"Position CREATED for {self.symbol}: {quantity} @ {price}")
            elif action == "SELL":
                # При продаже мы уменьшаем существующую позицию или закрываем ее.
                # Логика закрытия/уменьшения должна быть в PositionManager.
                # Для простоты, если есть активные позиции, попробуем обновить первую подходящую.
                # В идеале, PositionManager должен сам решать, какую позицию закрывать/уменьшать.
                active_positions = self.position_manager.get_active_positions()
                if not active_positions:
                    self.logger.warning(f"Tried to SELL {quantity} of {self.symbol}, but no active positions found.")
                    return

                # Простая логика: пытаемся закрыть часть первой открытой позиции
                # Более сложная логика может учитывать FIFO/LIFO или конкретные ID позиций
                updated_any = False
                for pos in active_positions:
                    if pos['quantity'] >= quantity:
                        self.position_manager.update_position(
                            pos['id'],
                            {"quantity": pos['quantity'] - quantity} # quantity здесь это то, что продали
                        )
                        self.logger.info(f"Position UPDATED for {self.symbol} (ID: {pos['id']}): sold {quantity}, remaining {pos['quantity'] - quantity}")
                        updated_any = True
                        break # Обновили одну позицию, выходим
                    else:
                        # Если продаваемое количество больше, чем в текущей позиции,
                        # можно закрыть эту позицию и продолжить с остатком для следующих
                        # (требует более сложной логики отслеживания остатка quantity_to_sell)
                        self.logger.warning(
                            f"Sell quantity {quantity} for {self.symbol} is more than "
                            f"quantity in position {pos['id']} ({pos['quantity']}). "
                            f"Partially closing or complex logic needed."
                        )
                        # Пока что просто пропустим, или можно закрыть эту позицию полностью, если quantity_to_sell > pos_qty
                        # self.position_manager.close_position(pos['id'])
                        # quantity -= pos['quantity']
                        # if quantity <= 0: break

                if not updated_any:
                    self.logger.warning(f"Could not fully apply SELL of {quantity} {self.symbol} to existing positions.")

        except Exception as e:
            self.logger.error(f"Position update failed for {self.symbol}: {str(e)}", exc_info=True)