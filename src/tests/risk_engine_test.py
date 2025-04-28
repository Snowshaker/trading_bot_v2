# tests/test_risk_engine.py
import pytest
from decimal import Decimal
from unittest.mock import Mock
from src.core.data_logic.decision_processor.risk_engine import RiskEngine


@pytest.fixture
def mock_fetcher():
  mock = Mock()
  mock.get_symbol_info.return_value = {
    'base_asset': 'BTC',
    'quote_asset': 'USDT',
    'min_lot': Decimal('0.001'),
    'step_size': Decimal('0.0001')
  }
  return mock


def test_buy_validation(mock_fetcher):
  engine = RiskEngine("BTCUSDT")
  engine.info_fetcher = mock_fetcher
  mock_fetcher.get_available_balance.return_value = Decimal('500')
  mock_fetcher.get_current_price.return_value = Decimal('50000')

  # Тест 1: Достаточный баланс
  assert engine.validate_quantity(Decimal('0.01'), "BUY") == Decimal('0.01')

  # Тест 2: Недостаточный баланс → возвращает максимально возможный объем
  assert engine.validate_quantity(Decimal('0.02'), "BUY") == Decimal('0.01')


def test_sell_validation(mock_fetcher):
  engine = RiskEngine("BTCUSDT")
  engine.info_fetcher = mock_fetcher
  mock_fetcher.get_available_balance.return_value = Decimal('0.5')

  # Тест 1: Достаточный баланс
  assert engine.validate_quantity(Decimal('0.5'), "SELL") == Decimal('0.5')

  # Тест 2: Превышение баланса
  assert engine.validate_quantity(Decimal('0.6'), "SELL") == Decimal('0.5')


def test_min_lot_validation(mock_fetcher):
  engine = RiskEngine("BTCUSDT")
  engine.info_fetcher = mock_fetcher

  # Тест минимального лота
  assert engine.validate_quantity(Decimal('0.0005'), "BUY") is None


def test_step_size_rounding(mock_fetcher):
  engine = RiskEngine("BTCUSDT")
  engine.info_fetcher = mock_fetcher
  mock_fetcher.get_symbol_info.return_value['step_size'] = Decimal('0.1')
  mock_fetcher.get_available_balance.return_value = Decimal('10000')
  mock_fetcher.get_current_price.return_value = Decimal('10000')

  # Тест округления 0.15 → 0.1
  assert engine.validate_quantity(Decimal('0.15'), "BUY") == Decimal('0.1')