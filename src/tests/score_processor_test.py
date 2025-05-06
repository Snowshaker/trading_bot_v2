# tests/core/data_logic/test_score_processor.py

import pytest
from decimal import Decimal # Хотя Decimal не используется напрямую, оставим на всякий случай
from src.core.data_logic.score_processor import ScoreProcessor

# --- Константы для моков и тестов ---

# Используем значения, отличные от возможных реальных, чтобы убедиться,
# что тесты зависят от моков, а не от реального конфига.
MOCK_RECOMMENDATION_SCORE_MAP = {
    "STRONG_BUY": 2.0,
    "BUY": 1.0,
    "NEUTRAL": 0.0,
    "SELL": -1.0,
    "STRONG_SELL": -2.0,
}
MOCK_BUY_THRESHOLD = 0.75
MOCK_SELL_THRESHOLD = -0.75

# --- Фикстуры ---

@pytest.fixture
def mock_config(monkeypatch):
    """Мокает константы конфигурации."""
    monkeypatch.setattr(
        "src.core.data_logic.score_processor.RECOMMENDATION_SCORE_MAP",
        MOCK_RECOMMENDATION_SCORE_MAP
    )
    monkeypatch.setattr(
        "src.core.data_logic.score_processor.BUY_THRESHOLD",
        MOCK_BUY_THRESHOLD
    )
    monkeypatch.setattr(
        "src.core.data_logic.score_processor.SELL_THRESHOLD",
        MOCK_SELL_THRESHOLD
    )

@pytest.fixture
def valid_weights():
    """Предоставляет валидный набор весов."""
    return {"1m": 0.1, "5m": 0.2, "15m": 0.3, "1h": 0.4}

@pytest.fixture
def processor(valid_weights, mock_config):
    """Создает экземпляр ScoreProcessor с валидными весами и моками."""
    # mock_config фикстура применяется автоматически перед созданием processor
    return ScoreProcessor(timeframe_weights=valid_weights)

# --- Тесты инициализации и валидации ---

def test_init_success(valid_weights, mock_config):
    """Тест успешной инициализации с валидными весами."""
    processor = ScoreProcessor(valid_weights)
    assert processor.timeframe_weights == valid_weights

def test_init_invalid_weights_sum_low(mock_config):
    """Тест ошибки инициализации, если сумма весов < 0.99."""
    invalid_weights = {"1m": 0.5, "5m": 0.4} # Сумма 0.9
    with pytest.raises(ValueError, match="Invalid weights sum: 0.90. Must sum to 1.0"):
        ScoreProcessor(invalid_weights)

def test_init_invalid_weights_sum_high(mock_config):
    """Тест ошибки инициализации, если сумма весов > 1.01."""
    invalid_weights = {"1m": 0.6, "5m": 0.5} # Сумма 1.1
    with pytest.raises(ValueError, match="Invalid weights sum: 1.10. Must sum to 1.0"):
        ScoreProcessor(invalid_weights)

def test_init_empty_weights(mock_config):
    """Тест ошибки инициализации с пустым словарем весов."""
    invalid_weights = {} # Сумма 0.0
    with pytest.raises(ValueError, match="Invalid weights sum: 0.00. Must sum to 1.0"):
        ScoreProcessor(invalid_weights)

def test_init_weights_almost_one(mock_config):
    """Тест успешной инициализации с весами, близкими к 1.0 (в пределах допуска)."""
    weights_slightly_low = {"1m": 0.5, "5m": 0.491} # Сумма 0.991
    processor_low = ScoreProcessor(weights_slightly_low)
    assert processor_low.timeframe_weights == weights_slightly_low

    weights_slightly_high = {"1m": 0.5, "5m": 0.509} # Сумма 1.009
    processor_high = ScoreProcessor(weights_slightly_high)
    assert processor_high.timeframe_weights == weights_slightly_high

# --- Тесты calculate_score ---

