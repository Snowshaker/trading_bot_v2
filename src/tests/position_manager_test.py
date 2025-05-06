# tests/unit/core/data_logic/decision_processor/test_position_manager.py
import pytest
from decimal import Decimal
from unittest.mock import Mock, patch
import uuid
import json
from datetime import datetime
from pathlib import Path
import logging
from binance.exceptions import BinanceAPIException

from src.core.data_logic.decision_processor.position_manager import PositionManager
from src.core.settings.config import PROFIT_TAKE_LEVELS


@pytest.fixture
def mock_client():
  return Mock()


@pytest.fixture
def mock_info_fetcher():
  return Mock()


@pytest.fixture
def position_manager(tmp_path, mock_info_fetcher):
  with patch("src.core.data_logic.decision_processor.position_manager.POSITIONS", tmp_path):
    manager = PositionManager("BTCUSDT", mock_info_fetcher)
    manager.client = Mock()
    return manager


def test_initialization(position_manager, tmp_path):
  assert position_manager.symbol == "BTCUSDT"
  assert position_manager._data_file == tmp_path / "BTCUSDT.json"
  position_manager._data_file.parent.mkdir(parents=True, exist_ok=True)
  assert position_manager._data_file.parent.exists()


def test_create_position_success(position_manager):
  pos_id = position_manager.create_position(
    entry_price=Decimal("50000"),
    quantity=Decimal("0.1"),
    position_type="LONG"
  )

  positions = position_manager._load_positions()
  assert len(positions) == 1
  assert positions[0]["id"] == pos_id
  assert positions[0]["status"] == "open"


def test_create_position_invalid_type(position_manager):
  with pytest.raises(PositionManager.InvalidPositionDataError):
    position_manager.create_position(
      entry_price=Decimal("50000"),
      quantity=Decimal("0.1"),
      position_type="INVALID"
    )


def test_create_position_negative_values(position_manager):
  with pytest.raises(PositionManager.InvalidPositionDataError):
    position_manager.create_position(
      entry_price=Decimal("-50000"),
      quantity=Decimal("0.1"),
      position_type="LONG"
    )


def test_update_position_success(position_manager):
  pos_id = position_manager.create_position(
    Decimal("50000"), Decimal("0.1"), "LONG"
  )

  updated = position_manager.update_position(pos_id, {"current_price": 51000})
  assert updated["current_price"] == 51000.0


def test_update_position_invalid_field(position_manager):
  pos_id = position_manager.create_position(
    Decimal("50000"), Decimal("0.1"), "LONG"
  )

  with pytest.raises(PositionManager.InvalidPositionDataError):
    position_manager.update_position(pos_id, {"invalid_field": "value"})


def test_update_position_not_found(position_manager):
  with pytest.raises(PositionManager.PositionNotFoundError):
    position_manager.update_position("invalid_id", {"current_price": 51000})


def test_close_position_success(position_manager):
  pos_id = position_manager.create_position(
    Decimal("50000"), Decimal("0.1"), "LONG"
  )

  position_manager.close_position(pos_id)
  pos = position_manager.get_position(pos_id)
  assert pos["status"] == "closed"
  assert "exit_time" in pos


def test_close_position_already_closed(position_manager):
  pos_id = position_manager.create_position(
    Decimal("50000"), Decimal("0.1"), "LONG"
  )
  position_manager.close_position(pos_id)

  with pytest.raises(PositionManager.PositionConflictError):
    position_manager.close_position(pos_id)


def test_close_position_not_found(position_manager):
  with pytest.raises(PositionManager.PositionNotFoundError):
    position_manager.close_position("invalid_id")


def test_get_position(position_manager):
  pos_id = position_manager.create_position(
    Decimal("50000"), Decimal("0.1"), "LONG"
  )

  pos = position_manager.get_position(pos_id)
  assert pos["id"] == pos_id
  assert isinstance(pos["entry_price"], Decimal)


def test_get_active_positions(position_manager):
  position_manager.create_position(Decimal("50000"), Decimal("0.1"), "LONG")
  position_manager.create_position(Decimal("50000"), Decimal("0.2"), "SHORT")

  active = position_manager.get_active_positions()
  assert len(active) == 2
  position_manager.close_position(active[0]["id"])
  assert len(position_manager.get_active_positions()) == 1


def test_add_profit_level_success(position_manager):
  pos_id = position_manager.create_position(
    Decimal("50000"), Decimal("0.1"), "LONG"
  )

  level = list(PROFIT_TAKE_LEVELS.keys())[0]
  position_manager.add_profit_level(pos_id, level)
  pos = position_manager.get_position(pos_id)
  assert level in pos["profit_levels"]


def test_add_profit_level_invalid_level(position_manager):
  pos_id = position_manager.create_position(
    Decimal("50000"), Decimal("0.1"), "LONG"
  )

  with pytest.raises(PositionManager.InvalidPositionDataError):
    position_manager.add_profit_level(pos_id, 1.5)


def test_add_profit_level_duplicate(position_manager):
  pos_id = position_manager.create_position(
    Decimal("50000"), Decimal("0.1"), "LONG"
  )
  level = list(PROFIT_TAKE_LEVELS.keys())[0]
  position_manager.add_profit_level(pos_id, level)

  with pytest.raises(PositionManager.PositionConflictError):
    position_manager.add_profit_level(pos_id, level)


def test_sync_with_exchange_zero_balance(position_manager, mock_info_fetcher):
  mock_info_fetcher.get_symbol_info.return_value = {"base_asset": "BTC"}
  position_manager.client.get_asset_balance.return_value = {"free": "0"}

  position_manager.sync_with_exchange()
  assert len(position_manager.get_active_positions()) == 0


def test_sync_with_exchange_invalid_symbol_info(position_manager, mock_info_fetcher):
  mock_info_fetcher.get_symbol_info.return_value = None

  position_manager.sync_with_exchange()
  assert len(position_manager.get_active_positions()) == 0


def test_convert_to_decimal(position_manager):
  position = {
    "entry_price": 50000.0,
    "quantity": 0.1,
    "current_price": 51000.0,
    "trailing_stop": 49000.0,
    "profit_levels": [1.01, 1.02]
  }

  converted = position_manager._convert_to_decimal(position)
  assert isinstance(converted["entry_price"], Decimal)
  assert isinstance(converted["trailing_stop"], Decimal)


def test_get_avg_price_no_trades(position_manager):
  position_manager.client.get_my_trades.return_value = []
  assert position_manager._get_avg_price() is None