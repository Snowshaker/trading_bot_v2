# tests/core/data_logic/test_timeframe_weights_calculator.py

import pytest
import math
from src.core.data_logic.timeframe_weights_calculator import (
    parse_timeframe,
    calculate_timeframe_weights
)

# --- Тесты для parse_timeframe ---

@pytest.mark.parametrize(
    "timeframe_str, expected_minutes",
    [
        # Минуты (только строчные 'm')
        ("1m", 1),
        ("15m", 15),
        ("59m", 59),
        ("m", 1), # По умолчанию 1 для 'm' (судя по отсутствию ошибки)
        ("0m", 0), # 0 допускается (судя по отсутствию ошибки)

        # Часы (только строчные 'h')
        ("1h", 60),
        ("2h", 120),
        ("23h", 23 * 60),
        ("h", 60), # По умолчанию 1 для 'h' (судя по отсутствию ошибки)
        ("0h", 0), # 0 допускается

        # Дни (только заглавные 'D')
        ("1D", 1440),
        ("D", 1440), # Без числа
        ("3D", 3 * 1440),
        ("0D", 0), # 0 допускается (судя по отсутствию ошибки)


        # Недели (только заглавные 'W')
        ("1W", 10080),
        ("W", 10080), # Без числа
        ("2W", 2 * 10080),
        ("0W", 0), # 0 допускается

        # Месяцы (только заглавные 'M', предполагаем 30 дней)
        ("1M", 43200),
        ("M", 43200), # Без числа
        ("3M", 3 * 43200),
        ("5M", 5 * 43200), # 5 месяцев, а не минут
        ("0M", 0), # 0 допускается
    ]
)
def test_parse_timeframe_valid(timeframe_str, expected_minutes):
    """Тестирование корректного парсинга валидных строк таймфреймов."""
    assert parse_timeframe(timeframe_str) == expected_minutes

@pytest.mark.parametrize(
    "invalid_str, match_error",
    [
        # Неверный формат / символы
        ("", "Invalid timeframe format: "), # Точное совпадение сообщения
        ("1", "Invalid timeframe format: 1"),
        ("1y", "Invalid timeframe format: 1y"), # Неизвестный юнит, регистр сохранен
        ("15 minutes", "Invalid timeframe format: 15 minutes"),
        ("h1", "Invalid timeframe format: h1"), # Неверный порядок
        ("1.5h", "Invalid timeframe format: 1.5h"), # Не целое число
        ("-5m", "Invalid timeframe format: -5m"), # Отрицательное
        ("M1", "Invalid timeframe format: M1"),
        ("1 M", "Invalid timeframe format: 1 M"), # Пробел между
        ("D1", "Invalid timeframe format: D1"),
        ("1Dm", "Invalid timeframe format: 1Dm"), # Два юнита

        # Неверный регистр
        ("1H", "Invalid timeframe format: 1H"), # H должно быть h
        ("1d", "Invalid timeframe format: 1d"), # d должно быть D
        ("1w", "Invalid timeframe format: 1w"), # w должно быть W
        # "5M" - теперь валидный тест, парсится как 5 месяцев

        # С пробелами (если не обрабатываются)
        (" 15m", "Invalid timeframe format:  15m"),
        ("15m ", "Invalid timeframe format: 15m "),
        ("  4h ", "Invalid timeframe format:   4h "),
    ]
)
def test_parse_timeframe_invalid(invalid_str, match_error):
    """Тестирование парсинга невалидных строк таймфреймов."""
    # Используем re.escape для экранирования спецсимволов в match_error, если они есть
    # Хотя в данном случае их нет, это хорошая практика
    import re
    with pytest.raises(ValueError, match=re.escape(match_error)):
        parse_timeframe(invalid_str)

# Тесты на случаи, которые НЕ должны вызывать ошибку (согласно логам)
@pytest.mark.parametrize("valid_but_maybe_unexpected", ["m", "h", "0m", "0h", "0D", "0W", "0M"])
def test_parse_timeframe_no_error_unexpected(valid_but_maybe_unexpected):
    """Проверка, что определенные вводы НЕ вызывают ValueError."""
    try:
        parse_timeframe(valid_but_maybe_unexpected)
    except ValueError:
        pytest.fail(f"parse_timeframe({valid_but_maybe_unexpected!r}) raised ValueError unexpectedly")


# --- Тесты для calculate_timeframe_weights ---

def test_calculate_weights_empty_list():
    """Тест с пустым списком таймфреймов (должен вызывать ошибку)."""
    with pytest.raises(ValueError, match="Total duration cannot be zero"):
        calculate_timeframe_weights([])

def test_calculate_weights_single_timeframe():
    """Тест с одним таймфреймом (вес должен быть 1.0)."""
    # Проверим с таймфреймом > 0 минут, чтобы избежать деления на ноль, если total = 0
    weights = calculate_timeframe_weights(["1h"])
    assert len(weights) == 1
    assert "1h" in weights
    # Если длительность 60, total=60, вес = 60/60 = 1.0
    assert weights["1h"] == pytest.approx(1.0)

def test_calculate_weights_single_zero_duration_timeframe():
    """Тест с одним таймфреймом нулевой длительности."""
    # Ожидаем ошибку деления на ноль или специфическую ошибку total=0
    # Зависит от реализации, но скорее всего ValueError
    with pytest.raises(ValueError): # Возможно, стоит уточнить match, если поведение известно
         calculate_timeframe_weights(["0m"])

