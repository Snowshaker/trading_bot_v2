# src/core/api/binance_client/transactions_executor.py
from binance import Client, exceptions
from decimal import Decimal, ROUND_DOWN
from typing import Optional, Dict
from src.core.settings.config import (
  BINANCE_API_KEY,
  BINANCE_SECRET_KEY,
  TESTNET,
  SAFETY_MARGIN
)


class TransactionsExecutor:
  def __init__(self):
    self.client = Client(
      api_key=BINANCE_API_KEY,
      api_secret=BINANCE_SECRET_KEY,
      testnet=TESTNET
    )
    self.symbols_info = {}

  def _get_symbol_filters(self, symbol: str) -> Dict:
    """Получает и кеширует информацию о символе"""
    if symbol not in self.symbols_info:
      info = self.client.get_symbol_info(symbol)
      if not info:
        raise InvalidSymbolError(f"Invalid symbol: {symbol}")
      self.symbols_info[symbol] = {
        'filters': {f['filterType']: f for f in info['filters']},
        'base_asset': info['baseAsset'],
        'quote_asset': info['quoteAsset']
      }
    return self.symbols_info[symbol]

  def _format_quantity(self, symbol: str, quantity: float) -> float:
    """Форматирует количество согласно правилам символа"""
    lot_size = self._get_symbol_filters(symbol)['filters']['LOT_SIZE']
    step = Decimal(lot_size['stepSize']).normalize()
    return float(Decimal(str(quantity)).quantize(step, ROUND_DOWN))

  def _format_price(self, symbol: str, price: float) -> float:
    """Форматирует цену согласно правилам символа"""
    price_filter = self._get_symbol_filters(symbol)['filters']['PRICE_FILTER']
    tick_size = Decimal(price_filter['tickSize']).normalize()
    return float(Decimal(str(price)).quantize(tick_size, ROUND_DOWN))

  def _validate_order_parameters(
    self,
    symbol: str,
    side: str,
    quantity: float,
    order_type: str,
    price: Optional[float] = None
  ):
    """Проверяет параметры ордера перед отправкой"""
    filters = self._get_symbol_filters(symbol)['filters']

    # Проверка минимального количества
    min_qty = float(filters['LOT_SIZE']['minQty'])
    if quantity < min_qty:
      raise InvalidOrderParameters(
        f"Quantity too small. Min: {min_qty}"
      )

    # Проверка минимальной стоимости
    if order_type == Client.ORDER_TYPE_MARKET and side == Client.SIDE_BUY:
      min_notional = float(filters['MIN_NOTIONAL']['minNotional'])
      if quantity < min_notional:
        raise InvalidOrderParameters(
          f"Buy value too small. Min: {min_notional}"
        )

    # Проверка цены для лимитных ордеров
    if order_type == Client.ORDER_TYPE_LIMIT and not price:
      raise InvalidOrderParameters(
        "Price required for limit orders"
      )

  def execute_order(
    self,
    symbol: str,
    side: str,
    quantity: float,
    order_type: str = Client.ORDER_TYPE_MARKET,
    price: Optional[float] = None,
    time_in_force: str = Client.TIME_IN_FORCE_GTC
  ) -> Dict:
    """
    Исполняет ордер с заданными параметрами

    :param symbol: Торговая пара (BTCUSDT)
    :param side: Покупка/продажа (SIDE_BUY/SIDE_SELL)
    :param quantity: Количество базового актива
    :param order_type: Тип ордера (MARKET, LIMIT и т.д.)
    :param price: Цена (для лимитных ордеров)
    :param time_in_force: Срок действия (GTC, IOC и т.д.)
    :return: Результат исполнения ордера
    """
    try:
      # Форматирование параметров
      quantity = self._format_quantity(symbol, quantity)
      if price:
        price = self._format_price(symbol, price)

      # Валидация параметров
      self._validate_order_parameters(
        symbol, side, quantity, order_type, price
      )

      # Проверка баланса
      quote_asset = self._get_symbol_filters(symbol)['quote_asset']
      balance = self.get_available_balance(quote_asset)

      if side == Client.SIDE_BUY:
        required = quantity * (price or self.get_current_price(symbol)) * SAFETY_MARGIN
        if required > balance:
          raise InsufficientFundsError(
            f"Need {required:.4f} {quote_asset}, available {balance:.4f}"
          )

      # Создание ордера
      params = {
        'symbol': symbol,
        'side': side,
        'type': order_type,
        'quantity': quantity
      }

      if order_type != Client.ORDER_TYPE_MARKET:
        params.update({
          'price': price,
          'timeInForce': time_in_force
        })

      return self.client.create_order(**params)

    except exceptions.BinanceAPIException as e:
      raise OrderExecutionError(f"API Error: {e.message}")
    except Exception as e:
      raise OrderExecutionError(f"Execution failed: {str(e)}")

  def cancel_order(self, symbol: str, order_id: str) -> Dict:
    """Отменяет активный ордер"""
    try:
      return self.client.cancel_order(
        symbol=symbol,
        orderId=order_id
      )
    except exceptions.BinanceAPIException as e:
      raise OrderCancelError(f"Cancel failed: {e.message}")

  def get_available_balance(self, asset: str) -> float:
    """Возвращает доступный баланс актива"""
    account = self.client.get_account()
    balance = next(
      (float(acc['free']) for acc in account['balances']
       if acc['asset'] == asset),
      0.0
    )
    return balance

  def get_current_price(self, symbol: str) -> float:
    """Возвращает текущую рыночную цену"""
    ticker = self.client.get_symbol_ticker(symbol=symbol)
    return float(ticker['price'])


# Custom Exceptions
class OrderExecutionError(Exception):
  pass


class OrderCancelError(Exception):
  pass


class InsufficientFundsError(OrderExecutionError):
  pass


class InvalidSymbolError(OrderExecutionError):
  pass


class InvalidOrderParameters(OrderExecutionError):
  pass