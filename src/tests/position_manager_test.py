# tests/position_manager_test.py
import pytest
from decimal import Decimal
from src.core.data_logic.decision_processor.position_manager import PositionManager
from src.core.settings.config import PROFIT_TAKE_LEVELS


def test_profit_level_management(tmp_path):
  PositionManager._data_file = tmp_path / "positions.json"
  pm = PositionManager("BTCUSDT")

  # Create position
  position_id = pm.create_position(
    entry_price=Decimal("50000"),
    quantity=Decimal("1"),
    position_type="LONG"
  )

  # Test valid levels
  for level in PROFIT_TAKE_LEVELS:
    pm.add_profit_level(position_id, float(level))
    pos = pm.get_position(position_id)
    assert float(level) in pos["profit_levels"]

  # Test invalid level
  with pytest.raises(PositionManager.InvalidPositionDataError):
    pm.add_profit_level(position_id, 3.0)

  # Test duplicate level
  with pytest.raises(PositionManager.PositionConflictError):
    pm.add_profit_level(position_id, 2.0)