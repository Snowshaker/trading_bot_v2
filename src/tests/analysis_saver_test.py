# tests/unit/core/api/tradingview_client/test_analysis_saver.py
import json
from decimal import Decimal
from datetime import datetime
from pathlib import Path
from unittest.mock import patch, mock_open
import pytest
from src.core.api.tradingview_client.analysis_saver import AnalysisSaver, DecimalEncoder


class TestDecimalEncoder:
  def test_decimal_encoder_with_decimal(self):
    data = {"value": Decimal("10.5")}
    result = json.dumps(data, cls=DecimalEncoder)
    assert result == '{"value": 10.5}'

  def test_decimal_encoder_with_other_types(self):
    data = {"value": "test", "num": 123}
    result = json.dumps(data, cls=DecimalEncoder)
    assert result == '{"value": "test", "num": 123}'


class TestAnalysisSaver:
  @pytest.fixture
  def storage_path(self, tmp_path):
    return tmp_path / "analysis"

  @pytest.fixture
  def saver(self, storage_path):
    return AnalysisSaver(storage_path)

  def test_init_creates_directory(self, storage_path):
    assert not storage_path.exists()
    AnalysisSaver(storage_path)
    assert storage_path.exists()

  def test_transform_entry_structure(self, saver, mocker):
      mock_time = datetime(2023, 1, 1, 12, 0, 0)
      # Исправленный мокинг через патчинг модуля анализа
      datetime_mock = mocker.patch("src.core.api.tradingview_client.analysis_saver.datetime")
      datetime_mock.utcnow.return_value = mock_time

      symbol = "BTCUSD"
      data = {
          "1H": {"score": Decimal(5.5), "recommendation": "BUY"},
          "4H": {"score": Decimal(6.0), "recommendation": "STRONG_BUY"}
      }
      result = saver._transform_entry(symbol, data)

      assert result == {
          "timestamp": "2023-01-01T12:00:00Z",
          "symbol": "BTCUSD",
          "timeframes": {
              "1H": {"score": 5.5, "recommendation": "BUY"},
              "4H": {"score": 6.0, "recommendation": "STRONG_BUY"}
          }
      }

  def test_save_symbol_data_writes_to_file(self, saver, storage_path):
    symbol = "BTCUSD"
    data = {"1H": {"score": Decimal(5.5), "recommendation": "BUY"}}

    saver.save_symbol_data(symbol, data)

    file_path = storage_path / f"{symbol}.jsonl"
    assert file_path.exists()

    with open(file_path, "r") as f:
      line = json.loads(f.readline())
      assert line["symbol"] == symbol
      assert isinstance(line["timestamp"], str)
      assert line["timeframes"]["1H"]["score"] == 5.5

  def test_save_symbol_data_appends_to_existing_file(self, saver, storage_path):
    symbol = "BTCUSD"
    file_path = storage_path / f"{symbol}.jsonl"
    file_path.write_text("existing data\n")

    saver.save_symbol_data(symbol, {"1H": {"score": Decimal(5.5), "recommendation": "BUY"}})

    with open(file_path, "r") as f:
      lines = f.readlines()
      assert len(lines) == 2
      assert lines[0] == "existing data\n"
      assert json.loads(lines[1])["symbol"] == symbol

  @patch("builtins.open", mock_open())
  def test_save_symbol_data_handles_ioerror(self, saver, capsys):
    symbol = "BTCUSD"
    data = {"1H": {"score": Decimal(5.5), "recommendation": "BUY"}}

    with patch("builtins.open") as mock_file:
      mock_file.side_effect = IOError("Disk error")
      saver.save_symbol_data(symbol, data)

    captured = capsys.readouterr()
    assert f"Save error for {symbol}: Disk error" in captured.out

  def test_batch_save_calls_save_for_each_symbol(self, saver, mocker):
    mock_save = mocker.spy(AnalysisSaver, "save_symbol_data")
    all_data = {
      "BTCUSD": {"1H": {"score": Decimal(5.5), "recommendation": "BUY"}},
      "ETHUSD": {"4H": {"score": Decimal(6.0), "recommendation": "SELL"}}
    }

    saver.batch_save(all_data)

    assert mock_save.call_count == 2
    calls = [mocker.call(saver, "BTCUSD", all_data["BTCUSD"]),
             mocker.call(saver, "ETHUSD", all_data["ETHUSD"])]
    mock_save.assert_has_calls(calls, any_order=True)