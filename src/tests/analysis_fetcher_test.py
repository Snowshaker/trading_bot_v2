from src.core.api.tradingview_client.analysis_fetcher import TradingViewFetcher
from src.core.settings.config import SYMBOLS, TIMEFRAMES
import time
import pytest
from unittest.mock import patch, MagicMock

@pytest.fixture
def fetcher():
    """Фикстура для создания TradingViewFetcher с уменьшенной задержкой."""
    return TradingViewFetcher(rate_limit_delay=0.1)  # Уменьшаем задержку для тестов

@pytest.fixture
def mock_ta_handler():
    """Фикстура для мокирования TA_Handler."""
    with patch("src.core.api.tradingview_client.analysis_fetcher.TA_Handler") as mock:
        yield mock

def mock_analysis_result(recommendation="BUY", score=1):
    """Вспомогательная функция для создания мокированных результатов анализа."""
    mock_analysis = MagicMock()
    mock_analysis.summary = {"RECOMMENDATION": recommendation}
    mock_analysis.get_analysis.return_value = mock_analysis
    return mock_analysis

def test_fetch_single_success(fetcher, mock_ta_handler):
    """Тест успешного получения данных для одного символа и таймфрейма."""

    mock_ta_handler.return_value = mock_analysis_result()
    result = fetcher._fetch_single("BTCUSDT", "1m")
    assert result == {"timeframe": "1m", "recommendation": "BUY", "score": 1}

def test_fetch_single_failure(fetcher, mock_ta_handler, caplog):
    """Тест обработки ошибки при получении данных."""

    mock_ta_handler.side_effect = Exception("API Error")
    result = fetcher._fetch_single("BTCUSDT", "1m")
    assert result is None
    assert "Failed to fetch BTCUSDT 1m" in caplog.text

def test_fetch_all_data(fetcher, mock_ta_handler):
    """Тест получения данных для всех символов и таймфреймов."""

    mock_ta_handler.return_value = mock_analysis_result()
    data = fetcher.fetch_all_data()

    assert len(data) == len(SYMBOLS)
    for symbol, timeframes_data in data.items():
        assert len(timeframes_data) == len(TIMEFRAMES)
        for tf, analysis in timeframes_data.items():
            assert analysis["recommendation"] == "BUY"
            assert analysis["score"] == 1

def test_fetch_all_data_partial_failure(fetcher, mock_ta_handler, caplog):
    """Тест обработки частичных сбоев при получении данных."""

    mock_ta_handler.side_effect = [
        mock_analysis_result(),  # First call succeeds
        Exception("API Error"),  # Second call fails
        mock_analysis_result(recommendation="SELL", score=-1),  # Third call succeeds
        mock_analysis_result()
    ]

    data = fetcher.fetch_all_data()
    assert len(data) == len(SYMBOLS)
    assert "BTCUSDT" in data
    assert "1m" in data["BTCUSDT"]
    assert "5m" in data["BTCUSDT"]
    assert data["BTCUSDT"]["1m"]["recommendation"] == "BUY"
    assert data["BTCUSDT"]["5m"]["recommendation"] == "SELL"
    assert "Failed to fetch BTCUSDT 5m" in caplog.text