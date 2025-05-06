# tests/core/api/binance_client/test_info_fetcher.py
import pytest
from decimal import Decimal
from unittest.mock import MagicMock
from binance import Client, exceptions
import logging
from src.core.api.binance_client.info_fetcher import BinanceInfoFetcher
import pytest_mock

@pytest.fixture
def mock_binance_client(mocker: pytest_mock.MockerFixture):
    mock_client = mocker.MagicMock(spec=Client)
    mocker.patch(
        'src.core.api.binance_client.info_fetcher.Client',
        return_value=mock_client
    )
    return mock_client

@pytest.fixture
def binance_info_fetcher(mock_binance_client):
    return BinanceInfoFetcher(
        api_key='test-key',
        api_secret='test-secret',
        testnet=True
    )

def test_initialization(mock_binance_client):
    mock_binance_client.testnet = True  # Явно задаем атрибут
    fetcher = BinanceInfoFetcher('key', 'secret', testnet=True)
    assert fetcher.client.testnet is True
    mock_binance_client.get_exchange_info.assert_called_once()

def test_load_symbols_info_success(mock_binance_client, binance_info_fetcher, caplog):
    caplog.set_level(logging.INFO)
    mock_binance_client.get_exchange_info.return_value = {
        'symbols': [
            {
                'symbol': 'BTCUSDT',
                'baseAsset': 'BTC',
                'quoteAsset': 'USDT',
                'filters': [
                    {'filterType': 'LOT_SIZE', 'minQty': '0.001', 'stepSize': '0.001'},
                    {'filterType': 'PRICE_FILTER', 'tickSize': '0.01'},
                    {'filterType': 'NOTIONAL', 'minNotional': '10.0', 'applyToMarket': True}
                ]
            }
        ]
    }
    binance_info_fetcher._load_symbols_info()
    assert 'BTCUSDT' in binance_info_fetcher.symbols_info
    assert 'Loaded info for 1 symbols' in caplog.text

def test_process_symbol_success(binance_info_fetcher):
    raw_info = {
        'symbol': 'BTCUSDT',
        'baseAsset': 'BTC',
        'quoteAsset': 'USDT',
        'filters': [
            {'filterType': 'LOT_SIZE', 'minQty': '0.001', 'stepSize': '0.001'},
            {'filterType': 'PRICE_FILTER', 'tickSize': '0.01'},
            {'filterType': 'NOTIONAL', 'minNotional': '10.0', 'applyToMarket': True}
        ]
    }
    processed = binance_info_fetcher._process_symbol(raw_info)
    assert processed['symbol'] == 'BTCUSDT'
    assert processed['filters']['LOT_SIZE']['minQty'] == Decimal('0.001')

def test_process_symbol_missing_filters(binance_info_fetcher):
    raw_info = {
        'symbol': 'BTCUSDT',
        'baseAsset': 'BTC',
        'quoteAsset': 'USDT',
        'filters': [
            {'filterType': 'PRICE_FILTER', 'tickSize': '0.01'}
        ]
    }
    processed = binance_info_fetcher._process_symbol(raw_info)
    assert processed['filters']['LOT_SIZE']['minQty'] == Decimal('0.001')

def test_process_symbol_key_error(binance_info_fetcher, caplog):
    raw_info = {
        'symbol': 'BTCUSDT',
        'filters': []
    }
    processed = binance_info_fetcher._process_symbol(raw_info)
    assert processed is None
    assert 'Critical symbol processing error' in caplog.text

def test_get_symbol_info(binance_info_fetcher):
    binance_info_fetcher.symbols_info = {'BTCUSDT': 'test_info'}
    assert binance_info_fetcher.get_symbol_info('BTCUSDT') == 'test_info'
    assert binance_info_fetcher.get_symbol_info('UNKNOWN') is None

def test_get_current_price_success(mock_binance_client, binance_info_fetcher):
    mock_binance_client.get_symbol_ticker.return_value = {'price': '50000.0'}
    price = binance_info_fetcher.get_current_price('BTCUSDT')
    assert price == Decimal('50000.0')

def test_get_asset_balance_found(mock_binance_client, binance_info_fetcher):
    mock_binance_client.get_account.return_value = {
        'balances': [
            {'asset': 'BTC', 'free': '1.5', 'locked': '0.5'}
        ]
    }
    balance = binance_info_fetcher.get_asset_balance('BTC')
    assert balance['free'] == Decimal('1.5')
    assert balance['locked'] == Decimal('0.5')

def test_get_asset_balance_not_found(mock_binance_client, binance_info_fetcher):
    mock_binance_client.get_account.return_value = {'balances': []}
    assert binance_info_fetcher.get_asset_balance('BTC') is None

def test_get_min_notional_fallback(binance_info_fetcher, caplog):
    caplog.set_level(logging.INFO)
    result = binance_info_fetcher._get_min_notional({}, 'BTCUSDT')
    assert result == Decimal('5')
    assert 'Using default MIN_NOTIONAL=5 for BTCUSDT' in caplog.text

def test_get_exchange_info(mock_binance_client, binance_info_fetcher):
    mock_binance_client.get_exchange_info.return_value = {'timezone': 'UTC'}
    assert binance_info_fetcher.get_exchange_info() == {'timezone': 'UTC'}