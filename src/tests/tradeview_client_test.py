# tests/core/api/tradingview_client/test_tradingview_client.py
import pytest
from unittest.mock import Mock, patch, call
from pathlib import Path
import json
import time
from datetime import datetime, UTC, timedelta
import logging
from decimal import Decimal

from src.core.api.tradingview_client.analysis_collector import AnalysisCollector
from src.core.api.tradingview_client.analysis_fetcher import TradingViewFetcher, RECOMMENDATION_SCORE_MAP
from src.core.api.tradingview_client.analysis_saver import AnalysisSaver, DecimalEncoder
from src.core.settings.config import SYMBOLS, TIMEFRAMES


# Fixtures
@pytest.fixture
def tmp_storage(tmp_path):
  path = tmp_path / "analysis_data"
  path.mkdir(parents=True, exist_ok=True)
  return path


@pytest.fixture
def sample_data():
  return {
    "1m": {"recommendation": "STRONG_BUY", "score": 2},
    "5m": {"recommendation": "SELL", "score": -1}
  }


# AnalysisCollector Tests
class TestAnalysisCollector:
  def test_get_latest_for_symbol(self, tmp_storage):
    collector = AnalysisCollector(tmp_storage)
    symbol = "BTCUSD"

    # Test missing file
    assert collector.get_latest_for_symbol(symbol) is None

    # Create test data
    data = [{"timestamp": "2023-01-01T12:00:00Z"}, {"timestamp": "2023-01-02T12:00:00Z"}]
    file_path = tmp_storage / f"{symbol}.jsonl"
    with open(file_path, "w") as f:
      for entry in data:
        f.write(json.dumps(entry) + "\n")

    assert collector.get_latest_for_symbol(symbol) == data[-1]

  def test_get_all_latest(self, tmp_storage):
    collector = AnalysisCollector(tmp_storage)

    # Create test data for 2 symbols
    for symbol in SYMBOLS[:2]:
      file_path = tmp_storage / f"{symbol}.jsonl"
      with open(file_path, "w") as f:
        f.write(json.dumps({symbol: "data"}) + "\n")

    result = collector.get_all_latest()
    assert len(result) == 2
    assert all(symbol in SYMBOLS for symbol in result.keys())

  def test_get_history(self, tmp_storage):
    collector = AnalysisCollector(tmp_storage)
    symbol = "ETHUSD"

    # Generate 150 entries
    test_data = [{"id": i} for i in range(150)]
    file_path = tmp_storage / f"{symbol}.jsonl"
    with open(file_path, "w") as f:
      for entry in test_data:
        f.write(json.dumps(entry) + "\n")

    assert len(collector.get_history(symbol)) == 100
    assert len(collector.get_history(symbol, 50)) == 50


# TradingViewFetcher Tests
class TestTradingViewFetcher:
  @patch('src.core.api.tradingview_client.analysis_fetcher.TA_Handler')
  def test_successful_fetch(self, mock_ta):
    mock_instance = mock_ta.return_value
    mock_instance.get_analysis.return_value.summary = {"RECOMMENDATION": "STRONG_BUY"}

    fetcher = TradingViewFetcher(rate_limit_delay=0)
    result = fetcher._fetch_single("BTCUSD", "1m")

    assert result == {
      "timeframe": "1m",
      "recommendation": "STRONG_BUY",
      "score": RECOMMENDATION_SCORE_MAP["STRONG_BUY"]
    }
    mock_ta.assert_called_with(
      symbol="BTCUSD",
      screener="crypto",
      exchange="BINANCE",
      interval="1m"
    )

  @patch('src.core.api.tradingview_client.analysis_fetcher.TA_Handler')
  def test_retry_logic(self, mock_ta, caplog):
    mock_instance = mock_ta.return_value
    mock_instance.get_analysis.side_effect = Exception("API Error")

    fetcher = TradingViewFetcher()
    result = fetcher._fetch_single("BTCUSD", "1m")

    assert result is None
    assert len(caplog.records) == 3
    assert "Failed to fetch" in caplog.text

  def test_rate_limiting(self):
    fetcher = TradingViewFetcher(rate_limit_delay=0.1)
    start_time = time.time()

    with patch.object(TradingViewFetcher, '_fetch_single', return_value={}):
      fetcher.fetch_all_data()

    elapsed = time.time() - start_time
    expected_delay = (len(TIMEFRAMES) * 0.1) + (len(SYMBOLS) * 0.1 * 2)
    assert elapsed >= expected_delay


# AnalysisSaver Tests
class TestAnalysisSaver:
  def test_transform_entry(self, sample_data):
    saver = AnalysisSaver()
    result = saver._transform_entry("BTCUSD", sample_data)

    assert result["symbol"] == "BTCUSD"
    assert "timestamp" in result
    assert list(result["timeframes"].keys()) == ["1m", "5m"]

  def test_save_symbol_data(self, tmp_storage, sample_data):
    saver = AnalysisSaver(tmp_storage)
    saver.save_symbol_data("BTCUSD", sample_data)

    target_file = tmp_storage / "BTCUSD.jsonl"
    assert target_file.exists()

    with open(target_file) as f:
      content = json.loads(f.read())
      assert content["symbol"] == "BTCUSD"

  def test_batch_save(self, tmp_storage, sample_data):
    saver = AnalysisSaver(tmp_storage)
    test_data = {"BTCUSD": sample_data, "ETHUSD": sample_data}

    saver.batch_save(test_data)

    assert (tmp_storage / "BTCUSD.jsonl").exists()
    assert (tmp_storage / "ETHUSD.jsonl").exists()


# Integration Test
def test_full_integration(tmp_storage, sample_data):
  fetcher = TradingViewFetcher(rate_limit_delay=0)
  saver = AnalysisSaver(tmp_storage)
  collector = AnalysisCollector(tmp_storage)

  with patch.object(TradingViewFetcher, 'fetch_all_data', return_value={"BTCUSD": sample_data}):
    data = fetcher.fetch_all_data()
    saver.batch_save(data)

    assert collector.get_latest_for_symbol("BTCUSD")["symbol"] == "BTCUSD"
    assert len(collector.get_history("BTCUSD")) == 1


# Edge Cases
def test_empty_symbols(tmp_storage):
  collector = AnalysisCollector(tmp_storage)
  assert collector.get_all_latest() == {}


def test_corrupted_file(tmp_storage):
  symbol = "BTCUSD"
  corrupted_data = '{"invalid": json}'
  file_path = tmp_storage / f"{symbol}.jsonl"
  with open(file_path, "w") as f:
    f.write(corrupted_data)

  collector = AnalysisCollector(tmp_storage)
  assert collector.get_latest_for_symbol(symbol) is None


def test_decimal_encoder():
  encoder = DecimalEncoder()
  assert encoder.default(Decimal("10.5")) == 10.5
  with pytest.raises(TypeError):
    encoder.default("invalid")