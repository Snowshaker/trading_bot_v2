# tests/unit/core/data_logic/decision_processor/test_risk_engine.py
import pytest
from decimal import Decimal
from unittest.mock import Mock
import logging
from src.core.data_logic.decision_processor.risk_engine import RiskEngine
from src.core.api.binance_client.info_fetcher import BinanceInfoFetcher


@pytest.fixture
def mock_info_fetcher():
  return Mock(spec=BinanceInfoFetcher)


@pytest.fixture
def mock_position_manager():
  return Mock()


@pytest.fixture
def risk_engine(mock_info_fetcher, mock_position_manager):
  engine = RiskEngine(
    symbol="BTCUSDT",
    info_fetcher=mock_info_fetcher,
    position_manager=mock_position_manager
  )
  engine.logger.setLevel(logging.DEBUG)
  return engine


def test_initialization(risk_engine):
  assert risk_engine.symbol == "BTCUSDT"
  assert risk_engine._cache["symbol_info"] is None
  assert risk_engine._cache["price"] is None


def test_log_data_structure(risk_engine, caplog):
  caplog.set_level(logging.DEBUG)
  test_data = {"key": "value"}
  risk_engine._log_data_structure(test_data, "Test")
  assert "Test structure" in caplog.text


def test_get_symbol_info_cache(risk_engine, mock_info_fetcher):
  mock_info = {"filters": {}}
  mock_info_fetcher.get_symbol_info.return_value = mock_info

  # First call
  result = risk_engine._get_symbol_info()
  assert result == mock_info
  mock_info_fetcher.get_symbol_info.assert_called_once_with("BTCUSDT")

  # Second call should use cache
  mock_info_fetcher.get_symbol_info.reset_mock()
  result_cached = risk_engine._get_symbol_info()
  assert result_cached == mock_info
  mock_info_fetcher.get_symbol_info.assert_not_called()


def test_get_current_price(risk_engine, mock_info_fetcher):
  mock_info_fetcher.get_current_price.return_value = "50000.50"

  # First call
  result = risk_engine._get_current_price()
  assert result == Decimal("50000.50")

  # Second call should use cache
  mock_info_fetcher.get_current_price.reset_mock()
  result_cached = risk_engine._get_current_price()
  assert result_cached == Decimal("50000.50")
  mock_info_fetcher.get_current_price.assert_not_called()


def test_validate_structure_valid(risk_engine):
  valid_data = {
    'filters': {
      'LOT_SIZE': {'minQty': Decimal('0.001'), 'stepSize': Decimal('0.001')},
      'PRICE_FILTER': {'tickSize': Decimal('0.01')},
      'minNotional': {'minNotional': Decimal('5.0')}
    },
    'base_asset': 'BTC',
    'quote_asset': 'USDT'
  }
  assert risk_engine._validate_structure(valid_data) is True


@pytest.mark.parametrize("quantity,action,expected", [
  # Valid cases
  (Decimal("0.01"), "BUY", Decimal("0.01")),
  (Decimal("100"), "SELL", Decimal("100")),
  # Invalid types
  (100, "BUY", None),
  ("invalid", "SELL", None),
  # Non-positive
  (Decimal("-1"), "BUY", None),
  (Decimal("0"), "SELL", None),
])
def test_validate_quantity_basic_cases(
  risk_engine, mock_info_fetcher, quantity, action, expected, caplog
):
  mock_info_fetcher.get_symbol_info.return_value = {
    'filters': {
      'LOT_SIZE': {'minQty': '0.001', 'stepSize': '0.001'},
      'PRICE_FILTER': {'tickSize': '0.01'},
      'NOTIONAL': {'minNotional': '5.0', 'applyToMarket': True}
    },
    'base_asset': 'BTC',
    'quote_asset': 'USDT'
  }
  mock_info_fetcher.get_current_price.return_value = "50000.0"
  mock_info_fetcher.get_asset_balance.return_value = {'free': '1000'}

  result = risk_engine.validate_quantity(quantity, action)
  assert result == expected


def test_validate_quantity_min_qty_failure(risk_engine, mock_info_fetcher, caplog):
  mock_info_fetcher.get_symbol_info.return_value = {
    'filters': {'LOT_SIZE': {'minQty': '0.01'}},
    'base_asset': 'BTC',
    'quote_asset': 'USDT'
  }
  mock_info_fetcher.get_current_price.return_value = "50000.0"
  result = risk_engine.validate_quantity(Decimal("0.005"), "BUY")
  assert result is None
  assert "Quantity 0.005 < minQty 0.01" in caplog.text


def test_validate_quantity_notional_failure(risk_engine, mock_info_fetcher, caplog):
  mock_info_fetcher.get_symbol_info.return_value = {
    'filters': {
      'LOT_SIZE': {'minQty': '0.001', 'stepSize': '0.001'},
      'NOTIONAL': {'minNotional': '100.0', 'applyToMarket': True}
    },
    'base_asset': 'BTC',
    'quote_asset': 'USDT'
  }
  mock_info_fetcher.get_current_price.return_value = "50.0"
  result = risk_engine.validate_quantity(Decimal("0.001"), "BUY")
  assert result is None
  assert "Notional value 0.05" in caplog.text


def test_validate_quantity_balance_failure(risk_engine, mock_info_fetcher, caplog):
  mock_info_fetcher.get_symbol_info.return_value = {
    'filters': {
      'LOT_SIZE': {'minQty': '0.001'},
      'PRICE_FILTER': {'tickSize': '0.01'},
      'NOTIONAL': {'minNotional': '5.0', 'applyToMarket': True}
    },
    'base_asset': 'BTC',
    'quote_asset': 'USDT'
  }
  mock_info_fetcher.get_current_price.return_value = "50000.0"
  mock_info_fetcher.get_asset_balance.return_value = {'free': '0.0005'}

  result = risk_engine.validate_quantity(Decimal("0.001"), "SELL")
  assert result is None
  assert "Insufficient funds" in caplog.text


def test_validate_quantity_full_success(risk_engine, mock_info_fetcher, caplog):
  caplog.set_level(logging.INFO)
  mock_info_fetcher.get_symbol_info.return_value = {
    'filters': {
      'LOT_SIZE': {'minQty': '0.001', 'stepSize': '0.001'},
      'PRICE_FILTER': {'tickSize': '0.01'},
      'NOTIONAL': {'minNotional': '5.0', 'applyToMarket': True}
    },
    'base_asset': 'BTC',
    'quote_asset': 'USDT'
  }
  mock_info_fetcher.get_current_price.return_value = "50000.0"
  mock_info_fetcher.get_asset_balance.return_value = {'free': '1000'}

  result = risk_engine.validate_quantity(Decimal("0.1"), "BUY")
  assert result == Decimal("0.1")
  assert "Validation passed" in caplog.text


def test_validate_quantity_price_failure(risk_engine, mock_info_fetcher, caplog):
  mock_info_fetcher.get_symbol_info.return_value = {
    'filters': {'LOT_SIZE': {'minQty': '0.001'}},
    'base_asset': 'BTC',
    'quote_asset': 'USDT'
  }
  mock_info_fetcher.get_current_price.return_value = None
  result = risk_engine.validate_quantity(Decimal("0.01"), "BUY")
  assert result is None
  assert "Invalid current price" in caplog.text