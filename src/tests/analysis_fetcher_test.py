# tests/core/api/tradingview_client/test_analysis_fetcher.py
import pytest
from unittest.mock import Mock
import logging
from tradingview_ta import TA_Handler
from src.core.api.tradingview_client.analysis_fetcher import TradingViewFetcher


@pytest.fixture
def fetcher():
  return TradingViewFetcher(rate_limit_delay=0)


@pytest.fixture
def mock_ta_handler(mocker):
  return mocker.patch('src.core.api.tradingview_client.analysis_fetcher.TA_Handler')


@pytest.fixture
def mock_config(monkeypatch):
  monkeypatch.setattr('src.core.api.tradingview_client.analysis_fetcher.SYMBOLS', ['BTCUSD', 'ETHUSD'])
  monkeypatch.setattr('src.core.api.tradingview_client.analysis_fetcher.TIMEFRAMES', ['1H', '4H'])
  monkeypatch.setattr(
    'src.core.api.tradingview_client.analysis_fetcher.RECOMMENDATION_SCORE_MAP',
    {'STRONG_BUY': 2, 'BUY': 1, 'NEUTRAL': 0}
  )


def test_fetch_single_success(fetcher, mock_ta_handler, mock_config):
  mock_instance = Mock()
  mock_instance.get_analysis.return_value.summary = {"RECOMMENDATION": "STRONG_BUY"}
  mock_ta_handler.return_value = mock_instance

  result = fetcher._fetch_single("BTCUSD", "1H")

  assert result == {
    "timeframe": "1H",
    "recommendation": "STRONG_BUY",
    "score": 2
  }
  mock_ta_handler.assert_called_with(
    symbol="BTCUSD",
    screener="crypto",
    exchange="BINANCE",
    interval="1H"
  )


def test_fetch_single_default_recommendation(fetcher, mock_ta_handler, mock_config):
  mock_instance = Mock()
  mock_instance.get_analysis.return_value.summary = {}
  mock_ta_handler.return_value = mock_instance

  result = fetcher._fetch_single("BTCUSD", "1H")

  assert result["recommendation"] == "NEUTRAL"
  assert result["score"] == 0


def test_fetch_all_data_partial_failure(fetcher, mock_ta_handler, mock_config, caplog):
  mock_instance = Mock()
  mock_instance.get_analysis.side_effect = Exception("Error")
  mock_ta_handler.return_value = mock_instance

  result = fetcher.fetch_all_data()

  assert 'BTCUSD' not in result
  assert 'ETHUSD' not in result
  assert "No data for BTCUSD" in caplog.text
  assert "No data for ETHUSD" in caplog.text