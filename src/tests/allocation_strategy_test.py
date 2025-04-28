# tests/test_allocation_strategy.py
import pytest
from decimal import Decimal
from unittest.mock import Mock
from src.core.data_logic.decision_processor.allocation_strategy import AllocationStrategy


@pytest.fixture
def mock_fetcher():
  mock = Mock()
  mock.get_symbol_info.return_value = {
    'base_asset': 'BTC',
    'quote_asset': 'USDT',
    'min_lot': Decimal('0.001'),
    'step_size': Decimal('0.0001')
  }
  mock.get_current_price.return_value = Decimal('50000')
  return mock


def test_buy_allocation(mock_fetcher):
  # Настройка моков
  mock_fetcher.get_available_balance.return_value = Decimal('10000')

  strategy = AllocationStrategy("BTCUSDT")
  strategy.info_fetcher = mock_fetcher

  # Тест 1: Максимальный score
  result = strategy.calculate_allocation(Decimal('2.0'), "BUY")
  assert result == {
    'action': 'BUY',
    'quantity': Decimal('0.004').quantize(Decimal('0.0001'))
  }

  # Тест 2: Score ниже минимального объема
  result = strategy.calculate_allocation(Decimal('0.4'), "BUY")
  assert result is None


def test_sell_allocation(mock_fetcher):
  strategy = AllocationStrategy("BTCUSDT")
  strategy.info_fetcher = mock_fetcher
  strategy.position_manager.get_active_positions = Mock(return_value=[
    {'quantity': Decimal('1.5')},
    {'quantity': Decimal('0.5')}
  ])

  # Тест 1: Продажа 100% при максимальном score
  result = strategy.calculate_allocation(Decimal('-2.0'), "SELL")
  assert result['quantity'] == Decimal('2.0')

  # Тест 2: Частичная продажа
  result = strategy.calculate_allocation(Decimal('-1.0'), "SELL")
  assert result['quantity'] == Decimal('1.0')


def test_lot_size_rounding(mock_fetcher):
  strategy = AllocationStrategy("BTCUSDT")
  strategy.info_fetcher = mock_fetcher
  mock_fetcher.get_available_balance.return_value = Decimal('1000000')  # 1M USDT

  # Настройка шага и цены
  mock_fetcher.get_symbol_info.return_value['step_size'] = Decimal('0.1')
  mock_fetcher.get_current_price.return_value = Decimal('50000')

  # Максимальный score для гарантии прохождения проверок
  result = strategy.calculate_allocation(Decimal('2.0'), "BUY")

  # Ожидаемый результат:
  # risk_amount = 1,000,000 * 2% = 20,000 USDT
  # quantity = 20,000 / 50,000 = 0.4 BTC
  assert result['quantity'] == Decimal('0.4')