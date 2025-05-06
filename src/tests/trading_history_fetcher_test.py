# tests/core/api/binance_client/test_trading_history_fetcher.py
import pytest
from unittest.mock import MagicMock, call
from binance import Client, exceptions
from datetime import datetime, timezone
import logging
from src.core.api.binance_client.trading_history_fetcher import (
  BinanceTradingHistoryFetcher,
  BinanceHistoryError
)
from src.core.settings.config import SYMBOLS, MAX_HISTORY_LIMIT


@pytest.fixture
def mock_client(mocker):
  mock = MagicMock(spec=Client)
  mocker.patch(
    'src.core.api.binance_client.trading_history_fetcher.Client',
    return_value=mock
  )
  return mock


@pytest.fixture
def history_fetcher(mock_client):
  fetcher = BinanceTradingHistoryFetcher()
  mock_client.get_symbol_info.return_value = {'symbol': 'MOCKED'}
  return fetcher


def create_mock_trade(symbol: str, timestamp: int):
  return {
    'id': 123,
    'symbol': symbol,
    'price': '50000.0',
    'qty': '0.1',
    'quoteQty': '5000.0',
    'time': timestamp,
    'isBuyer': True,
    'commission': '0.001',
    'commissionAsset': 'BTC'
  }


def test_get_trade_history_success(mock_client, history_fetcher):
  # Arrange
  mock_trade = create_mock_trade('BTCUSDT', 1630000000000)
  mock_client.get_my_trades.return_value = [mock_trade]

  # Act
  start_time = datetime(2023, 1, 1, tzinfo=timezone.utc)
  end_time = datetime(2023, 1, 2, tzinfo=timezone.utc)
  result = history_fetcher.get_trade_history(
    symbol='BTCUSDT',
    start_time=start_time,
    end_time=end_time,
    limit=1000
  )

  # Assert
  assert len(result) == 1
  assert result[0]['price'] == 50000.0
  mock_client.get_my_trades.assert_called_once_with(
    symbol='BTCUSDT',
    limit=1000,
    startTime=int(start_time.timestamp() * 1000),
    endTime=int(end_time.timestamp() * 1000)
  )


def test_get_trade_history_validation_error(history_fetcher):
  # Act & Assert
  with pytest.raises(BinanceHistoryError):
    history_fetcher.get_trade_history('INVALID', limit=0)


def test_get_all_trades_history_success(mock_client, history_fetcher):
  # Arrange
  mock_client.get_my_trades.side_effect = [
    [create_mock_trade('BTCUSDT', 1630000001000)],
    [create_mock_trade('ETHUSDT', 1630000002000)]
  ]

  # Act
  result = history_fetcher.get_all_trades_history(limit=2)

  # Assert
  assert len(result) == 2
  assert result[0]['symbol'] == 'ETHUSDT'
  assert result[1]['symbol'] == 'BTCUSDT'
  assert mock_client.get_my_trades.call_args_list == [
    call(symbol=symbol, limit=2) for symbol in SYMBOLS
  ]


def test_validate_params_valid(history_fetcher):
  history_fetcher._validate_params('BTCUSDT', 500)


def test_validate_params_invalid_symbol(history_fetcher):
  with pytest.raises(ValueError):
    history_fetcher._validate_params('INVALID', 100)


def test_validate_params_invalid_limit(history_fetcher):
  with pytest.raises(ValueError):
    history_fetcher._validate_params('BTCUSDT', 0)


def test_process_trades_success(history_fetcher):
  # Arrange
  raw_trades = [create_mock_trade('BTCUSDT', 1630000000000)]

  # Act
  result = history_fetcher._process_trades(raw_trades)

  # Assert
  assert len(result) == 1
  assert result[0]['time'].year == 2021


def test_process_trades_missing_key(history_fetcher, caplog):
  # Arrange
  invalid_trade = {'id': 1, 'price': '50000'}

  # Act
  with caplog.at_level(logging.WARNING):
    result = history_fetcher._process_trades([invalid_trade])

  # Assert
  assert len(result) == 0
  assert 'Missing key in trade data' in caplog.text


def test_process_trades_unexpected_error(history_fetcher, mocker, caplog):
  # Arrange
  mock_trade = mocker.MagicMock()
  mock_trade.__getitem__.side_effect = Exception('Test error')

  # Act
  with caplog.at_level(logging.ERROR):
    result = history_fetcher._process_trades([mock_trade])

  # Assert
  assert len(result) == 0
  assert 'Error processing trade' in caplog.text


def test_custom_exception_handling(mock_client, history_fetcher):
  # Arrange
  mock_client.get_my_trades.side_effect = Exception('Test error')

  # Act & Assert
  with pytest.raises(BinanceHistoryError):
    history_fetcher.get_trade_history('BTCUSDT')


def test_max_limit_config(history_fetcher):
  # Act & Assert
  with pytest.raises(ValueError):
    history_fetcher.get_all_trades_history(limit=MAX_HISTORY_LIMIT + 100)