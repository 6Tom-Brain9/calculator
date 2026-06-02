"""
Вспомогательные функции
"""

from typing import Dict, Any


def find_category_by_engine(engine_cc: float, categories: list) -> Dict[str, Any]:
    """
    Находит категорию по объему двигателя
    
    Args:
        engine_cc: объем двигателя в куб.см
        categories: список категорий с полями min_cm3 и max_cm3
    
    Returns:
        категория или None
    """
    for cat in categories:
        min_cm3 = cat.get('min_cm3', 0)
        max_cm3 = cat.get('max_cm3')
        
        if max_cm3 is None:
            if engine_cc >= min_cm3:
                return cat
        else:
            if min_cm3 <= engine_cc <= max_cm3:
                return cat
    
    return None


def find_bracket_by_value(value_euro: float, brackets: list) -> Dict[str, Any]:
    """
    Находит ценовой диапазон по стоимости в евро
    
    Args:
        value_euro: стоимость в евро
        brackets: список диапазонов с полем max_euro
    
    Returns:
        диапазон или последний, если не найден
    """
    for bracket in brackets:
        max_euro = bracket.get('max_euro')
        if max_euro is None:
            return bracket
        if value_euro <= max_euro:
            return bracket
    
    return brackets[-1] if brackets else None


def format_currency(value: float, currency: str = 'RUB') -> str:
    """Форматирует валюту для отображения"""
    symbols = {
        'RUB': '₽',
        'USD': '$',
        'EUR': '€',
        'CNY': '¥',
        'KRW': '₩',
        'KGS': 'сом',
        'KZT': '₸'
    }
    
    symbol = symbols.get(currency, currency)
    
    if value >= 1000000:
        return f"{value/1000000:.2f} млн {symbol}"
    elif value >= 1000:
        return f"{value:,.0f} {symbol}".replace(',', ' ')
    else:
        return f"{value:.2f} {symbol}"


def format_breakdown(breakdown: Dict[str, float]) -> str:
    """Форматирует детальную разбивку для PDF"""
    lines = []
    for key, value in breakdown.items():
        lines.append(f"{key}: {format_currency(value)}")
    return "\n".join(lines)