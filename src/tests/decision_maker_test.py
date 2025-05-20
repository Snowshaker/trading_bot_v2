# tests/unit/core/data_logic/decision_processor/test_decision_maker.py
import pytest
from decimal import Decimal
from unittest.mock import Mock, call
from typing import Optional, Dict
import logging

from src.core.data_logic.decision_processor.decision_maker import DecisionMaker
from src.core.api.binance_client.transactions_executor import TransactionsExecutor
from src.core.data_logic.decision_processor.position_manager import PositionManager


@pytest.fixture
def mock_info_fetcher():
  return Mock()


@pytest.fixture
def mock_position_manager():
  manager = Mock()
  manager.get_active_positions.return_value = [
    {'id': 1, 'quantity': Decimal('100'), 'position_type': 'LONG'}
  ]
  return manager


@pytest.fixture
def decision_maker(mock_info_fetcher, mock_position_manager):
  dm = DecisionMaker(
    symbol="BTCUSDT",
    info_fetcher=mock_info_fetcher,
    position_manager=mock_position_manager
  )
  dm.executor = Mock(spec=TransactionsExecutor)
  return dm


@pytest.fixture
def mock_strategy(decision_maker):
  strategy = Mock()
  decision_maker.strategy = strategy
  return strategy


@pytest.fixture
def mock_risk_engine(decision_maker):
  risk_engine = Mock()
  decision_maker.risk_engine = risk_engine
  return risk_engine


@pytest.fixture
def mock_executor(decision_maker):
  return decision_maker.executor


def test_process_signal_invalid_signal(decision_maker, caplog):
  result = decision_maker.process_signal(Decimal('0.5'), "INVALID")
  assert result is False
  assert "Invalid signal: INVALID for BTCUSDT" in caplog.text


def test_process_signal_no_allocation(decision_maker, mock_strategy, caplog):
  caplog.set_level(logging.INFO)
  mock_strategy.calculate_allocation.return_value = None
  result = decision_maker.process_signal(Decimal('0.5'), "BUY")
  assert result is False
  assert "No allocation calculated for BTCUSDT with signal BUY and score 0.5" in caplog.text


def test_process_signal_risk_validation_failed(
  decision_maker, mock_strategy, mock_risk_engine, caplog
):
  mock_strategy.calculate_allocation.return_value = {
    "action": "BUY",
    "quantity": Decimal('100')
  }
  mock_risk_engine.validate_quantity.return_value = None

  result = decision_maker.process_signal(Decimal('0.5'), "BUY")
  assert result is False
  assert "Risk validation failed for BTCUSDT" in caplog.text


def test_process_signal_successful_flow(
  decision_maker, mock_strategy, mock_risk_engine, mock_executor, mock_position_manager
):
  mock_strategy.calculate_allocation.return_value = {
    "action": "BUY",
    "quantity": Decimal('100')
  }
  mock_risk_engine.validate_quantity.return_value = Decimal('50')
  mock_executor.execute_order.return_value = {
    "success": True,
    "avg_price": "50000.0",
    "price": "50000.0",
    "status": "FILLED"
  }

  result = decision_maker.process_signal(Decimal('0.7'), "BUY")
  assert result is True

  mock_strategy.calculate_allocation.assert_called_once_with(Decimal('0.7'), "BUY")
  mock_risk_engine.validate_quantity.assert_called_once_with(Decimal('100'), "BUY")
  mock_executor.execute_order.assert_called_once_with(
    symbol="BTCUSDT",
    side="BUY",
    quantity=50.0,
    order_type="MARKET"
  )
  mock_position_manager.create_position.assert_called_once_with(
    entry_price=Decimal('50000.0'),
    quantity=Decimal('50'),
    position_type="LONG"
  )


def test_process_signal_order_execution_failed_returns_false(
  decision_maker, mock_strategy, mock_risk_engine, mock_executor, caplog
):
  mock_strategy.calculate_allocation.return_value = {
    "action": "SELL",
    "quantity": Decimal('50')
  }
  mock_risk_engine.validate_quantity.return_value = Decimal('30')
  mock_executor.execute_order.return_value = {"success": False, "avg_price": "0"}

  result = decision_maker.process_signal(Decimal('0.3'), "SELL")
  assert result is False
  assert "Order execution did not return a successful result for BTCUSDT" in caplog.text


def test_process_signal_exception_handling(decision_maker, mock_strategy, caplog):
  mock_strategy.calculate_allocation.side_effect = Exception("Test error")

  result = decision_maker.process_signal(Decimal('0.5'), "BUY")
  assert result is False
  assert "Decision process failed for BTCUSDT: Test error" in caplog.text


def test_execute_order_success(mock_executor, decision_maker):
  mock_executor.execute_order.return_value = {"status": "FILLED", "avg_price": "50000.0", "success": True}

  result = decision_maker._execute_order("BUY", Decimal('100'))
  assert result == {"status": "FILLED", "avg_price": "50000.0", "success": True}
  mock_executor.execute_order.assert_called_once_with(
      symbol="BTCUSDT", side="BUY", quantity=100.0, order_type="MARKET"
  )


def test_execute_order_failure(mock_executor, decision_maker, caplog):
  mock_executor.execute_order.side_effect = Exception("API error")

  result = decision_maker._execute_order("SELL", Decimal('50'))
  assert result is None
  assert "Order execution failed for BTCUSDT SELL 50: API error" in caplog.text


def test_update_position_buy(mock_position_manager, decision_maker):
  decision_maker._update_position("BUY", Decimal('100'), Decimal('50000.0'))

  mock_position_manager.create_position.assert_called_once_with(
    entry_price=Decimal('50000.0'),
    quantity=Decimal('100'),
    position_type="LONG"
  )


def test_update_position_sell(mock_position_manager, decision_maker, caplog):
  caplog.set_level(logging.INFO)
  decision_maker._update_position("SELL", Decimal('30'), Decimal('51000.0'))

  mock_position_manager.get_active_positions.assert_called_once()
  mock_position_manager.update_position.assert_called_once_with(
    1, {'quantity': Decimal('70')}
  )
  assert f"Position UPDATED for BTCUSDT (ID: 1): sold {Decimal('30')}, remaining {Decimal('70')}" in caplog.text


def test_update_position_exception_handling(mock_position_manager, decision_maker, caplog):
  mock_position_manager.create_position.side_effect = Exception("DB error")

  decision_maker._update_position("BUY", Decimal('100'), Decimal('50000.0'))
  assert "Position update failed for BTCUSDT: DB error" in caplog.text


def test_update_position_sell_no_active_positions(mock_position_manager, decision_maker, caplog):
  mock_position_manager.get_active_positions.return_value = []

  decision_maker._update_position("SELL", Decimal('50'), Decimal('50000.0'))
  mock_position_manager.update_position.assert_not_called()
  assert "Tried to SELL 50 of BTCUSDT, but no active positions found." in caplog.text