def test_calculate_score_basic(processor, valid_weights):
    """Тест базового расчета скоринга."""
    analysis_data = {
        "1m": {"recommendation": "BUY"},         # 1.0 * 0.1 = 0.1
        "5m": {"recommendation": "STRONG_BUY"},  # 2.0 * 0.2 = 0.4
        "15m": {"recommendation": "SELL"},        # -1.0 * 0.3 = -0.3
        "1h": {"recommendation": "NEUTRAL"},     # 0.0 * 0.4 = 0.0
    }
    expected_score = 0.1 + 0.4 - 0.3 + 0.0 # = 0.2
    assert processor.calculate_score(analysis_data) == pytest.approx(expected_score)

def test_calculate_score_missing_timeframe_in_weights(processor):
    """Тест расчета, когда таймфрейм из данных отсутствует в весах."""
    analysis_data = {
        "1m": {"recommendation": "BUY"},         # 1.0 * 0.1 = 0.1
        "unknown_tf": {"recommendation": "STRONG_BUY"}, # 2.0 * 0.0 = 0.0 (вес 0)
    }
    expected_score = 0.1
    assert processor.calculate_score(analysis_data) == pytest.approx(expected_score)

def test_calculate_score_missing_recommendation_key(processor):
    """Тест расчета, когда ключ 'recommendation' отсутствует (должен быть NEUTRAL)."""
    analysis_data = {
        "1m": {"score": 5}, # Нет 'recommendation', будет NEUTRAL
        "5m": {"recommendation": "BUY"}, # 1.0 * 0.2 = 0.2
    }
    # "1m": NEUTRAL -> 0.0 * 0.1 = 0.0
    expected_score = 0.0 + 0.2 # = 0.2
    assert processor.calculate_score(analysis_data) == pytest.approx(expected_score)

def test_calculate_score_unknown_recommendation_value(processor):
    """Тест расчета, когда значение 'recommendation' неизвестно (должно быть 0.0)."""
    analysis_data = {
        "1m": {"recommendation": "HOLD_TIGHT"}, # Неизвестно -> 0.0 * 0.1 = 0.0
        "5m": {"recommendation": "SELL"},       # -1.0 * 0.2 = -0.2
    }
    expected_score = 0.0 - 0.2 # = -0.2
    assert processor.calculate_score(analysis_data) == pytest.approx(expected_score)

def test_calculate_score_case_insensitive_recommendation(processor):
    """Тест расчета с рекомендациями в разном регистре."""
    analysis_data = {
        "1m": {"recommendation": "buy"},       # 1.0 * 0.1 = 0.1
        "5m": {"recommendation": "Strong_Sell"}, # -2.0 * 0.2 = -0.4
    }
    expected_score = 0.1 - 0.4 # = -0.3
    assert processor.calculate_score(analysis_data) == pytest.approx(expected_score)

def test_calculate_score_empty_analysis_data(processor):
    """Тест расчета с пустыми данными анализа."""
    analysis_data = {}
    expected_score = 0.0
    assert processor.calculate_score(analysis_data) == pytest.approx(expected_score)

# --- Тесты get_signal ---

@pytest.mark.parametrize(
    "score, expected_signal",
    [
        (MOCK_BUY_THRESHOLD + 0.1, "BUY"),       # Выше порога BUY
        (MOCK_BUY_THRESHOLD, "BUY"),          # На пороге BUY
        (0.0, "NEUTRAL"),                         # Нейтральный
        ((MOCK_BUY_THRESHOLD + MOCK_SELL_THRESHOLD) / 2, "NEUTRAL"), # Между порогами
        (MOCK_SELL_THRESHOLD, "SELL"),         # На пороге SELL
        (MOCK_SELL_THRESHOLD - 0.1, "SELL"),      # Ниже порога SELL
    ]
)
def test_get_signal(processor, score, expected_signal):
    """Тест определения сигнала для разных скорингов."""
    assert processor.get_signal(score) == expected_signal

