# src/core/data_logic/decision_processor/position_manager.py
import json
import uuid
from pathlib import Path
from decimal import Decimal
from datetime import datetime
from binance import Client
import logging
from typing import List, Dict, Optional
from src.core.settings.config import (
  BINANCE_API_KEY,
  BINANCE_SECRET_KEY,
  TESTNET, PROFIT_TAKE_LEVELS
)


class PositionManager:
  _data_dir = Path("collected_data/positions")

  _data_file = Path("collected_data/positions.json")

  class PositionError(Exception):
    ...

  class PositionNotFoundError(PositionError):
    ...

  class InvalidPositionDataError(PositionError):
    ...

  class PositionConflictError(PositionError):
    ...

  def __init__(self, symbol: str, info_fetcher):
    self.symbol = symbol
    self.info_fetcher = info_fetcher
    self.client = Client(
      api_key=BINANCE_API_KEY,
      api_secret=BINANCE_SECRET_KEY,
      testnet=TESTNET
    )
    self._data_file = self._data_dir / f"{symbol}.json"
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
      base_asset = self.symbol.replace("USDT", "")
      balance = self.client.get_asset_balance(asset=base_asset)
      free_balance = Decimal(balance['free'])

      if free_balance > 0:
        avg_price = self._get_avg_price()
        if avg_price > 0:  # Добавить проверку
          self.create_position(
            entry_price=avg_price,
            quantity=free_balance,
            position_type="LONG"
          )
    except Exception as e:
      logging.error(f"Sync error: {str(e)}")

  def _get_avg_price(self) -> Decimal:
    trades = self.client.get_my_trades(symbol=self.symbol)
    total_qty = sum(Decimal(trade['qty']) for trade in trades)
    total_cost = sum(Decimal(trade['qty']) * Decimal(trade['price']) for trade in trades)
    return total_cost / total_qty if total_qty > 0 else Decimal(0)