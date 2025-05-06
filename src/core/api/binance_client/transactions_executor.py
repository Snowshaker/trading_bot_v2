# src/core/api/binance_client/transactions_executor.py
import json
import logging

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
    self.logger = logging.getLogger(self.__class__.__name__)

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
    step = Decimal(lot_size['stepSize']).normalize()  # camelCase
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
    logger = self.logger

    try:
      # Получение информации о символе с защитой от ошибок
      symbol_filters = self._get_symbol_filters(symbol).get('filters', {})

      # Извлечение параметров с значениями по умолчанию для тестовой сети
      lot_size = symbol_filters.get('LOT_SIZE', {
        'minQty': '0.001',
        'stepSize': '0.001'
      })

      notional_filter = symbol_filters.get('NOTIONAL', {
        'minNotional': '5.0',
        'applyToMarket': True
      })

      # Параметры фильтров
      min_qty = float(lot_size.get('minQty', '0.001'))
      step_size = float(lot_size.get('stepSize', '0.001'))
      min_notional = float(notional_filter.get('minNotional', '5.0'))
      apply_to_market = notional_filter.get('applyToMarket', True)

      logger.debug(
        f"Validating order: {symbol} {side} {quantity} {order_type} | "
        f"Params: minQty={min_qty}, stepSize={step_size}, "
        f"minNotional={min_notional}, applyToMarket={apply_to_market}"
      )

      # 1. Проверка минимального количества
      if quantity < min_qty:
        error_msg = f"Quantity {quantity} < minQty {min_qty}"
        logger.error(error_msg)
        raise InvalidOrderParameters(error_msg)

      # 2. Проверка для рыночных ордеров на покупку
      if order_type == Client.ORDER_TYPE_MARKET and side == Client.SIDE_BUY:
        if apply_to_market:
          current_price = self.get_current_price(symbol)
          if not current_price:
            error_msg = "Can't validate notional - price unavailable"
            logger.error(error_msg)
            raise InvalidOrderParameters(error_msg)

          notional_value = quantity * current_price
          if notional_value < min_notional:
            error_msg = (
              f"Notional value {notional_value:.2f} < "
              f"min {min_notional:.2f}"
            )
            logger.error(error_msg)
            raise InvalidOrderParameters(error_msg)

      # 3. Проверка наличия цены для лимитных ордеров
      if order_type == Client.ORDER_TYPE_LIMIT:
        if not price:
          error_msg = "Price required for limit orders"
          logger.error(error_msg)
          raise InvalidOrderParameters(error_msg)

        # Дополнительная проверка формата цены
        tick_size = float(symbol_filters.get('PRICE_FILTER', {}).get('tickSize', '0.01'))
        formatted_price = round(price / tick_size) * tick_size
        if abs(price - formatted_price) > 1e-8:
          error_msg = f"Invalid price format. Use multiples of {tick_size}"
          logger.error(error_msg)
          raise InvalidOrderParameters(error_msg)

      logger.info("Order parameters validation passed")

    except KeyError as e:
      error_msg = f"Missing key in symbol data: {str(e)}"
      logger.error(error_msg, exc_info=True)
      raise InvalidOrderParameters(error_msg)
    except Exception as e:
      error_msg = f"Validation error: {str(e)}"
      logger.error(error_msg, exc_info=True)
      raise InvalidOrderParameters(error_msg)

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
    Исполняет ордер с полной обработкой ошибок, логированием и поддержкой разных форматов ответов
    """
    self.logger.info(f"🔄 Starting order execution: {symbol} {side} {quantity} {order_type}")

    try:
      # 1. Получение информации о символе
      symbol_info = self._get_symbol_filters(symbol)
      base_asset = symbol_info['base_asset']
      quote_asset = symbol_info['quote_asset']

      # 2. Форматирование параметров
      formatted_quantity = self._format_quantity(symbol, quantity)
      formatted_price = self._format_price(symbol, price) if price else None

      self.logger.debug(
        f"Formatted params: Qty: {quantity} → {formatted_quantity} | "
        f"Price: {price} → {formatted_price}"
      )

      # 3. Валидация параметров
      self._validate_order_parameters(
        symbol,
        side,
        formatted_quantity,
        order_type,
        formatted_price
      )

      # 4. Проверка баланса
      balance = self.get_available_balance(
        quote_asset if side == Client.SIDE_BUY else base_asset
      )

      self.logger.debug(f"Available balance: {balance} {quote_asset if side == 'BUY' else base_asset}")

      if side == Client.SIDE_BUY:
        current_price = self.get_current_price(symbol)
        required = Decimal(formatted_quantity) * Decimal(current_price) * Decimal(SAFETY_MARGIN)
        if required > balance:
          raise InsufficientFundsError(
            f"Need {required:.4f} {quote_asset}, available {balance:.4f}"
          )

      # 5. Подготовка параметров ордера
      order_params = {
        'symbol': symbol,
        'side': side,
        'type': order_type,
        'quantity': formatted_quantity,
        'newOrderRespType': 'FULL'
      }

      if order_type != Client.ORDER_TYPE_MARKET:
        order_params.update({
          'price': formatted_price,
          'timeInForce': time_in_force
        })

      self.logger.debug(f"Sending order params: {order_params}")

      # 6. Отправка ордера
      response = self.client.create_order(**order_params)
      self.logger.debug(f"Binance API response: {json.dumps(response, indent=2)}")

      # 7. Обработка ответа
      executed_qty = 0.0
      commission = 0.0
      avg_price = 0.0
      fills = response.get('fills', [])

      # Основной способ получения executedQty
      if 'executedQty' in response:
        executed_qty = float(response['executedQty'])
      elif fills:
        executed_qty = sum(float(f['qty']) for f in fills)
        total_quote = sum(float(f['qty']) * float(f['price']) for f in fills)
        avg_price = total_quote / executed_qty if executed_qty > 0 else 0
        commission = sum(float(f['commission']) for f in fills)
        self.logger.debug(f"Calculated from {len(fills)} fills")
      else:
        executed_qty = float(response.get('origQty', 0))
        self.logger.warning("Using origQty as fallback")

      # 8. Проверка исполнения
      if executed_qty <= 0:
        raise OrderExecutionError("Order not filled")

      # 9. Формирование результата
      result = {
        'symbol': symbol,
        'side': side,
        'order_type': order_type,
        'requested_qty': formatted_quantity,
        'executed_qty': executed_qty,
        'avg_price': avg_price,
        'commission': commission,
        'commission_asset': fills[0]['commissionAsset'] if fills else '',
        'status': response.get('status', 'UNKNOWN'),
        'success': True,
        'exchange_id': response.get('orderId', None)
      }

      self.logger.info(
        f"✅ Order executed: {executed_qty} {symbol} @ ~{avg_price:.4f} "
        f"(Commission: {commission:.4f} {result['commission_asset']})"
      )

      return result

    except exceptions.BinanceAPIException as e:
      error_msg = f"🚨 API Error [{e.status_code}]: {e.message}"
      self.logger.error(error_msg)
      raise OrderExecutionError(error_msg)

    except Exception as e:
      error_msg = f"🔥 Critical error: {str(e)}"
      self.logger.error(error_msg, exc_info=True)
      raise OrderExecutionError(error_msg)

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