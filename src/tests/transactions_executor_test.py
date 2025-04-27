from src.core.api.binance_client.transactions_executor import (
  TransactionsExecutor,
  OrderExecutionError,
  OrderCancelError
)
from binance.enums import *
import time


def test_safe_sell_order_demo():
  print("\n=== ДЕМО БЕЗОПАСНОЙ ПРОДАЖИ ===")
  print("Цель: создать и отменить лимитный ордер на продажу\n")

  executor = TransactionsExecutor()
  symbol = "BTCUSDT"
  order_id = None

  try:
    # 1. Показать текущий баланс BTC
    btc_balance = executor.get_available_balance("BTC")
    print(f"[1] Текущий баланс BTC: {btc_balance:.6f}")

    # 2. Создание лимитного ордера на продажу
    print("\n[2] Создание ордера...")
    order = executor.execute_order(
      symbol=symbol,
      side=SIDE_SELL,
      quantity=0.001,  # 0.001 BTC
      order_type=ORDER_TYPE_LIMIT,
      price=200000.00  # Заведомо высокая цена
    )
    order_id = order['orderId']
    print(f"✓ Ордер создан успешно!")
    print(f"   ID: {order_id}")
    print(f"   Цена: {order['price']}")
    print(f"   Количество: {order['origQty']} BTC")

    # 3. Искусственная задержка для демонстрации
    print("\n[3] Имитация ожидания (3 сек)...")
    time.sleep(3)

    # 4. Отмена ордера
    print("\n[4] Отмена ордера...")
    cancel_result = executor.cancel_order(symbol, order_id)
    print(f"✓ Ордер отменен!")
    print(f"   Статус: {cancel_result['status']}")
    print(f"   Исполнено: {cancel_result['executedQty']} BTC")

    # 5. Проверка баланса после отмены
    new_btc_balance = executor.get_available_balance("BTC")
    print(f"\n[5] Баланс BTC после отмены: {new_btc_balance:.6f}")
    print("   ✓ Баланс не изменился - ордер не исполнился")

  except OrderExecutionError as e:
    print(f"\n❌ Ошибка исполнения: {e}")
    if order_id:
      try:
        executor.cancel_order(symbol, order_id)
        print("   Попытка отмены ордера...")
      except OrderCancelError:
        pass
  except OrderCancelError as e:
    print(f"\n❌ Ошибка отмены: {e}")
  except Exception as e:
    print(f"\n❌ Неожиданная ошибка: {str(e)}")


if __name__ == "__main__":
  test_safe_sell_order_demo()