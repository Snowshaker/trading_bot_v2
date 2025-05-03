from unittest.mock import patch

from src.core.api.tradingview_client.analysis_saver import AnalysisSaver
from pathlib import Path
import json
from datetime import datetime
import shutil
import pytest

@pytest.fixture
def test_dir():
    """Фикстура для создания и очистки тестовой директории."""
    test_dir = Path("test_saver_data")
    test_dir.mkdir(exist_ok=True)
    yield test_dir
    shutil.rmtree(test_dir, ignore_errors=True)

def test_save_symbol_data(test_dir):
    """Тест сохранения данных для одного символа."""

    saver = AnalysisSaver(test_dir)
    test_data = {"1m": {"score": 1, "recommendation": "BUY"}}
    saver.save_symbol_data("BTCUSDT", test_data)

    file_path = test_dir / "BTCUSDT.jsonl"
    assert file_path.exists()
    with open(file_path, "r") as f:
        content = json.loads(f.readline())
        assert content["symbol"] == "BTCUSDT"
        assert "timestamp" in content
        assert content["timeframes"]["1m"]["score"] == 1
        assert content["timeframes"]["1m"]["recommendation"] == "BUY"
        datetime.fromisoformat(content["timestamp"].replace("Z", ""))  # Check timestamp format

def test_batch_save(test_dir):
    """Тест пакетного сохранения данных для нескольких символов."""

    saver = AnalysisSaver(test_dir)
    test_data = {
        "BTCUSDT": {"1m": {"score": 1, "recommendation": "BUY"}},
        "ETHUSDT": {"5m": {"score": -1, "recommendation": "SELL"}}
    }
    saver.batch_save(test_data)

    btc_path = test_dir / "BTCUSDT.jsonl"
    eth_path = test_dir / "ETHUSDT.jsonl"

    assert btc_path.exists()
    assert eth_path.exists()

    with open(btc_path, "r") as f:
        btc_content = json.loads(f.readline())
        assert btc_content["symbol"] == "BTCUSDT"
        assert btc_content["timeframes"]["1m"]["score"] == 1

    with open(eth_path, "r") as f:
        eth_content = json.loads(f.readline())
        assert eth_content["symbol"] == "ETHUSDT"
        assert eth_content["timeframes"]["5m"]["recommendation"] == "SELL"

def test_save_error_handling(test_dir, capsys):
    """Тест обработки ошибок при сохранении данных."""

    saver = AnalysisSaver(test_dir)
    # Мокируем запись в файл, чтобы вызвать ошибку
    with patch("builtins.open", side_effect=IOError("Disk full")):
        saver.save_symbol_data("BTCUSDT", {"1m": {"score": 1, "recommendation": "BUY"}})
    captured = capsys.readouterr()
    assert "Save error for BTCUSDT: Disk full" in captured.out