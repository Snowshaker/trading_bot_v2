from src.core.api.tradingview_client.analysis_collector import AnalysisCollector
from src.core.api.tradingview_client.analysis_saver import AnalysisSaver
from pathlib import Path
import json
from datetime import datetime
import shutil
import pytest

@pytest.fixture
def test_dir():
    """Фикстура для создания и очистки тестовой директории."""
    test_dir = Path("test_collector_data")
    test_dir.mkdir(exist_ok=True)
    yield test_dir
    shutil.rmtree(test_dir, ignore_errors=True)

def create_test_data(saver: AnalysisSaver):
    """Вспомогательная функция для создания тестовых данных."""
    test_records = {
        "BTCUSDT": [
            {
                "timestamp": "2023-10-10T12:00:00Z",
                "timeframes": {"1m": {"score": 1, "recommendation": "BUY"}}
            },
            {
                "timestamp": "2023-10-10T12:01:00Z",
                "timeframes": {"1m": {"score": -1, "recommendation": "SELL"}}
            }
        ],
        "ETHUSDT": [
            {
                "timestamp": "2023-10-11T10:00:00Z",
                "timeframes": {"5m": {"score": 0, "recommendation": "NEUTRAL"}}
            }
        ]
    }
    for symbol, records in test_records.items():
        for record in records:
            saver.save_symbol_data(symbol, record["timeframes"])
    return test_records

def test_get_latest_for_symbol(test_dir):
    """Тест получения последней записи для символа."""

    saver = AnalysisSaver(test_dir)
    collector = AnalysisCollector(test_dir)
    test_records = create_test_data(saver)

    latest_btc = collector.get_latest_for_symbol("BTCUSDT")
    assert latest_btc is not None
    assert latest_btc["timeframes"]["1m"]["recommendation"] == "SELL"
    assert latest_btc["timeframes"]["1m"]["score"] == -1

    latest_eth = collector.get_latest_for_symbol("ETHUSDT")
    assert latest_eth is not None
    assert latest_eth["timeframes"]["5m"]["recommendation"] == "NEUTRAL"
    assert latest_eth["timeframes"]["5m"]["score"] == 0

def test_get_all_latest(test_dir):
    """Тест получения последних данных для всех символов."""

    saver = AnalysisSaver(test_dir)
    collector = AnalysisCollector(test_dir)
    create_test_data(saver)

    all_latest = collector.get_all_latest()
    assert "BTCUSDT" in all_latest
    assert "ETHUSDT" in all_latest
    assert all_latest["BTCUSDT"]["timeframes"]["1m"]["recommendation"] == "SELL"
    assert all_latest["ETHUSDT"]["timeframes"]["5m"]["score"] == 0

def test_get_history(test_dir):
    """Тест получения истории записей для символа."""

    saver = AnalysisSaver(test_dir)
    collector = AnalysisCollector(test_dir)
    create_test_data(saver)

    history_btc = collector.get_history("BTCUSDT", limit=2)
    assert len(history_btc) == 2
    assert history_btc[0]["timeframes"]["1m"]["recommendation"] == "BUY"
    assert history_btc[1]["timeframes"]["1m"]["recommendation"] == "SELL"

    history_eth = collector.get_history("ETHUSDT", limit=1)
    assert len(history_eth) == 1
    assert history_eth[0]["timeframes"]["5m"]["score"] == 0

def test_get_latest_for_symbol_missing(test_dir):
    """Тест обработки отсутствующего символа."""

    collector = AnalysisCollector(test_dir)
    missing = collector.get_latest_for_symbol("UNKNOWN")
    assert missing is None

def test_get_history_missing(test_dir):
    """Тест обработки отсутствующего файла."""

    collector = AnalysisCollector(test_dir)
    history = collector.get_history("UNKNOWN", limit=10)
    assert history == []