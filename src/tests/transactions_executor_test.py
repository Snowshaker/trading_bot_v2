# tests/core/api/binance_client/test_transactions_executor.py
import pytest
from unittest.mock import MagicMock, patch, call
from decimal import Decimal
from binance import Client, exceptions
from datetime import datetime
import logging
from src.core.api.binance_client.transactions_executor import (
  TransactionsExecutor,
  OrderExecutionError,
  OrderCancelError,
  InsufficientFundsError,
  InvalidSymbolError,
  InvalidOrderParameters
)
from src.core.settings.config import SAFETY_MARGIN


@pytest.fixture
def mock_client(mocker):
  mock = MagicMock(spec=Client)
  mocker.patch(
    'src.core.api.binance_client.transactions_executor.Client',
    return_value=mock
  )
  return mock


@pytest.fixture
def executor(mock_client):
  ex = TransactionsExecutor()
  ex.logger = MagicMock()
  return ex


def test_get_symbol_filters_cache(executor, mock_client):
  mock_client.get_symbol_info.return_value = {
    'filters': [
      {'filterType': 'LOT_SIZE', 'minQty': '0.1', 'stepSize': '0.01'},
      {'filterType': 'PRICE_FILTER', 'tickSize': '0.1'}
    ],
    'baseAsset': 'BTC',
    'quoteAsset': 'USDT'
  }

  result1 = executor._get_symbol_filters('BTCUSDT')
  result2 = executor._get_symbol_filters('BTCUSDT')

  mock_client.get_symbol_info.assert_called_once()
  assert result1 == result2


def test_format_quantity(executor, mock_client):
  mock_client.get_symbol_info.return_value = {
    'filters': [
      {'filterType': 'LOT_SIZE', 'stepSize': '0.01'}
    ],
    'baseAsset': 'BTC',
    'quoteAsset': 'USDT'
  }

  formatted = executor._format_quantity('BTCUSDT', 1.234567)
  assert formatted == 1.23


def test_validate_order_parameters_market_buy(executor, mock_client):
  mock_client.get_symbol_info.return_value = {
    'filters': [
      {'filterType': 'LOT_SIZE', 'minQty': '0.1', 'stepSize': '0.01'},
      {'filterType': 'NOTIONAL', 'minNotional': '10', 'applyToMarket': True},
      {'filterType': 'PRICE_FILTER', 'tickSize': '0.1'}
    ],
    'baseAsset': 'BTC',
    'quoteAsset': 'USDT'
  }

  executor.get_current_price = MagicMock(return_value=100.0)

  executor._validate_order_parameters(
    symbol='BTCUSDT',
    side=Client.SIDE_BUY,
    quantity=0.5,
    order_type=Client.ORDER_TYPE_MARKET
  )

  with pytest.raises(InvalidOrderParameters):
    executor._validate_order_parameters(
      symbol='BTCUSDT',
      side=Client.SIDE_BUY,
      quantity=0.05,
      order_type=Client.ORDER_TYPE_MARKET
    )


def test_execute_order_success(executor, mock_client):
  mock_client.create_order.return_value = {
    'orderId': 123,
    'status': 'FILLED',
    'executedQty': '1.0',
    'fills': [
      {'qty': '1.0', 'price': '50000', 'commission': '0.001', 'commissionAsset': 'BTC'}
    ]
  }
  executor._get_symbol_filters = MagicMock(return_value={
    'filters': {
      'LOT_SIZE': {'minQty': '0.1', 'stepSize': '0.01'},
      'PRICE_FILTER': {'tickSize': '0.1'}
    },
    'base_asset': 'BTC',
    'quote_asset': 'USDT'
  })
  executor.get_current_price = MagicMock(return_value=50000.0)
  executor.get_available_balance = MagicMock(return_value=100000.0)

  result = executor.execute_order(
    symbol='BTCUSDT',
    side=Client.SIDE_BUY,
    quantity=1.0
  )

  assert result['success'] is True
  assert result['executed_qty'] == 1.0
  mock_client.create_order.assert_called_once()


def test_cancel_order_success(executor, mock_client):
  mock_client.cancel_order.return_value = {'status': 'CANCELED'}
  result = executor.cancel_order('BTCUSDT', '123')
  assert result['status'] == 'CANCELED'


def test_get_available_balance(executor, mock_client):
  mock_client.get_account.return_value = {
    'balances': [
      {'asset': 'BTC', 'free': '1.5'},
      {'asset': 'USDT', 'free': '10000'}
    ]
  }
  balance = executor.get_available_balance('BTC')
  assert balance == 1.5


def test_get_current_price(executor, mock_client):
  mock_client.get_symbol_ticker.return_value = {'price': '50000.0'}
  price = executor.get_current_price('BTCUSDT')
  assert price == 50000.0


def test_order_response_handling(executor, mock_client):
  executor._get_symbol_filters = MagicMock(return_value={
    'filters': {
      'LOT_SIZE': {'stepSize': '0.01'},
      'PRICE_FILTER': {'tickSize': '0.1'}
    },
    'base_asset': 'BTC',
    'quote_asset': 'USDT'
  })
  executor.get_current_price = MagicMock(return_value=50000.0)
  executor.get_available_balance = MagicMock(return_value=100000.0)

  test_cases = [
    ({'executedQty': '1.0', 'fills': []}, 1.0),
    ({
       'fills': [
         {'qty': '0.5', 'price': '50000', 'commission': '0.0005', 'commissionAsset': 'BTC'},
         {'qty': '0.5', 'price': '50000', 'commission': '0.0005', 'commissionAsset': 'BTC'}
       ]
     }, 1.0),
    ({'origQty': '1.0'}, 1.0)
  ]

  for response, expected in test_cases:
    mock_client.create_order.return_value = response
    result = executor.execute_order('BTCUSDT', Client.SIDE_BUY, 1.0)
    assert result['executed_qty'] == expected


def test_invalid_symbol_error(executor, mock_client):
  mock_client.get_symbol_info.return_value = None
  with pytest.raises(InvalidSymbolError):
    executor._get_symbol_filters('INVALID')


def test_market_order_without_price(executor, mock_client):
  executor._validate_order_parameters(
    symbol='BTCUSDT',
    side=Client.SIDE_BUY,
    quantity=1.0,
    order_type=Client.ORDER_TYPE_MARKET
  )