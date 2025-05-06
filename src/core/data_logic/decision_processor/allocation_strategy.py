import json
from decimal import Decimal, ROUND_DOWN, ROUND_UP, InvalidOperation
import logging
from typing import Dict, Optional
from src.core.settings.config import (
  BUY_THRESHOLD,
  SELL_THRESHOLD,
  ALLOCATION_MAX_PERCENT,
  MIN_ORDER_SIZE
)


class AllocationStrategy:
  def __init__(self, symbol: str, info_fetcher, position_manager):
    self.symbol = symbol
    self.info_fetcher = info_fetcher
    self.position_manager = position_manager
    self.logger = logging.getLogger(self.__class__.__name__)

  def _validate_symbol_info(self, symbol_info: Dict) -> bool:
    # Эта валидация должна быть более гибкой или вызываться с осторожностью,
    # так как структура ответа Binance может немного меняться.
    # Для простоты пока оставим базовую проверку.
    if not symbol_info or 'filters' not in symbol_info:
      self.logger.error(f"Symbol info for {self.symbol} is missing or malformed (no 'filters').")
      return False
    if 'LOT_SIZE' not in symbol_info['filters'] or 'NOTIONAL' not in symbol_info['filters']:  # или MIN_NOTIONAL
      self.logger.error(f"Essential filters LOT_SIZE or NOTIONAL missing for {self.symbol}.")
      # Проверим также MIN_NOTIONAL на случай старого API
      if 'MIN_NOTIONAL' not in symbol_info['filters']:
        return False
    return True

  def calculate_allocation(self, score: Decimal, signal: str) -> Optional[Dict]:
    try:
      if signal not in ("BUY", "SELL"):
        self.logger.error(f"Invalid signal type received: {signal} for {self.symbol}")
        return None

      if not isinstance(score, Decimal):
        self.logger.error(f"Invalid score type: {type(score)} for {self.symbol}. Score: {score}")
        try:
          score = Decimal(str(score))  # Попытка конвертации
        except InvalidOperation:
          self.logger.error(f"Failed to convert score to Decimal for {self.symbol}.")
          return None

      symbol_info = self.info_fetcher.get_symbol_info(self.symbol)
      if not symbol_info:
        self.logger.error(f"Symbol info not found for {self.symbol} in allocation calculation.")
        return None

      if not self._validate_symbol_info(symbol_info):  # Валидация структуры
        self.logger.error(f"Invalid symbol_info structure for {self.symbol}. Data:\n"
                          f"{json.dumps(symbol_info, indent=2, default=str)}")
        return None

      self.logger.debug(f"Processing {signal} signal for {self.symbol} "
                        f"with score: {score:.4f}")

      if signal == "BUY":
        result = self._calculate_buy(score, symbol_info)
      elif signal == "SELL":
        result = self._calculate_sell(score, symbol_info)
      else:  # На всякий случай
        result = None

      if result:
        self.logger.info(f"Allocation calculated for {self.symbol} {signal}: {result}")
        return result

      self.logger.warning(f"No allocation could be calculated for {self.symbol} {signal} with score {score:.4f}")
      return None

    except KeyError as e:
      self.logger.error(f"KeyError in allocation calculation for {self.symbol}: {str(e)}", exc_info=True)
      return None
    except ValueError as e:
      self.logger.error(f"ValueError in allocation calculation for {self.symbol}: {str(e)}", exc_info=True)
      return None
    except Exception as e:
      self.logger.error(f"Unexpected error in allocation calculation for {self.symbol}: "
                        f"{str(e)}", exc_info=True)
      return None

  def _get_filter_param(self, symbol_info: Dict, filter_type: str, param_name: str, default_value: str) -> Decimal:
    """Вспомогательная функция для безопасного извлечения параметра фильтра."""
    try:
      value_str = symbol_info['filters'][filter_type][param_name]
      return Decimal(value_str)
    except (KeyError, TypeError, InvalidOperation) as e:
      self.logger.warning(
        f"Could not get {param_name} from {filter_type} for {self.symbol}. Using default {default_value}. Error: {e}"
      )
      return Decimal(default_value)

  def _calculate_buy(self, score: Decimal, symbol_info: Dict) -> Optional[Dict]:
    try:
      BUY_THRESHOLD_DEC = Decimal(str(BUY_THRESHOLD))  # Убедимся, что тип Decimal
      if score < BUY_THRESHOLD_DEC:
        self.logger.debug(f"Buy score {score:.4f} for {self.symbol} is below threshold {BUY_THRESHOLD_DEC}")
        return None

      step_size = self._get_filter_param(symbol_info, 'LOT_SIZE', 'stepSize', '0.00000001')
      min_qty = self._get_filter_param(symbol_info, 'LOT_SIZE', 'minQty', '0.00000001')

      # Обработка NOTIONAL или MIN_NOTIONAL фильтра
      notional_filter_data = symbol_info['filters'].get('NOTIONAL')
      min_notional_fallback = '5.0'  # Значение по умолчанию для minNotional
      apply_to_market_default = True

      if notional_filter_data:
        min_notional_value = Decimal(str(notional_filter_data.get('minNotional', min_notional_fallback)))
        apply_to_market = notional_filter_data.get('applyToMarket', apply_to_market_default)
      elif 'MIN_NOTIONAL' in symbol_info['filters']:  # Старый API
        notional_filter_data = symbol_info['filters']['MIN_NOTIONAL']
        min_notional_value = Decimal(str(notional_filter_data.get('minNotional', min_notional_fallback)))
        apply_to_market = notional_filter_data.get('applyMinToMarket', apply_to_market_default)
      else:
        self.logger.warning(
          f"Neither NOTIONAL nor MIN_NOTIONAL filter found for {self.symbol}. Using default minNotional={min_notional_fallback}.")
        min_notional_value = Decimal(min_notional_fallback)
        apply_to_market = apply_to_market_default

      quote_asset = symbol_info.get('quote_asset', 'USDT')

      current_price = self.info_fetcher.get_current_price(self.symbol)  # Возвращает Decimal
      if not current_price or current_price <= Decimal('0'):
        self.logger.error(f"Invalid or zero current price ({current_price}) for {self.symbol} during BUY.")
        return None

      balance_data = self.info_fetcher.get_asset_balance(quote_asset)  # Возвращает Dict[str, Decimal]
      if not balance_data or balance_data['free'] <= Decimal('0'):
        self.logger.info(f"Zero or no free balance for {quote_asset} ({self.symbol}).")
        return None

      free_balance_quote = balance_data['free']

      # Расчет доступного капитала для сделки
      # score здесь может быть > 1 (STRONG_BUY). ALLOCATION_MAX_PERCENT - это максимум от баланса.
      # Сила сигнала (score) может влиять на то, какую часть от этого максимума мы берем.
      # Например, если score = 2.0 (STRONG_BUY), можно использовать весь ALLOCATION_MAX_PERCENT.
      # Если score = 1.0 (BUY), можно использовать половину от ALLOCATION_MAX_PERCENT.
      # Это требует более детальной логики масштабирования. Пока упростим:

      # Доля от максимальной аллокации, зависящая от силы сигнала (score > BUY_THRESHOLD)
      # Нормализуем score относительно BUY_THRESHOLD (если BUY_THRESHOLD=1, score=1.5 -> factor=1.5)
      # Ограничим максимальный фактор, например, 2.0 (для STRONG_BUY)
      score_factor = min(score / BUY_THRESHOLD_DEC, Decimal('2.0'))  # Max factor 2, if score is 2*BUY_THRESHOLD

      # Капитал для аллокации (не более ALLOCATION_MAX_PERCENT от свободного баланса)
      max_capital_for_trade = free_balance_quote * (ALLOCATION_MAX_PERCENT / Decimal('100'))

      # Аллоцируемый капитал = max_capital_for_trade * (доля от силы сигнала, но не более 100% от max_capital_for_trade)
      # Если score_factor = 1 (т.е. score == BUY_THRESHOLD), то берем, например, 50% от max_capital_for_trade
      # Если score_factor = 2 (т.е. score == 2*BUY_THRESHOLD), то берем 100% от max_capital_for_trade
      # Линейная интерполяция: (score_factor - 1) / (2-1) -> от 0 до 1. Прибавим 0.5, чтобы было от 0.5 до 1.5, но клипнем до 1.
      # Простая версия: если score сильный, берем больше.

      effective_allocation_percentage_of_max = Decimal('0.5')  # Базовая аллокация при минимальном BUY_THRESHOLD
      if score_factor > Decimal('1.0'):  # Если сигнал сильнее порога
        effective_allocation_percentage_of_max += (score_factor - Decimal('1.0')) * Decimal(
          '0.5')  # Добавляем до 50% сверху
      effective_allocation_percentage_of_max = min(effective_allocation_percentage_of_max,
                                                   Decimal('1.0'))  # Не более 100% от max_capital_for_trade

      allocated_capital = max_capital_for_trade * effective_allocation_percentage_of_max

      # Убедимся, что аллоцированный капитал не меньше MIN_ORDER_SIZE (в quote_asset)
      if allocated_capital < MIN_ORDER_SIZE:
        if max_capital_for_trade >= MIN_ORDER_SIZE:  # Если можем взять MIN_ORDER_SIZE
          allocated_capital = MIN_ORDER_SIZE
          self.logger.debug(
            f"Calculated allocation {allocated_capital} for {self.symbol} was less than MIN_ORDER_SIZE {MIN_ORDER_SIZE}. Adjusted to MIN_ORDER_SIZE.")
        else:
          self.logger.info(
            f"Max capital for trade {max_capital_for_trade:.4f} {quote_asset} for {self.symbol} "
            f"is less than MIN_ORDER_SIZE {MIN_ORDER_SIZE} {quote_asset}. Cannot BUY."
          )
          return None

      # Рассчитанное количество базового актива
      raw_quantity = allocated_capital / current_price
      quantity = raw_quantity.quantize(step_size, rounding=ROUND_DOWN)

      # Проверка минимального количества и минимального номинала
      if quantity < min_qty:
        self.logger.info(f"Calculated quantity {quantity} for {self.symbol} BUY is less than minQty {min_qty}.")
        # Попробовать увеличить до min_qty, если это возможно по балансу и min_notional
        quantity = min_qty
        if quantity * current_price > allocated_capital or quantity * current_price > free_balance_quote:
          self.logger.info(
            f"Cannot adjust quantity to minQty {min_qty} for {self.symbol} due to balance/notional constraints.")
          return None
        self.logger.debug(f"Adjusted quantity to minQty {min_qty} for {self.symbol} BUY.")

      final_notional = quantity * current_price
      if apply_to_market and final_notional < min_notional_value:
        self.logger.info(
          f"Final notional {final_notional:.4f} for {self.symbol} BUY is less than minNotional {min_notional_value:.4f}. "
          f"Qty: {quantity}, Price: {current_price}"
        )
        # Попробовать увеличить количество, чтобы удовлетворить min_notional
        required_qty_for_min_notional = (min_notional_value / current_price).quantize(step_size, rounding=ROUND_UP)
        if required_qty_for_min_notional * current_price > allocated_capital or \
          required_qty_for_min_notional * current_price > free_balance_quote:
          self.logger.info(f"Cannot adjust quantity for {self.symbol} to meet minNotional due to balance constraints.")
          return None
        quantity = required_qty_for_min_notional
        final_notional = quantity * current_price
        self.logger.debug(
          f"Adjusted quantity to {quantity} for {self.symbol} to meet minNotional. New notional: {final_notional}")

      # Финальная проверка, что мы не превышаем баланс
      if quantity * current_price > free_balance_quote * Decimal('1.0001'):  # Небольшой допуск на округления
        self.logger.error(
          f"FATAL: Calculated order cost {quantity * current_price:.4f} {quote_asset} for {self.symbol} BUY "
          f"exceeds free balance {free_balance_quote:.4f} {quote_asset} after all adjustments."
        )
        return None

      if quantity <= Decimal(0):
        self.logger.info(f"Final quantity for {self.symbol} BUY is zero or negative.")
        return None

      return {
        'action': 'BUY',
        'quantity': float(quantity),  # TransactionsExecutor ожидает float
        'calculated_notional': float(final_notional),
        'min_notional_filter': float(min_notional_value),
        'current_price': float(current_price)
      }

    except Exception as e:
      self.logger.error(f"Buy calculation error for {self.symbol}: {str(e)}", exc_info=True)
      return None

  def _calculate_sell(self, score: Decimal, symbol_info: Dict) -> Optional[Dict]:
    try:
      self.logger.debug(f"[SELL] Starting calculation for {self.symbol}. Score: {score:.4f}")

      SELL_THRESHOLD_DEC = Decimal(str(SELL_THRESHOLD))  # Убедимся, что тип Decimal
      if score > SELL_THRESHOLD_DEC:  # score отрицательный, SELL_THRESHOLD тоже. score=-1, threshold=-0.5 -> (-1 > -0.5) is False -> OK
        # score=-0.2, threshold=-0.5 -> (-0.2 > -0.5) is True -> Skip
        self.logger.debug(
          f"[SELL] Score {score:.4f} for {self.symbol} is above (less negative/positive than) threshold {SELL_THRESHOLD_DEC}")
        return None

      step_size = self._get_filter_param(symbol_info, 'LOT_SIZE', 'stepSize', '0.00000001')
      min_qty = self._get_filter_param(symbol_info, 'LOT_SIZE', 'minQty', '0.00000001')
      base_asset = symbol_info.get('base_asset')
      if not base_asset:
        self.logger.error(f"[SELL] Missing base_asset in symbol_info for {self.symbol}")
        return None

      # Обработка NOTIONAL или MIN_NOTIONAL фильтра для рыночных продаж
      notional_filter_data = symbol_info['filters'].get('NOTIONAL')
      min_notional_fallback = '5.0'
      apply_to_market_default = True  # Для продаж это обычно тоже True, если фильтр есть

      if notional_filter_data:
        min_notional_value = Decimal(str(notional_filter_data.get('minNotional', min_notional_fallback)))
        apply_to_market = notional_filter_data.get('applyToMarket', apply_to_market_default)
      elif 'MIN_NOTIONAL' in symbol_info['filters']:
        notional_filter_data = symbol_info['filters']['MIN_NOTIONAL']
        min_notional_value = Decimal(str(notional_filter_data.get('minNotional', min_notional_fallback)))
        apply_to_market = notional_filter_data.get('applyMinToMarket', apply_to_market_default)  # Имя поля другое
      else:
        self.logger.warning(
          f"[SELL] Neither NOTIONAL nor MIN_NOTIONAL filter found for {self.symbol}. Using default minNotional={min_notional_fallback}.")
        min_notional_value = Decimal(min_notional_fallback)
        apply_to_market = apply_to_market_default

      balance_data = self.info_fetcher.get_asset_balance(base_asset)
      if not balance_data or balance_data['free'] <= Decimal(0):
        self.logger.info(f"[SELL] Zero or no free balance for {base_asset} ({self.symbol}).")
        return None
      available_qty_base = balance_data['free']
      self.logger.info(f"[SELL] Available {base_asset} for {self.symbol}: {available_qty_base:.8f}")

      # Логика определения количества к продаже
      # abs_score будет >= abs(SELL_THRESHOLD)
      # Например, SELL_THRESHOLD = -0.45. Если score = -1.0 (STRONG_SELL), abs(score) = 1.0
      # Если score = -0.5, abs(score) = 0.5
      # Мы хотим продать долю, пропорциональную силе сигнала, или всё, если сигнал очень сильный.

      # Нормализуем силу сигнала. Максимальный score по модулю = 2.0 (STRONG_SELL)
      # abs(SELL_THRESHOLD) - это минимальный порог для продажи.
      # (abs(score) - abs(SELL_THRESHOLD_DEC)) / (2.0 - abs(SELL_THRESHOLD_DEC)) -> от 0 до 1, как далеко мы от порога к макс.силе

      normalized_sell_strength = Decimal('0.0')
      max_abs_score_sell = Decimal('2.0')  # Соответствует STRONG_SELL
      abs_sell_threshold = abs(SELL_THRESHOLD_DEC)

      if abs(score) >= max_abs_score_sell:  # Очень сильный сигнал, продать всё
        normalized_sell_strength = Decimal('1.0')
      elif abs(score) > abs_sell_threshold:  # Сигнал сильнее порога
        # Линейная интерполяция доли продажи
        # (чем score более отрицательный, тем больше продаем)
        # Пример: SELL_THRESHOLD = -0.5 (abs=0.5), STRONG_SELL = -2.0 (abs=2.0)
        # score = -1.0 (abs=1.0). (1.0 - 0.5) / (2.0 - 0.5) = 0.5 / 1.5 = 0.33
        # Это доля "сверх" минимального. Т.е. можно продать (например) 50% + 0.33 * 50%
        # Упрощенная версия:
        # if abs(score) >= 1.0 (например, "SELL" или "STRONG_SELL"), продать все.
        # Иначе (если score между SELL_THRESHOLD и -1.0), продать долю.
        if abs(score) >= Decimal('1.0'):  # Если обычный "SELL" или "STRONG_SELL"
          normalized_sell_strength = Decimal('1.0')  # Продать всё
        else:  # Если сигнал слабее "SELL", но сильнее порога
          # Продаем пропорционально от abs(SELL_THRESHOLD) до 1.0
          # abs(score) будет здесь между abs(SELL_THRESHOLD) и 1.0
          # (abs(score) - abs_sell_threshold) / (1.0 - abs_sell_threshold)
          # Эта формула даст от 0 до 1 в этом диапазоне.
          # Пример: SELL_THRESHOLD=-0.5 (abs=0.5). score=-0.75 (abs=0.75)
          # (0.75 - 0.5) / (1.0 - 0.5) = 0.25 / 0.5 = 0.5. Продаем 50% от доступного.
          if (Decimal('1.0') - abs_sell_threshold) > Decimal('0.0001'):  # Защита от деления на ноль
            normalized_sell_strength = (abs(score) - abs_sell_threshold) / (Decimal('1.0') - abs_sell_threshold)
            normalized_sell_strength = max(Decimal('0.1'),
                                           min(normalized_sell_strength, Decimal('1.0')))  # Минимум 10% если уж продаем
          else:  # Если SELL_THRESHOLD очень близок к -1.0
            normalized_sell_strength = Decimal('1.0')  # Продать всё
      else:  # score == SELL_THRESHOLD (минимально допустимый для продажи)
        normalized_sell_strength = Decimal('0.25')  # Продать небольшую часть, например 25%

      raw_quantity_to_sell = available_qty_base * normalized_sell_strength
      quantity_to_sell = raw_quantity_to_sell.quantize(step_size, rounding=ROUND_DOWN)

      self.logger.debug(
        f"[SELL] {self.symbol} | Score: {score:.4f}, NormStrength: {normalized_sell_strength:.4f} | "
        f"Avail: {available_qty_base:.8f} | RawSellQty: {raw_quantity_to_sell:.8f} | FinalSellQty: {quantity_to_sell:.8f}"
      )

      if quantity_to_sell < min_qty:
        # Если доступного для продажи (даже всего) меньше min_qty, и это не пыль
        if available_qty_base >= min_qty and available_qty_base > Decimal(
          0):  # Проверяем, что сам баланс не меньше min_qty
          # Если рассчитанное количество меньше min_qty, но у нас есть min_qty или больше,
          # и сигнал достаточно сильный, то можно продать min_qty.
          # Здесь нужно решить, стоит ли продавать min_qty, если стратегия сказала продать меньше.
          # Пока что, если расчетное < min_qty, но available_qty >= min_qty, то не продаем, если сигнал не очень сильный.
          # Если normalized_sell_strength > 0.5 (достаточно сильный сигнал), то можно попробовать продать min_qty.
          if normalized_sell_strength >= Decimal('0.5') and available_qty_base >= min_qty:
            quantity_to_sell = min_qty.quantize(step_size,
                                                rounding=ROUND_DOWN)  # Убедимся, что min_qty тоже кратно step_size
            self.logger.info(
              f"[SELL] Adjusted quantity to minQty {quantity_to_sell} for {self.symbol} due to strong signal and available amount.")
          else:
            self.logger.info(
              f"[SELL] Calculated quantity {quantity_to_sell:.8f} for {self.symbol} is less than minQty {min_qty:.8f}. "
              f"Available: {available_qty_base:.8f}. Signal strength: {normalized_sell_strength:.4f}. Skipping sell."
            )
            return None
        else:  # Если самого баланса меньше min_qty
          self.logger.info(
            f"[SELL] Available quantity {available_qty_base:.8f} for {self.symbol} is less than minQty {min_qty:.8f}. Skipping sell."
          )
          return None

      # Проверка минимального ноушенала для ПРОДАЖИ (если применимо)
      current_price = self.info_fetcher.get_current_price(self.symbol)
      if not current_price or current_price <= Decimal('0'):
        self.logger.error(f"[SELL] Invalid or zero current price ({current_price}) for {self.symbol}.")
        return None

      notional_value = quantity_to_sell * current_price
      if apply_to_market and notional_value < min_notional_value:
        self.logger.info(
          f"[SELL] Notional value {notional_value:.4f} for {self.symbol} (Qty: {quantity_to_sell}) "
          f"is less than minNotional {min_notional_value:.4f}. Skipping sell."
        )
        # В случае продажи, если ноушенал маленький, обычно просто не продаем,
        # а не пытаемся увеличить количество (т.к. это изменит стратегию)
        return None

      if quantity_to_sell <= Decimal(0):
        self.logger.info(f"Final quantity to sell for {self.symbol} is zero or negative.")
        return None

      self.logger.info(
        f"[SELL] Calculated to sell: {quantity_to_sell:.8f} {self.symbol} "
        f"(Value: {notional_value:.2f} {symbol_info.get('quote_asset', 'USDT')})"
      )

      return {
        'action': 'SELL',
        'quantity': float(quantity_to_sell),  # TransactionsExecutor ожидает float
        'calculated_notional': float(notional_value),
        'available_before_sell': float(available_qty_base),
        'current_price': float(current_price)
      }

    except Exception as e:
      self.logger.error(f"[SELL] Critical error for {self.symbol}: {str(e)}", exc_info=True)
      return None