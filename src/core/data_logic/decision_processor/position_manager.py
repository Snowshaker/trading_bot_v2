# src/core/data_logic/decision_processor/position_manager.py
import json
import uuid
from pathlib import Path
from decimal import Decimal, InvalidOperation
from datetime import datetime
from binance import Client
import logging
from typing import List, Dict, Optional
from src.core.settings.config import (
    BINANCE_API_KEY,
    BINANCE_SECRET_KEY,
    TESTNET,
    PROFIT_TAKE_LEVELS
)
from src.core.paths import POSITIONS
import logging


class PositionManager:
    class PositionError(Exception):
        pass

    class PositionNotFoundError(PositionError):
        pass

    class InvalidPositionDataError(PositionError):
        pass

    class PositionConflictError(PositionError):
        pass

    def __init__(self, symbol: str, info_fetcher):
        self.symbol = symbol
        self.info_fetcher = info_fetcher
        self.logger = logging.getLogger(self.__class__.__name__)  # <-- Добавьте эту строку
        self.client = Client(
            api_key=BINANCE_API_KEY,
            api_secret=BINANCE_SECRET_KEY,
            testnet=TESTNET
        )
        self._data_file = POSITIONS / f"{symbol}.json"
        self._data_file.parent.mkdir(parents=True, exist_ok=True)

    def _load_positions(self) -> List[Dict]:
        if not self._data_file.exists():
            return []
        with open(self._data_file, 'r') as f:
            return json.load(f)

    def _save_positions(self, positions: List[Dict]) -> None:
        with open(self._data_file, 'w') as f:
            json.dump(positions, f, indent=2, default=str)

    def create_position(
        self,
        entry_price: Decimal,
        quantity: Decimal,
        position_type: str,
        trailing_stop: Decimal = None
    ) -> str:
        if position_type not in ("LONG", "SHORT"):
            raise self.InvalidPositionDataError("Invalid position type")

        if entry_price <= 0 or quantity <= 0:
            raise self.InvalidPositionDataError("Prices and quantities must be positive")

        position_id = str(uuid.uuid4())
        new_position = {
            "id": position_id,
            "symbol": self.symbol,
            "status": "open",
            "entry_price": float(entry_price),
            "quantity": float(quantity),
            "position_type": position_type,
            "trailing_stop": float(trailing_stop) if trailing_stop else None,
            "entry_time": datetime.utcnow().isoformat(),
            "profit_levels": [],
            "current_price": float(entry_price)
        }

        positions = self._load_positions()
        positions.append(new_position)
        self._save_positions(positions)
        return position_id

    def update_position(self, position_id: str, updates: Dict) -> Dict:
        positions = self._load_positions()
        for idx, pos in enumerate(positions):
            if pos["id"] == position_id:
                valid_fields = {"current_price", "trailing_stop", "status", "quantity"}
                for key in updates:
                    if key not in valid_fields:
                        raise self.InvalidPositionDataError(f"Invalid field: {key}")

                updates = {k: float(v) if isinstance(v, Decimal) else v for k, v in updates.items()}
                positions[idx].update(updates)
                self._save_positions(positions)
                return positions[idx]
        raise self.PositionNotFoundError(f"Position {position_id} not found")

    def close_position(self, position_id: str) -> None:
        positions = self._load_positions()
        for idx, pos in enumerate(positions):
            if pos["id"] == position_id:
                if pos["status"] == "closed":
                    raise self.PositionConflictError("Position already closed")
                positions[idx]["status"] = "closed"
                positions[idx]["exit_time"] = datetime.utcnow().isoformat()
                self._save_positions(positions)
                return
        raise self.PositionNotFoundError(f"Position {position_id} not found")

    def get_position(self, position_id: str) -> Optional[Dict]:
        for pos in self._load_positions():
            if pos["id"] == position_id:
                return self._convert_to_decimal(pos)
        return None

    def get_active_positions(self) -> List[Dict]:
        return [
            self._convert_to_decimal(pos)
            for pos in self._load_positions()
            if pos["symbol"] == self.symbol and pos["status"] == "open"
        ]

    def add_profit_level(self, position_id: str, level: float) -> None:
        if level not in PROFIT_TAKE_LEVELS:
            raise self.InvalidPositionDataError(
                f"Invalid profit level: {level}. Allowed: {list(PROFIT_TAKE_LEVELS.keys())}"
            )

        positions = self._load_positions()
        for idx, pos in enumerate(positions):
            if pos["id"] == position_id:
                if level in pos["profit_levels"]:
                    raise self.PositionConflictError(f"Level {level} already added")
                positions[idx]["profit_levels"].append(level)
                self._save_positions(positions)
                return
        raise self.PositionNotFoundError(f"Position {position_id} not found")

    def _convert_to_decimal(self, position: Dict) -> Dict:
        return {
            **position,
            "entry_price": Decimal(str(position["entry_price"])),
            "quantity": Decimal(str(position["quantity"])),
            "current_price": Decimal(str(position["current_price"])),
            "trailing_stop": Decimal(str(position["trailing_stop"])) if position["trailing_stop"] else None,
            "profit_levels": [float(level) for level in position["profit_levels"]]
        }

    def sync_with_exchange(self):
        try:
            # 1. Получаем информацию о символе для правильного определения базового актива
            symbol_info = self.info_fetcher.get_symbol_info(self.symbol)
            if not symbol_info:
                self.logger.error(f"Symbol info not found for {self.symbol}")
                return

            base_asset = symbol_info['base_asset']  # Вместо грубой замены USDT

            # 2. Получаем и валидируем баланс
            balance = self.client.get_asset_balance(asset=base_asset)
            self.logger.debug(f"Raw balance response: {balance}")

            if not balance or not isinstance(balance, dict):
                self.logger.warning(f"Invalid balance format for {base_asset}")
                return

            # 3. Безопасное извлечение и конвертация значений
            free_str = balance.get('free', '0')
            try:
                free_balance = Decimal(free_str)
            except InvalidOperation:
                self.logger.error(f"Invalid balance value: {free_str}")
                free_balance = Decimal(0)

            # 4. Логика создания позиции
            if free_balance > Decimal(0):
                avg_price = self._get_avg_price()
                if avg_price and avg_price > Decimal(0):
                    self.logger.info(f"Creating position for {free_balance} {base_asset}")
                    self.create_position(
                        entry_price=avg_price,
                        quantity=free_balance,
                        position_type="LONG"
                    )

        except Exception as e:
            self.logger.error(f"Sync error: {str(e)}", exc_info=True)

    def _get_avg_price(self) -> Optional[Decimal]:
        try:
            trades = self.client.get_my_trades(symbol=self.symbol)
            if not trades:
                return None

            total_qty = Decimal(0)
            total_cost = Decimal(0)

            for trade in trades:
                qty = Decimal(trade['qty'])
                price = Decimal(trade['price'])
                total_qty += qty
                total_cost += qty * price

            return total_cost / total_qty if total_qty > 0 else None

        except Exception as e:
            self.logger.error(f"Error calculating avg price: {str(e)}")
            return None