# tests/unit/core/data_logic/decision_processor/test_allocation_strategy.py
import pytest
from decimal import Decimal
from unittest.mock import Mock, patch
from src.core.data_logic.decision_processor.allocation_strategy import AllocationStrategy
from src.core.settings.config import BUY_THRESHOLD, SELL_THRESHOLD, ALLOCATION_MAX_PERCENT, MIN_ORDER_SIZE


@pytest.fixture
def allocation_strategy():
  info_fetcher = Mock()
  position_manager = Mock()
  return AllocationStrategy(
    symbol="BTCUSDT",
    info_fetcher=info_fetcher,
    position_manager=position_manager
  )


@pytest.fixture
def valid_symbol_info():
  return {
    'filters': {
      'LOT_SIZE': {
        'minQty': Decimal('0.001'),
        'stepSize': Decimal('0.001')
      },
      'PRICE_FILTER': {
        'tickSize': Decimal('0.01')
      },
      'NOTIONAL': {
        'minNotional': Decimal('10'),
        'applyToMarket': True
      }
    },
    'base_asset': 'BTC',
    'quote_asset': 'USDT',
    'symbol': 'BTCUSDT'
  }


def test_validate_symbol_info_valid(allocation_strategy, valid_symbol_info):
  assert allocation_strategy._validate_symbol_info(valid_symbol_info) is True


def test_validate_symbol_info_missing_key(allocation_strategy, valid_symbol_info):
  del valid_symbol_info['filters']['LOT_SIZE']
  assert allocation_strategy._validate_symbol_info(valid_symbol_info) is False


def test_validate_symbol_info_type_mismatch(allocation_strategy, valid_symbol_info):
  valid_symbol_info['filters']['LOT_SIZE']['minQty'] = '0.001'
  assert allocation_strategy._validate_symbol_info(valid_symbol_info) is True


def test_calculate_allocation_invalid_signal(allocation_strategy):
  result = allocation_strategy.calculate_allocation(Decimal('0.5'), "INVALID")
  assert result is None


def test_calculate_allocation_invalid_score_type(allocation_strategy):
  allocation_strategy.info_fetcher.get_symbol_info.return_value = None
  result = allocation_strategy.calculate_allocation(0.5, "BUY")
  assert result is None


def test_calculate_allocation_missing_symbol_info(allocation_strategy):
  allocation_strategy.info_fetcher.get_symbol_info.return_value = None
  result = allocation_strategy.calculate_allocation(Decimal('0.5'), "BUY")
  assert result is None


def test_calculate_allocation_invalid_structure(allocation_strategy, valid_symbol_info):
  del valid_symbol_info['filters']['LOT_SIZE']
  allocation_strategy.info_fetcher.get_symbol_info.return_value = valid_symbol_info
  score_for_buy = Decimal(str(BUY_THRESHOLD)) + Decimal('0.1')
  result = allocation_strategy.calculate_allocation(score_for_buy, "BUY")
  assert result is None


def test_calculate_buy_below_threshold(allocation_strategy, valid_symbol_info):
  allocation_strategy.info_fetcher.get_symbol_info.return_value = valid_symbol_info
  result = allocation_strategy._calculate_buy(
    Decimal(str(BUY_THRESHOLD)) - Decimal('0.1'),
    valid_symbol_info
  )
  assert result is None


def test_calculate_sell_above_threshold(allocation_strategy, valid_symbol_info):
  allocation_strategy.info_fetcher.get_symbol_info.return_value = valid_symbol_info
  result = allocation_strategy._calculate_sell(
    Decimal(str(SELL_THRESHOLD)) + Decimal('0.1'),
    valid_symbol_info
  )
  assert result is None


def test_calculate_sell_success(allocation_strategy, valid_symbol_info):
  allocation_strategy.info_fetcher.get_symbol_info.return_value = valid_symbol_info
  allocation_strategy.info_fetcher.get_asset_balance.return_value = {'free': Decimal('1.5')}
  allocation_strategy.info_fetcher.get_current_price.return_value = Decimal('50000')

  result = allocation_strategy._calculate_sell(Decimal('-0.8'), valid_symbol_info)

  assert result is not None
  assert result['action'] == 'SELL'
  assert result['quantity'] == pytest.approx(0.954) # Based on SUT logic for score -0.8 and SELL_THRESHOLD -0.45
  assert result['calculated_notional'] == pytest.approx(47700.0) # 0.954 * 50000


def test_calculate_sell_insufficient_balance(allocation_strategy, valid_symbol_info):
  allocation_strategy.info_fetcher.get_symbol_info.return_value = valid_symbol_info
  allocation_strategy.info_fetcher.get_asset_balance.return_value = {'free': Decimal('0')}
  allocation_strategy.info_fetcher.get_current_price.return_value = Decimal('50000')
  result = allocation_strategy._calculate_sell(Decimal('-0.8'), valid_symbol_info)
  assert result is None


@patch.object(AllocationStrategy, '_calculate_buy')
def test_calculate_allocation_buy_flow(mock_buy, allocation_strategy, valid_symbol_info):
  allocation_strategy.info_fetcher.get_symbol_info.return_value = valid_symbol_info
  score = Decimal(str(BUY_THRESHOLD)) + Decimal('0.1')
  allocation_strategy.calculate_allocation(score, "BUY")
  mock_buy.assert_called_once()


@patch.object(AllocationStrategy, '_calculate_sell')
def test_calculate_allocation_sell_flow(mock_sell, allocation_strategy, valid_symbol_info):
  allocation_strategy.info_fetcher.get_symbol_info.return_value = valid_symbol_info
  score = Decimal(str(SELL_THRESHOLD)) - Decimal('0.1')
  allocation_strategy.calculate_allocation(score, "SELL")
  mock_sell.assert_called_once()


def test_calculation_errors_logged(allocation_strategy, valid_symbol_info):
  allocation_strategy.info_fetcher.get_symbol_info.return_value = valid_symbol_info
  with patch.object(allocation_strategy, '_calculate_buy', side_effect=Exception("Test buy error")):
    with patch.object(allocation_strategy.logger, 'error') as mock_logger:
      result = allocation_strategy.calculate_allocation(Decimal(str(BUY_THRESHOLD)) + Decimal('0.1'), "BUY")
      assert result is None
      mock_logger.assert_called()
      assert any("Unexpected error in allocation calculation" in call_args[0][0] for call_args in mock_logger.call_args_list)
      assert any("Test buy error" in call_args[0][0] for call_args in mock_logger.call_args_list)