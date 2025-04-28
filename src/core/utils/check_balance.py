from binance import Client
from src.core.settings.config import BINANCE_API_KEY, BINANCE_SECRET_KEY, TESTNET


def check_balance():
  client = Client(
    api_key=BINANCE_API_KEY,
    api_secret=BINANCE_SECRET_KEY,
    testnet=TESTNET
  )

  try:
    balance = client.get_account()['balances']
    for asset in balance:
      if float(asset['free']) > 0 or float(asset['locked']) > 0:
        print(f"{asset['asset']}:")
        print(f"  Free: {asset['free']}")
        print(f"  Locked: {asset['locked']}\n")
  except Exception as e:
    print(f"Ошибка: {str(e)}")


if __name__ == "__main__":
  check_balance()