# src/core/api/binance_client/info_fetcher.py
import logging
from decimal import Decimal
from binance import Client, exceptions
from typing import Dict, Optional
from src.core.settings.config import (
    BINANCE_API_KEY,
    BINANCE_SECRET_KEY,
    TESTNET,
    API_RATE_LIMIT_DELAY
)

class BinanceInfoFetcher:
    def __init__(self):
        self.client = Client(
            api_key=BINANCE_API_KEY,
            api_secret=BINANCE_SECRET_KEY,
            testnet=TESTNET
        )
        self.symbols_info = {}
        self.logger = logging.getLogger(__name__)

    def _load_symbols_info(self):
        """Кэширование информации о торговых парах"""
        try:
            exchange_info = self.client.get_exchange_info()
            self.symbols_info = {
                s['symbol']: {
                    'base_asset': s['baseAsset'],
                    'quote_asset': s['quoteAsset'],
                    'filters': {f['filterType']: f for f in s['filters']}
                }
                for s in exchange_info['symbols']
            }
        except exceptions.BinanceAPIException as e:
            self.logger.error(f"Symbols info error: {e.message}")

    def get_symbol_info(self, symbol: str) -> Optional[Dict]:
        """Информация о торговой паре"""
        if not self.symbols_info:
            self._load_symbols_info()
        return self.symbols_info.get(symbol)

    def get_current_price(self, symbol: str) -> Decimal:
        """Текущая цена"""
        try:
            ticker = self.client.get_symbol_ticker(symbol=symbol)
            return Decimal(ticker['price'])
        except exceptions.BinanceAPIException as e:
            self.logger.error(f"Price error: {e.message}")
            return Decimal(0)

    def get_asset_balance(self, asset: str) -> Dict[str, Decimal]:
        """Баланс актива"""
        try:
            account = self.client.get_account()
            for balance in account['balances']:
                if balance['asset'] == asset:
                    return {
                        'free': Decimal(balance['free']),
                        'locked': Decimal(balance['locked'])
                    }
            return {'free': Decimal(0), 'locked': Decimal(0)}
        except exceptions.BinanceAPIException as e:
            self.logger.error(f"Balance error: {e.message}")
            return {'free': Decimal(0), 'locked': Decimal(0)}

    def get_lot_size(self, symbol: str) -> Dict:
        """Параметры лота"""
        info = self.get_symbol_info(symbol)
        return info['filters']['LOT_SIZE'] if info else None