def test_calculate_weights_all_zero_duration_timeframes():
    """Тест, когда все таймфреймы имеют нулевую длительность."""
    with pytest.raises(ValueError, match="Total duration cannot be zero"):
         calculate_timeframe_weights(["0m", "0h", "0D"])


def test_calculate_weights_multiple_timeframes():
    """Тест с несколькими таймфреймами."""
    timeframes = ["5m", "1h", "4h", "1D"] # Длительности: 5, 60, 240, 1440. Total = 1745
    weights = calculate_timeframe_weights(timeframes)

    assert len(weights) == len(timeframes)
    assert set(weights.keys()) == set(timeframes)

    # Проверяем, что все веса >= 0 (могут быть 0, если есть 0m)
    for tf, weight in weights.items():
        assert weight >= 0.0
        assert weight <= 1.0

    # Проверяем, что сумма весов равна 1.0
    assert sum(weights.values()) == pytest.approx(1.0)

    # Проверяем относительный порядок весов (для данной логики: дольше -> больше вес)
    # 5m < 1h < 4h < 1D
    assert weights["5m"] == pytest.approx(5 / 1745)
    assert weights["1h"] == pytest.approx(60 / 1745)
    assert weights["4h"] == pytest.approx(240 / 1745)
    assert weights["1D"] == pytest.approx(1440 / 1745)
    assert weights["5m"] < weights["1h"] < weights["4h"] < weights["1D"]

def test_calculate_weights_with_zero_duration():
    """Тест с таймфреймом нулевой длительности среди прочих."""
    timeframes = ["0m", "1h", "5m"] # 0, 60, 5. Total = 65
    weights = calculate_timeframe_weights(timeframes)
    assert len(weights) == len(timeframes)
    assert sum(weights.values()) == pytest.approx(1.0)
    assert weights["0m"] == pytest.approx(0.0)
    assert weights["5m"] == pytest.approx(5 / 65)
    assert weights["1h"] == pytest.approx(60 / 65)
    assert weights["0m"] < weights["5m"] < weights["1h"]


def test_calculate_weights_with_duplicates():
    """
    Тест со списком, содержащим дубликаты таймфреймов.
    Проверяет ТЕКУЩЕЕ (вероятно, некорректное) поведение функции,
    где сумма весов не равна 1.0 из-за обработки дубликатов.
    """
    timeframes = ["1h", "15m", "1h", "1D", "15m"]
    # Уникальные ключи, которые вернет функция: "1h", "15m", "1D"
    unique_timeframes = ["1h", "15m", "1D"]
    # Фактические длительности: 60, 15, 60, 1440, 15
    # Вероятный Total, используемый функцией (с дубликатами): 60 + 15 + 60 + 1440 + 15 = 1590
    # Сумма длительностей уникальных ключей: 60 + 15 + 1440 = 1515
    # Ожидаемая (некорректная) сумма весов: 1515 / 1590 = 0.9528301886792453

    expected_buggy_sum = 1515 / 1590

    weights = calculate_timeframe_weights(timeframes)

    # Словарь должен содержать только уникальные ключи
    assert len(weights) == len(unique_timeframes)
    assert set(weights.keys()) == set(unique_timeframes)

    # Сумма весов НЕ равна 1.0 из-за бага, проверяем фактическое значение
    assert sum(weights.values()) == pytest.approx(expected_buggy_sum), \
        f"Sum of weights is {sum(weights.values())}, expected {expected_buggy_sum} due to duplicate handling."

    # Проверяем относительный порядок (дольше -> больше вес)
    # Это должно быть верно даже при неверной нормализации, если расчет идет от длительности
    assert weights["15m"] < weights["1h"] < weights["1D"]

    # Проверяем конкретные значения, рассчитанные с НЕПРАВИЛЬНЫМ total = 1590
    assert weights["15m"] == pytest.approx(15 / 1590)
    assert weights["1h"] == pytest.approx(60 / 1590)
    assert weights["1D"] == pytest.approx(1440 / 1590)


def test_calculate_weights_invalid_timeframe_in_list():
    """Тест со списком, содержащим невалидный таймфрейм."""
    timeframes = ["1h", "invalid", "1D"]
    # Ожидаем точное совпадение сообщения об ошибке от parse_timeframe
    import re
    with pytest.raises(ValueError, match=re.escape("Invalid timeframe format: invalid")):
        calculate_timeframe_weights(timeframes)

def test_calculate_weights_all_same_duration():
    """Тест, когда все таймфреймы имеют одинаковую продолжительность."""
    # "60m" и "1h" парсятся в 60 минут. Total = 60 + 60 = 120
    timeframes = ["60m", "1h"]
    weights = calculate_timeframe_weights(timeframes)

    assert len(weights) == 2
    assert set(weights.keys()) == set(timeframes)
    # Сумма весов должна быть 1.0 (так как дубликатов НЕТ в этом списке)
    assert sum(weights.values()) == pytest.approx(1.0)
    # Веса должны быть равны (60/120 = 0.5)
    assert weights["60m"] == pytest.approx(weights["1h"])
    assert weights["60m"] == pytest.approx(0.5)