# --- Тесты process ---

def test_process_buy_signal(processor, valid_weights):
    """Тест полного цикла обработки, результат - BUY."""
    analysis_data = {
        "1m": {"recommendation": "STRONG_BUY"}, # 2.0 * 0.1 = 0.2
        "5m": {"recommendation": "BUY"},        # 1.0 * 0.2 = 0.2
        "15m": {"recommendation": "BUY"},       # 1.0 * 0.3 = 0.3
        "1h": {"recommendation": "NEUTRAL"},    # 0.0 * 0.4 = 0.0
    }
    # Total score = 0.2 + 0.2 + 0.3 + 0.0 = 0.7
    # MOCK_BUY_THRESHOLD = 0.75, так что ожидаем NEUTRAL (поправим тест)
    # Обновим данные для получения BUY
    analysis_data = {
        "1m": {"recommendation": "STRONG_BUY"}, # 2.0 * 0.1 = 0.2
        "5m": {"recommendation": "STRONG_BUY"}, # 2.0 * 0.2 = 0.4
        "15m": {"recommendation": "BUY"},       # 1.0 * 0.3 = 0.3
        "1h": {"recommendation": "NEUTRAL"},    # 0.0 * 0.4 = 0.0
    }
     # Total score = 0.2 + 0.4 + 0.3 + 0.0 = 0.9
    expected_score = 0.9
    expected_signal = "BUY" # 0.9 >= 0.75

    result = processor.process(analysis_data)

    assert result["score"] == pytest.approx(expected_score)
    assert result["signal"] == expected_signal
    assert "details" in result
    assert len(result["details"]) == len(analysis_data)

    details_1m = result["details"]["1m"]
    assert details_1m["recommendation"] == "STRONG_BUY"
    assert details_1m["weight"] == valid_weights["1m"]
    assert details_1m["contribution"] == pytest.approx(2.0 * 0.1)

    details_1h = result["details"]["1h"]
    assert details_1h["recommendation"] == "NEUTRAL"
    assert details_1h["weight"] == valid_weights["1h"]
    assert details_1h["contribution"] == pytest.approx(0.0 * 0.4)

    # Проверяем округление в details
    analysis_data_rounding = { "15m": {"recommendation": "BUY"}} # 1.0 * 0.3 = 0.3
    result_rounding = processor.process(analysis_data_rounding)
    assert result_rounding["details"]["15m"]["contribution"] == 0.3000

    # Проверим округление итогового score (до 4 знаков)
    tricky_weights = {"a": 1/3, "b": 1/3, "c": 1/3} # Сумма близка к 1
    processor_tricky = ScoreProcessor(tricky_weights)
    tricky_data = {
        "a": {"recommendation": "BUY"}, # 1.0 * 1/3
        "b": {"recommendation": "BUY"}, # 1.0 * 1/3
        "c": {"recommendation": "BUY"}, # 1.0 * 1/3
    }
    # Итоговый скор ~1.0
    result_tricky = processor_tricky.process(tricky_data)
    # Ожидаем округление 1.0 * (1/3 + 1/3 + 1/3) до 4 знаков
    assert result_tricky["score"] == pytest.approx(1.0000) # Должно быть округлено


def test_process_sell_signal(processor, valid_weights):
    """Тест полного цикла обработки, результат - SELL."""
    analysis_data = {
        "1m": {"recommendation": "STRONG_SELL"},# -2.0 * 0.1 = -0.2
        "5m": {"recommendation": "SELL"},       # -1.0 * 0.2 = -0.2
        "15m": {"recommendation": "SELL"},      # -1.0 * 0.3 = -0.3
        "1h": {"recommendation": "STRONG_SELL"},# -2.0 * 0.4 = -0.8
    }
    # Total score = -0.2 - 0.2 - 0.3 - 0.8 = -1.5
    expected_score = -1.5
    expected_signal = "SELL" # -1.5 <= -0.75

    result = processor.process(analysis_data)

    assert result["score"] == pytest.approx(expected_score)
    assert result["signal"] == expected_signal
    assert "details" in result
    assert len(result["details"]) == len(analysis_data)

    details_1h = result["details"]["1h"]
    assert details_1h["recommendation"] == "STRONG_SELL"
    assert details_1h["weight"] == valid_weights["1h"]
    assert details_1h["contribution"] == pytest.approx(-2.0 * 0.4)

