# tests/test_decision_maker.py
import pytest
from decimal import Decimal
from unittest.mock import Mock, patch
from src.core.data_logic.decision_processor.decision_maker import DecisionMaker
from src.core.data_logic.decision_processor.position_manager import PositionManager


def test_successful_buy():
  with patch.object(DecisionMaker, '_execute_order') as mock_execute, \
    patch.object(PositionManager, 'create_position') as mock_create:
    # Настройка моков
    mock_execute.return_value = {"price": Decimal('50000')}

    dm = DecisionMaker("BTCUSDT")
    dm.strategy.calculate_allocation = Mock(return_value={
      "action": "BUY",
      "quantity": Decimal('0.5')
    })
    dm.risk_engine.validate_quantity = Mock(return_value=Decimal('0.5'))

    # Вызов тестируемого метода
    result = dm.process_signal(Decimal('1.5'), "BUY")

    # Проверки
    assert result is True
    mock_create.assert_called_once_with(
      entry_price=Decimal('50000'),
      quantity=Decimal('0.5'),
      position_type="LONG"
    )


def test_risk_validation_failure():
  dm = DecisionMaker("BTCUSDT")
  dm.strategy.calculate_allocation = Mock(return_value={
    "action": "SELL",
    "quantity": Decimal('1.0')
  })
  dm.risk_engine.validate_quantity = Mock(return_value=None)

  assert dm.process_signal(Decimal('-2.0'), "SELL") is False


def test_order_execution_failure():
  dm = DecisionMaker("BTCUSDT")
  dm.strategy.calculate_allocation = Mock(return_value={
    "action": "BUY",
    "quantity": Decimal('0.5')
  })
  dm.risk_engine.validate_quantity = Mock(return_value=Decimal('0.5'))
  dm._execute_order = Mock(return_value=None)

  assert dm.process_signal(Decimal('1.8'), "BUY") is False