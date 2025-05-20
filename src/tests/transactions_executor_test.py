# tests/core/api/binance_client/test_transactions_executor.py
import pytest
from unittest.mock import MagicMock, patch, call
from decimal import Decimal
from binance import Client, exceptions
import logging
import json
from src.core.api.binance_client.transactions_executor import (
  TransactionsExecutor,
  OrderExecutionError,
  OrderCancelError,
  InsufficientFundsError,
  InvalidSymbolError,
  InvalidOrderParameters
)


@pytest.fixture
def mock_client_class(mocker):
  client_class_mock = mocker.patch('src.core.api.binance_client.transactions_executor.Client')
  instance_mock = MagicMock(spec=Client)
  client_class_mock.return_value = instance_mock
  return instance_mock

@pytest.fixture
def executor(mock_client_class):
  ex = TransactionsExecutor()
  ex.logger = MagicMock(spec=logging.Logger)
  return ex

def set_default_filters_and_price(ex_instance, min_qty_str='0.001', min_notional_str='5.0', current_price_val=50000.0, apply_to_market_val=True):
    ex_instance._get_symbol_filters = MagicMock(return_value={
        'filters': {
            'LOT_SIZE': {'minQty': min_qty_str, 'stepSize': '0.001'},
            'PRICE_FILTER': {'tickSize': '0.01'},
            'NOTIONAL': {'minNotional': min_notional_str, 'applyToMarket': apply_to_market_val}
        },
        'base_asset': 'BTC',
        'quote_asset': 'USDT'
    })
    ex_instance.get_current_price = MagicMock(return_value=float(current_price_val))
    ex_instance.get_available_balance = MagicMock(return_value=100000.0)


def test_get_symbol_filters_cache(executor, mock_client_class):
  mock_client_instance = mock_client_class
  mock_client_instance.get_symbol_info.return_value = {
    'filters': [
      {'filterType': 'LOT_SIZE', 'minQty': '0.1', 'stepSize': '0.01'},
      {'filterType': 'PRICE_FILTER', 'tickSize': '0.1'}
    ],
    'baseAsset': 'BTC',
    'quoteAsset': 'USDT',
    'symbol': 'BTCUSDT'
  }

  result1 = executor._get_symbol_filters('BTCUSDT')
  result2 = executor._get_symbol_filters('BTCUSDT')

  mock_client_instance.get_symbol_info.assert_called_once_with('BTCUSDT')
  assert result1 is not None
  assert result2 is not None
  assert result1 == result2
  assert 'LOT_SIZE' in result1['filters']


def test_format_quantity(executor, mock_client_class):
  executor._get_symbol_filters = MagicMock(return_value={
    'filters': {'LOT_SIZE': {'stepSize': '0.01'}},
    'base_asset': 'BTC', 'quote_asset': 'USDT'
  })
  formatted = executor._format_quantity('BTCUSDT', 1.234567)
  assert formatted == 1.23


def test_execute_order_success(executor, mock_client_class):
  set_default_filters_and_price(executor)
  mock_client_instance = mock_client_class
  mock_client_instance.create_order.return_value = {
    'orderId': 123,
    'status': 'FILLED',
    'executedQty': '1.0',
    'fills': [
      {'qty': '1.0', 'price': '50000', 'commission': '0.001', 'commissionAsset': 'BTC'}
    ]
  }

  result = executor.execute_order(
    symbol='BTCUSDT',
    side=Client.SIDE_BUY,
    quantity=1.0
  )

  assert result['success'] is True
  assert result['executed_qty'] == 1.0
  assert result['avg_price'] == 50000.0
  mock_client_instance.create_order.assert_called_once()


def test_cancel_order_success(executor, mock_client_class):
  mock_client_instance = mock_client_class
  mock_client_instance.cancel_order.return_value = {'status': 'CANCELED'}
  result = executor.cancel_order('BTCUSDT', '123')
  assert result['status'] == 'CANCELED'


def test_get_available_balance(executor, mock_client_class):
  mock_client_instance = mock_client_class
  mock_client_instance.get_account.return_value = {
    'balances': [
      {'asset': 'BTC', 'free': '1.5'},
      {'asset': 'USDT', 'free': '10000'}
    ]
  }
  balance_btc = executor.get_available_balance('BTC')
  assert balance_btc == 1.5
  balance_usdt = executor.get_available_balance('USDT')
  assert balance_usdt == 10000.0


def test_get_current_price(executor, mock_client_class):
  mock_client_instance = mock_client_class
  mock_client_instance.get_symbol_ticker.return_value = {'price': '50000.0'}
  price = executor.get_current_price('BTCUSDT')
  assert price == 50000.0


def test_invalid_symbol_error(executor, mock_client_class):
  mock_client_instance = mock_client_class
  mock_client_instance.get_symbol_info.return_value = None
  with pytest.raises(InvalidSymbolError, match="Invalid symbol: INVALID"):
    executor._get_symbol_filters('INVALID')


def test_market_order_without_price(executor, mock_client_class):
  set_default_filters_and_price(executor)
  try:
    executor._validate_order_parameters(
      symbol='BTCUSDT',
      side=Client.SIDE_BUY,
      quantity=1.0,
      order_type=Client.ORDER_TYPE_MARKET,
      price=None
    )
  except InvalidOrderParameters as e:
    pytest.fail(f"_validate_order_parameters raised unexpected error for MARKET order: {e}")