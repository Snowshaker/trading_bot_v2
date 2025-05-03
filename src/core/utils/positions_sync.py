#src/core/utils/positions_sync.py
from binance import Client
from decimal import Decimal
import logging
from src.core.settings.config import BINANCE_API_KEY, BINANCE_SECRET_KEY, TESTNET

class PositionManagerrrr:
    def __init__(self, symbol: str):
        self.symbol = symbol
        self.client = Client(
            api_key=BINANCE_API_KEY,
            api_secret=BINANCE_SECRET_KEY,
            testnet=TESTNET
        )

    def sync_with_exchange(self):
        """Синхронизирует локальные позиции с реальными на бирже"""
        try:
            # Получение баланса базового актива (например, BTC для BTCUSDT)
            base_asset = self.symbol.replace("USDT", "")
            balance = self.client.get_asset_balance(asset=base_asset)
            free_balance = Decimal(balance['free'])

            if free_balance > 0:
                # Создаем позицию в локальном хранилище
                self.create_position(
                    entry_price=self._get_avg_price(),
                    quantity=free_balance,
                    position_type="LONG"
                )
        except Exception as e:
            logging.error(f"Sync failed: {str(e)}")

    def _get_avg_price(self) -> Decimal:
        """Получение средней цены открытия позиций"""
        # Реализуйте логику расчета средней цены на основе истории сделок
        trades = self.client.get_my_trades(symbol=self.symbol)
        total_qty = sum(Decimal(trade['qty']) for trade in trades)
        total_cost = sum(Decimal(trade['qty']) * Decimal(trade['price']) for trade in trades)
        return total_cost / total_qty if total_qty > 0 else Decimal(0)