#src/telegram_bot/handlers/trade_handlers.py
import logging
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import (
  ContextTypes,
  CommandHandler,
  MessageHandler,
  filters,
  ConversationHandler,
  CallbackQueryHandler
)
from decimal import Decimal
from src.core.settings.telegram_config import TELEGRAM_ADMINS
from src.core.api.binance_client.transactions_executor import TransactionsExecutor, OrderExecutionError
from src.core.api.binance_client.info_fetcher import BinanceInfoFetcher
from src.core.settings.config import SYMBOLS, BINANCE_API_KEY, BINANCE_SECRET_KEY, TESTNET

logger = logging.getLogger(__name__)

SELECT_SYMBOL, ENTER_QUANTITY, CONFIRM_TRADE = range(3)


class TradeHandlers:
  def __init__(self):
    self.executor = TransactionsExecutor()
    self.info_fetcher = BinanceInfoFetcher(
          api_key=BINANCE_API_KEY,
          api_secret=BINANCE_SECRET_KEY,
          testnet=TESTNET
    )

  async def check_admin(self, update: Update) -> bool:
    user = update.effective_user
    if user.id not in TELEGRAM_ADMINS:
      await update.message.reply_text("⛔ У вас нет прав для выполнения этой операции")
      return False
    return True

  async def start_trade(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if not await self.check_admin(update):
      context.user_data.clear()
      return ConversationHandler.END

    action = update.message.text[1:].lower()
    context.user_data['action'] = action
    
    symbols_available = self._get_available_symbols(action)

    if not symbols_available:
        await update.message.reply_text(
            f"Нет доступных символов для операции '{action}' или недостаточно средств на балансе для ее начала."
        )
        context.user_data.clear()
        return ConversationHandler.END

    keyboard = [
      [InlineKeyboardButton(symbol, callback_data=symbol)]
      for symbol in symbols_available
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    action_rus = "покупки" if action == "buy" else "продажи"
    await update.message.reply_text(
      f"Выберите торговую пару для {action_rus}:",
      reply_markup=reply_markup
    )
    return SELECT_SYMBOL

  async def select_symbol(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()

    context.user_data['symbol'] = query.data
    action = context.user_data.get('action', 'операции')
    action_rus = "покупки" if action == "buy" else "продажи"

    await query.edit_message_text(
      f"Выбрана пара: {query.data}\nВведите количество для {action_rus}:"
    )
    return ENTER_QUANTITY

  async def enter_quantity(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    try:
      quantity_str = update.message.text
      quantity = Decimal(quantity_str)
      if quantity <= Decimal(0):
        await update.message.reply_text("❌ Количество должно быть положительным числом. Попробуйте снова.")
        return ENTER_QUANTITY
      
      context.user_data['quantity'] = quantity

      symbol = context.user_data['symbol']
      current_price = self.info_fetcher.get_current_price(symbol) # Returns Decimal
      
      estimated_cost_str = "не удалось рассчитать"
      if current_price and current_price > Decimal(0):
          estimated_cost = quantity * current_price
          estimated_cost_str = f"{estimated_cost:.2f} USDT (примерно)"


      await update.message.reply_text(
        f"Подтвердите операцию:\n"
        f"Действие: {context.user_data.get('action', '').upper()}\n"
        f"Символ: {symbol}\n"
        f"Количество: {quantity}\n"
        f"Примерная стоимость: {estimated_cost_str}\n\n"
        "Отправить ордер?",
        reply_markup=InlineKeyboardMarkup([
          [InlineKeyboardButton("✅ Да", callback_data="confirm"),
           InlineKeyboardButton("❌ Отмена", callback_data="cancel")]
        ])
      )
      return CONFIRM_TRADE
    except ValueError:
      await update.message.reply_text("❌ Некорректный формат количества. Введите число. Попробуйте снова.")
      return ENTER_QUANTITY
    except Exception as e:
      logger.error(f"Error in enter_quantity: {e}", exc_info=True)
      await update.message.reply_text("❌ Произошла ошибка при обработке количества. Попробуйте снова.")
      return ENTER_QUANTITY

  async def confirm_trade(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()

    action_to_perform = context.user_data.get('action')
    if not action_to_perform:
        await query.edit_message_text("❌ Действие не определено. Операция отменена.")
        context.user_data.clear()
        return ConversationHandler.END

    if query.data == "cancel":
        await query.edit_message_text("❌ Операция отменена.")
        context.user_data.clear()
        return ConversationHandler.END

    try:
        symbol = context.user_data.get('symbol')
        quantity_decimal = context.user_data.get('quantity') # Это Decimal

        if not symbol or quantity_decimal is None:
            await query.edit_message_text("❌ Не удалось получить данные для сделки. Операция отменена.")
            context.user_data.clear()
            return ConversationHandler.END
        
        action_upper = action_to_perform.upper()
        action_rus = "покупка" if action_upper == "BUY" else "продажа"

        await query.edit_message_text(f"⏳ Обработка {action_rus} ордера для {symbol}...")

        result = self.executor.execute_order(
            symbol=symbol,
            side=action_upper,
            quantity=float(quantity_decimal), # executor ожидает float
            order_type="MARKET"
        )

        if result and result.get('success'):
            executed_qty_val = result.get('executed_qty', 0.0)
            avg_price_val = result.get('avg_price', 0.0)
            base_asset = result.get('base_asset', symbol.replace("USDT", ""))
            quote_asset = result.get('quote_asset', "USDT")

            success_message = (
                f"✅ Успешная {action_rus} (статус: {result.get('status', 'N/A')}):\n"
                f"Символ: {result.get('symbol')}\n"
                f"Исполнено: {executed_qty_val:.8f} {base_asset}\n"
            )
            if avg_price_val > 0:
                 success_message += f"Средняя цена: {avg_price_val:.8f} {quote_asset}\n"
            else:
                 success_message += "Средняя цена: (недоступна или 0.0)\n"
            
            commission_val = result.get('commission', 0.0)
            commission_asset_val = result.get('commission_asset', '')
            if commission_val > 0 and commission_asset_val:
                success_message += f"Комиссия: {commission_val:.8f} {commission_asset_val}\n"

            await query.edit_message_text(success_message)

            try:src/core/api/binance_client/transactions_executor.py
                balance_base = self.info_fetcher.get_asset_balance(base_asset) # Возвращает dict или None
                balance_quote = self.info_fetcher.get_asset_balance(quote_asset)
                
                balance_message = f"\n💰 Балансы:\n"
                if balance_base:
                    balance_message += (f"{balance_base.get('asset', base_asset)}: "
                                        f"{balance_base.get('free', Decimal('0.0'))} (своб.) / "
                                        f"{balance_base.get('locked', Decimal('0.0'))} (забл.)\n")
                if balance_quote:
                    balance_message += (f"{balance_quote.get('asset', quote_asset)}: "
                                        f"{balance_quote.get('free', Decimal('0.0'))} (своб.) / "
                                        f"{balance_quote.get('locked', Decimal('0.0'))} (забл.)")
                
                await query.message.reply_text(text=balance_message)
            except Exception as bal_exc:
                logger.error(f"Ошибка при получении/отображении баланса для {symbol}: {bal_exc}", exc_info=True)
                await query.message.reply_text(text="ℹ️ Не удалось обновить информацию о балансе.")

        else:
            error_detail = "Причина неизвестна."
            if result:
                if isinstance(result.get('raw_response'), dict):
                    binance_msg = result['raw_response'].get('msg')
                    if binance_msg:
                        error_detail = f"Ответ биржи: {binance_msg}"
                elif result.get('status'):
                     error_detail = f"Статус ордера: {result.get('status')}"
            
            await query.edit_message_text(f"❌ Не удалось исполнить ордер для {symbol}.\n{error_detail}")
            logger.warning(f"Order execution not successful for {symbol}. Result: {result}")

    except OrderExecutionError as e: # Конкретные ошибки от executor
        logger.error(f"Trade error (OrderExecutionError) for {context.user_data.get('symbol', 'N/A')}: {str(e)}", exc_info=True)
        await query.edit_message_text(f"❌ Ошибка исполнения ордера: {str(e)}")
    except KeyError as e:
        logger.error(f"Trade error - KeyError: {str(e)} for symbol {context.user_data.get('symbol', 'N/A')}", exc_info=True)
        await query.edit_message_text(f"❌ Ошибка обработки ответа: ключ '{str(e)}' не найден. Сообщите администратору.")
    except Exception as e:
        logger.error(f"Trade error for symbol {context.user_data.get('symbol', 'N/A')}: {str(e)}", exc_info=True)
        await query.edit_message_text(f"❌ Произошла критическая ошибка: {str(e)}")
    finally:
        context.user_data.clear()

    return ConversationHandler.END

  async def cancel(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await update.message.reply_text("Операция отменена.")
    context.user_data.clear()
    return ConversationHandler.END

  def _get_available_symbols(self, action: str):
    return [s for s in SYMBOLS if self._has_balance_for_symbol(s, action)]

  def _has_balance_for_symbol(self, symbol: str, action: str) -> bool:
    asset_to_check = None
    try:
        if symbol not in self.executor.symbols_info:
            self.executor._get_symbol_filters(symbol) 

        symbol_details = self.executor.symbols_info.get(symbol)
        if not symbol_details:
            logger.warning(f"Не удалось получить детали символа {symbol} для проверки баланса.")
            return False 

        action_lower = action.lower()
        if action_lower == "buy":
            asset_to_check = symbol_details.get('quote_asset')
        elif action_lower == "sell":
            asset_to_check = symbol_details.get('base_asset')
        else:
            logger.warning(f"Неизвестное действие '{action}' для проверки баланса по символу {symbol}.")
            return False

        if asset_to_check:
            balance_info = self.info_fetcher.get_asset_balance(asset_to_check) # Возвращает dict {'free': Decimal, ...} или None
            if balance_info and isinstance(balance_info.get('free'), Decimal):
                 return balance_info['free'] > Decimal('0')
            logger.warning(f"Не удалось получить баланс или 'free' не Decimal для {asset_to_check} (символ {symbol}). balance_info: {balance_info}")
            return False
        else:
            logger.warning(f"Не удалось определить актив для проверки баланса (действие: {action}, символ: {symbol}).")
            return False

    except Exception as e:
        logger.error(f"Ошибка при проверке баланса для действия '{action}' по символу {symbol} (актив: {asset_to_check}): {e}", exc_info=True)
        return False


def get_trade_handlers():
  handler = TradeHandlers()

  conv_handler = ConversationHandler(
    entry_points=[
      CommandHandler("buy", handler.start_trade),
      CommandHandler("sell", handler.start_trade)
    ],
    states={
      SELECT_SYMBOL: [CallbackQueryHandler(handler.select_symbol)],
      ENTER_QUANTITY: [MessageHandler(filters.TEXT & ~filters.COMMAND, handler.enter_quantity)],
      CONFIRM_TRADE: [CallbackQueryHandler(handler.confirm_trade)]
    },
    fallbacks=[CommandHandler("cancel", handler.cancel)],
  )

  return [conv_handler]
