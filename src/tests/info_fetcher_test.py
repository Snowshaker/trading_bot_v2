# tests/info_fetcher_test.py
import pytest
from decimal import Decimal
from src.core.api.binance_client.info_fetcher import BinanceInfoFetcher
from src.core.settings.config import BINANCE_API_KEY, BINANCE_SECRET_KEY, TESTNET


@pytest.fixture
def fetcher():
  return BinanceInfoFetcher()


def test_get_symbol_info_valid_symbol(fetcher):
  # Проверка для известной торговой пары
  symbol = "BTCUSDT"
  result = fetcher.get_symbol_info(symbol)

  assert result is not None
  assert result['base_asset'] == 'BTC'
  assert result['quote_asset'] == 'USDT'
  assert 'LOT_SIZE' in result['filters']

  lot_size = result['filters']['LOT_SIZE']
  assert 'minQty' in lot_size
  assert 'stepSize' in lot_size


def test_get_current_price_valid_symbol(fetcher):
  symbol = "BTCUSDT"
  price = fetcher.get_current_price(symbol)

  assert isinstance(price, Decimal)
  assert price > Decimal('0')

  # Проверка формата цены
  str_price = format(price, 'f')
  assert '.' in str_price
  assert len(str_price.split('.')[1]) >= 4  # Проверка точности


def test_get_asset_balance_smoke_test(fetcher):
  # Тест на структуру ответа (не проверяет реальный баланс)
  asset = "USDT"
  balance = fetcher.get_asset_balance(asset)

  assert isinstance(balance, dict)
  assert 'free' in balance
  assert 'locked' in balance
  assert isinstance(balance['free'], Decimal)
  assert isinstance(balance['locked'], Decimal)


def test_get_lot_size_for_known_symbol(fetcher):
  symbol = "BTCUSDT"
  lot_size = fetcher.get_lot_size(symbol)

  assert lot_size is not None
  assert 'minQty' in lot_size
  assert 'maxQty' in lot_size
  assert 'stepSize' in lot_size

  # Проверка числовых значений
  assert Decimal(lot_size['minQty']) > Decimal('0')
  assert Decimal(lot_size['stepSize']) > Decimal('0')


def test_error_handling_for_invalid_symbol(fetcher):
  invalid_symbol = "INVALID_SYMBOL_123"

  # Проверка информации о символе
  assert fetcher.get_symbol_info(invalid_symbol) is None

  # Проверка цены
  price = fetcher.get_current_price(invalid_symbol)
  assert price == Decimal('0')

  # Проверка параметров лота
  assert fetcher.get_lot_size(invalid_symbol) is None


def test_api_authentication():
  # Проверка корректности аутентификации
  fetcher = BinanceInfoFetcher()
  account = fetcher.client.get_account()

  assert 'balances' in account
  assert isinstance(account['balances'], list)
  assert 'makerCommission' in account