#src/core/api/binance_client/transactions_executor.py
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
    lot_size = self._get_symbol_filters(symbol)['filters']['LOT_SIZE']
    step = Decimal(lot_size['stepSize']).normalize()
    return float(Decimal(str(quantity)).quantize(step, ROUND_DOWN))

  def _format_price(self, symbol: str, price: float) -> float:
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
    logger = self.logger

    try:
      symbol_filters_data = self._get_symbol_filters(symbol)
      symbol_filters = symbol_filters_data.get('filters', {})

      lot_size = symbol_filters.get('LOT_SIZE', {
        'minQty': '0.001',
        'stepSize': '0.001'
      })

      notional_filter = symbol_filters.get('NOTIONAL', {
        'minNotional': '5.0',
        'applyToMarket': True
      })
      if 'MIN_NOTIONAL' in symbol_filters and 'NOTIONAL' not in symbol_filters:
        notional_filter = symbol_filters.get('MIN_NOTIONAL', {
          'minNotional': '5.0',
          'applyMinToMarket': True # Binance API uses applyMinToMarket for MIN_NOTIONAL
        })


      min_qty = float(lot_size.get('minQty', '0.001'))
      min_notional = float(notional_filter.get('minNotional', '5.0'))
      apply_to_market = notional_filter.get('applyToMarket', True)
      if 'applyMinToMarket' in notional_filter: # For MIN_NOTIONAL
        apply_to_market = notional_filter.get('applyMinToMarket', True)


      logger.debug(
        f"Validating order: {symbol} {side} {quantity} {order_type} | "
        f"Params: minQty={min_qty}, "
        f"minNotional={min_notional}, applyToMarket={apply_to_market}"
      )

      if quantity < min_qty:
        error_msg = f"Quantity {quantity} < minQty {min_qty} for {symbol}"
        logger.error(error_msg)
        raise InvalidOrderParameters(error_msg)

      if order_type == Client.ORDER_TYPE_MARKET:
        if apply_to_market:
          current_price_float = self.get_current_price(symbol)
          if not current_price_float or current_price_float <= 0:
            error_msg = f"Can't validate notional for {symbol} - current price unavailable or zero: {current_price_float}"
            logger.error(error_msg)
            raise InvalidOrderParameters(error_msg)

          notional_value = quantity * current_price_float
          if notional_value < min_notional:
            error_msg = (
              f"Notional value {notional_value:.4f} (qty {quantity} * price {current_price_float}) "
              f"is less than minNotional {min_notional:.4f} for {symbol}"
            )
            logger.error(error_msg)
            raise InvalidOrderParameters(error_msg)

      if order_type == Client.ORDER_TYPE_LIMIT:
        if not price:
          error_msg = f"Price required for limit orders for {symbol}"
          logger.error(error_msg)
          raise InvalidOrderParameters(error_msg)

        price_filter_rules = symbol_filters.get('PRICE_FILTER', {})
        tick_size_str = price_filter_rules.get('tickSize', '0.01')
        tick_size = Decimal(tick_size_str)
        if (Decimal(str(price)) % tick_size).compare(Decimal('0')) != 0:
          error_msg = f"Invalid price format for {symbol}. Price {price} is not a multiple of tickSize {tick_size}."
          logger.error(error_msg)
          raise InvalidOrderParameters(error_msg)

      logger.info(f"Order parameters validation passed for {symbol} {side} {quantity}")

    except KeyError as e:
      error_msg = f"Missing key in symbol data during validation for {symbol}: {str(e)}"
      logger.error(error_msg, exc_info=True)
      raise InvalidOrderParameters(error_msg)
    except InvalidOrderParameters:
      raise
    except Exception as e:
      error_msg = f"Unexpected validation error for {symbol}: {str(e)}"
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
    self.logger.info(f"🔄 Starting order execution: {symbol} {side} {quantity} {order_type}")

    try:
      symbol_info_data = self._get_symbol_filters(symbol)
      base_asset = symbol_info_data['base_asset']
      quote_asset = symbol_info_data['quote_asset']

      formatted_quantity = self._format_quantity(symbol, quantity)
      formatted_price = self._format_price(symbol, price) if price and order_type != Client.ORDER_TYPE_MARKET else None

      self.logger.debug(
        f"Formatted params for {symbol}: Qty: {quantity} → {formatted_quantity} | "
        f"Price: {price} → {formatted_price}"
      )

      self._validate_order_parameters(
        symbol,
        side,
        formatted_quantity,
        order_type,
        formatted_price
      )

      asset_to_check = quote_asset if side == Client.SIDE_BUY else base_asset
      available_balance = self.get_available_balance(asset_to_check)
      self.logger.debug(f"Available balance for {asset_to_check}: {available_balance}")

      if side == Client.SIDE_BUY and order_type == Client.ORDER_TYPE_MARKET:
        current_price_float = self.get_current_price(symbol)
        if current_price_float > 0:
          required_quote = Decimal(str(formatted_quantity)) * Decimal(str(current_price_float)) * Decimal(str(SAFETY_MARGIN))
          if Decimal(str(available_balance)) < required_quote:
            raise InsufficientFundsError(
              f"Need approx {required_quote:.4f} {quote_asset}, available {available_balance:.4f} for {symbol} BUY"
            )
      elif side == Client.SIDE_SELL:
        if Decimal(str(available_balance)) < Decimal(str(formatted_quantity)):
          raise InsufficientFundsError(
            f"Need {formatted_quantity} {base_asset}, available {available_balance} for {symbol} SELL"
          )

      order_params = {
        'symbol': symbol,
        'side': side.upper(),
        'type': order_type.upper(),
        'newOrderRespType': 'FULL'
      }

      if order_type == Client.ORDER_TYPE_MARKET:
        order_params['quantity'] = formatted_quantity
      elif order_type == Client.ORDER_TYPE_LIMIT:
        if not formatted_price:
          raise InvalidOrderParameters(f"Price is required for LIMIT order for {symbol}")
        order_params.update({
          'quantity': formatted_quantity,
          'price': str(formatted_price),
          'timeInForce': time_in_force
        })

      self.logger.debug(f"Sending order params to Binance for {symbol}: {order_params}")

      response = self.client.create_order(**order_params)
      self.logger.debug(f"Binance API response for {symbol} order: {json.dumps(response, indent=2)}")

      executed_qty_final = Decimal('0')
      avg_price_final = Decimal('0')
      commission_final = Decimal('0')
      commission_asset_final = ''
      order_status = response.get('status', 'UNKNOWN')

      fills = response.get('fills', [])
      if fills:
        accumulated_qty = Decimal('0')
        accumulated_quote_qty = Decimal('0')
        accumulated_commission = Decimal('0')

        for fill in fills:
          fill_qty = Decimal(str(fill.get('qty', '0')))
          fill_price = Decimal(str(fill.get('price', '0')))
          accumulated_qty += fill_qty
          accumulated_quote_qty += fill_qty * fill_price
          accumulated_commission += Decimal(str(fill.get('commission', '0')))
          if not commission_asset_final and fill.get('commissionAsset'):
            commission_asset_final = fill['commissionAsset']

        if accumulated_qty > Decimal('0'):
          executed_qty_final = accumulated_qty
          avg_price_final = accumulated_quote_qty / accumulated_qty
          commission_final = accumulated_commission
          self.logger.debug(
            f"Calculated from {len(fills)} fills for {symbol}: exec_qty={executed_qty_final}, avg_price={avg_price_final:.4f}")
        else:
          self.logger.warning(
            f"Fills array is present but total quantity from fills is 0 for {symbol}. Response: {response}")
          executed_qty_final = Decimal(str(response.get('executedQty', '0')))
          if executed_qty_final > Decimal('0'):
            self.logger.warning(
              f"Using executedQty ({executed_qty_final}) from main response for {symbol} as fills qty is 0. Avg price cannot be determined from fills.")
          else:
            self.logger.warning(f"executedQty from main response is also 0 for {symbol}.")

      elif response.get('executedQty'):
        executed_qty_final = Decimal(str(response.get('executedQty', '0')))
        if executed_qty_final > Decimal('0'):
          self.logger.warning(
            f"Order for {symbol} has executedQty={executed_qty_final} but no 'fills' data. "
            f"Avg price cannot be determined. This is common in Testnet. Status: {order_status}."
          )
        else:
          self.logger.warning(f"executedQty from main response is 0 and no fills for {symbol}.")
      else:
        self.logger.warning(
          f"No 'fills' and no 'executedQty' in response for {symbol}. Order likely not filled or partially filled without details. Status: {order_status}.")

      is_considered_executed = (order_status in ['FILLED', 'PARTIALLY_FILLED'] and executed_qty_final > Decimal('0')) or \
                               (order_status == 'NEW' and order_type != Client.ORDER_TYPE_MARKET)

      if not is_considered_executed and order_type == Client.ORDER_TYPE_MARKET:
        raise OrderExecutionError(
          f"Market order for {symbol} reported as {order_status} with zero executed quantity. Response: {json.dumps(response)}")

      result = {
        'symbol': symbol,
        'side': side,
        'order_type': order_type,
        'requested_qty': float(formatted_quantity),
        'executed_qty': float(executed_qty_final),
        'avg_price': float(avg_price_final.quantize(Decimal('0.00000001')) if avg_price_final > 0 else 0.0),
        'commission': float(commission_final),
        'commission_asset': commission_asset_final,
        'status': order_status,
        'success': is_considered_executed or order_status == 'FILLED',
        'exchange_id': response.get('orderId'),
        'raw_response': response,
        'base_asset': base_asset,
        'quote_asset': quote_asset
      }

      self.logger.info(
        f"✅ Order for {symbol} processed: Status {result['status']}, Executed {result['executed_qty']} @ ~{result['avg_price']:.4f} "
        f"(Commission: {result['commission']:.6f} {result['commission_asset']})"
      )
      return result

    except exceptions.BinanceAPIException as e:
      error_msg = f"🚨 Binance API Error for {symbol} [{e.status_code}]: {e.message}. Request: {e.request}"
      self.logger.error(error_msg)
      raise OrderExecutionError(error_msg)

    except InsufficientFundsError as e:
      self.logger.error(f"🔥 InsufficientFundsError for {symbol}: {str(e)}")
      raise

    except InvalidOrderParameters as e:
      self.logger.error(f"🔥 InvalidOrderParameters for {symbol}: {str(e)}")
      raise

    except Exception as e:
      error_msg = f"🔥 Critical error during order execution for {symbol}: {str(e)}"
      self.logger.error(error_msg, exc_info=True)
      raise OrderExecutionError(error_msg)

  def cancel_order(self, symbol: str, order_id: str) -> Dict:
    try:
      self.logger.info(f"Attempting to cancel order {order_id} for {symbol}")
      response = self.client.cancel_order(
        symbol=symbol,
        orderId=order_id
      )
      self.logger.info(f"Cancel order response for {order_id} ({symbol}): {response}")
      return response
    except exceptions.BinanceAPIException as e:
      self.logger.error(f"Cancel order failed for {order_id} ({symbol}): {e.message}")
      raise OrderCancelError(f"Cancel failed for {symbol} order {order_id}: {e.message}")

  def get_available_balance(self, asset: str) -> float:
    try:
      account = self.client.get_account()
      balance_info = next(
        (acc for acc in account['balances'] if acc['asset'] == asset),
        None
      )
      if balance_info:
        return float(balance_info['free'])
      self.logger.warning(f"Asset {asset} not found in account balances.")
      return 0.0
    except exceptions.BinanceAPIException as e:
      self.logger.error(f"Failed to get balance for {asset} due to API error: {e.message}")
      return 0.0
    except Exception as e:
      self.logger.error(f"Unexpected error getting balance for {asset}: {str(e)}")
      return 0.0

  def get_current_price(self, symbol: str) -> float:
    try:
      ticker = self.client.get_symbol_ticker(symbol=symbol)
      return float(ticker['price'])
    except exceptions.BinanceAPIException as e:
      self.logger.error(f"Failed to get price for {symbol} due to API error: {e.message}")
      return 0.0
    except Exception as e:
      self.logger.error(f"Unexpected error getting price for {symbol}: {str(e)}")
      return 0.0


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
