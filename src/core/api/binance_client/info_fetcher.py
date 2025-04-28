# src/core/api/binance_client/info_fetcher.py
import logging

from binance import Client, exceptions
from decimal import Decimal
from typing import Dict, Optional
from src.core.settings.config import BINANCE_API_KEY, BINANCE_SECRET_KEY, TESTNET

class BinanceInfoFetcher:
    def __init__(self):
        self._client = Client(
            api_key=BINANCE_API_KEY,
            api_secret=BINANCE_SECRET_KEY,
            testnet=TESTNET
        )
        self._symbols_info: Optional[Dict] = None

    def _load_symbols_info(self) -> None:
        """Загружает и кеширует информацию о торговых парах"""
        try:
            exchange_info = self._client.get_exchange_info()
            self._symbols_info = {
                s['symbol']: {
                    'filters': {f['filterType']: f for f in s['filters']},
                    'base_asset': s['baseAsset'],
                    'quote_asset': s['quoteAsset']
                }
                for s in exchange_info['symbols']
            }
        except exceptions.BinanceAPIException as e:
            raise BinanceConnectionError(f"Failed to load symbols info: {e}")

    def get_current_prices(self, symbols: list) -> Dict[str, float]:
        """Возвращает текущие цены для указанных символов"""
        try:
            # Убираем параметр symbol для получения всех цен
            prices = self._client.get_symbol_ticker()
            return {
                item['symbol']: float(item['price'])
                for item in prices if item['symbol'] in symbols
            }
        except exceptions.BinanceAPIException as e:
            raise BinanceConnectionError(f"Price fetch failed: {e}")

    def get_current_price(self, symbol: str) -> float:
        """Получение текущей цены для конкретного символа"""
        prices = self.get_current_prices([symbol])
        return prices.get(symbol, 0.0)

    def get_asset_balance(self, asset: str) -> Dict[str, Decimal]:
        """Возвращает баланс в Decimal формате"""
        try:
            account = self._client.get_account()
            for balance in account['balances']:
                if balance['asset'] == asset:
                    return {
                        'free': Decimal(balance['free']),
                        'locked': Decimal(balance['locked'])
                    }
            return {'free': Decimal(0), 'locked': Decimal(0)}
        except Exception as e:
            logging.error(f"Balance error: {str(e)}")
            return {'free': Decimal(0), 'locked': Decimal(0)}

    def get_symbol_info(self, symbol: str) -> Dict:
        """Возвращает информацию о торговой паре"""
        if not self._symbols_info:
            self._load_symbols_info()
        return self._symbols_info.get(symbol)

    def get_lot_size(self, symbol: str) -> Dict:
        """Возвращает параметры лота для символа"""
        info = self.get_symbol_info(symbol)
        return info['filters']['LOT_SIZE'] if info else None

# Исключения
class BinanceConnectionError(Exception):
    pass