def test_process_neutral_signal(processor, valid_weights):
    """Тест полного цикла обработки, результат - NEUTRAL."""
    analysis_data = {
        "1m": {"recommendation": "BUY"},         # 1.0 * 0.1 = 0.1
        "5m": {"recommendation": "SELL"},        # -1.0 * 0.2 = -0.2
        "15m": {"recommendation": "NEUTRAL"},     # 0.0 * 0.3 = 0.0
        "1h": {"recommendation": "NEUTRAL"},     # 0.0 * 0.4 = 0.0
    }
    # Total score = 0.1 - 0.2 + 0.0 + 0.0 = -0.1
    expected_score = -0.1
    expected_signal = "NEUTRAL" # -0.75 < -0.1 < 0.75

    result = processor.process(analysis_data)

    assert result["score"] == pytest.approx(expected_score)
    assert result["signal"] == expected_signal
    assert "details" in result
    assert len(result["details"]) == len(analysis_data)

    details_5m = result["details"]["5m"]
    assert details_5m["recommendation"] == "SELL"
    assert details_5m["weight"] == valid_weights["5m"]
    assert details_5m["contribution"] == pytest.approx(-1.0 * 0.2)

def test_process_with_missing_and_unknown(processor, valid_weights):
    """Тест process с отсутствующими и неизвестными рекомендациями/таймфреймами."""
    analysis_data = {
        "1m": {"recommendation": "BUY"},         # 1.0 * 0.1 = 0.1
        "5m": {},                                # NEUTRAL -> 0.0 * 0.2 = 0.0
        "15m": {"recommendation": "HOLD"},       # Unknown -> 0.0 * 0.3 = 0.0
        "unknown_tf": {"recommendation": "SELL"},# Weight 0.0 -> -1.0 * 0.0 = 0.0
    }
    # Total score = 0.1 + 0.0 + 0.0 + 0.0 = 0.1
    expected_score = 0.1
    expected_signal = "NEUTRAL" # -0.75 < 0.1 < 0.75

    result = processor.process(analysis_data)

    assert result["score"] == pytest.approx(expected_score)
    assert result["signal"] == expected_signal
    assert "details" in result
    # Должны быть записи для всех ключей из analysis_data
    assert len(result["details"]) == len(analysis_data)

    # Проверяем детали для обработанных по умолчанию случаев
    details_5m = result["details"]["5m"]
    assert details_5m["recommendation"] == "NEUTRAL" # По умолчанию
    assert details_5m["weight"] == valid_weights["5m"]
    assert details_5m["contribution"] == pytest.approx(0.0)

    details_15m = result["details"]["15m"]
    assert details_15m["recommendation"] == "HOLD" # Как передали, но score 0
    assert details_15m["weight"] == valid_weights["15m"]
    assert details_15m["contribution"] == pytest.approx(0.0) # Score 0 для HOLD

    details_unknown = result["details"]["unknown_tf"]
    assert details_unknown["recommendation"] == "SELL"
    assert details_unknown["weight"] == 0.0 # Вес 0.0
    assert details_unknown["contribution"] == pytest.approx(0.0) # Вклад 0.0

def test_process_empty_analysis_data(processor):
    """Тест process с пустыми входными данными."""
    analysis_data = {}
    expected_score = 0.0
    expected_signal = "NEUTRAL"

    result = processor.process(analysis_data)

    assert result["score"] == pytest.approx(expected_score)
    assert result["signal"] == expected_signal
    assert "details" in result
    assert result["details"] == {}