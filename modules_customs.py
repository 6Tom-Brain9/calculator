"""
Модуль расчета таможенной пошлины
"""

from typing import Dict, Any
from utils_helpers import find_category_by_engine, find_bracket_by_value
from modules_currency import CurrencyConverter


class CustomsCalculator:
    """Калькулятор таможенной пошлины"""
    
    def __init__(self, customs_rates: Dict[str, Any]):
        self.rates = customs_rates
        self.currency = CurrencyConverter()
    
    def calculate_individual(self, customs_value_rub: float, engine_cc: int, age_years: float) -> float:
        """
        Расчет пошлины для физического лица
        
        Args:
            customs_value_rub: таможенная стоимость в рублях
            engine_cc: объем двигателя в куб.см
            age_years: возраст автомобиля в годах
        
        Returns:
            пошлина в рублях
        """
        # Конвертируем стоимость в евро для расчета
        customs_value_eur = self.currency.convert(customs_value_rub, 'RUB', 'EUR')
        
        # Возраст менее 3 лет
        if age_years < 3:
            return self._calc_by_value(customs_value_eur, engine_cc)
        
        # Возраст от 3 до 5 лет
        elif 3 <= age_years <= 5:
            return self._calc_by_volume(engine_cc, 'rate_3_5')
        
        # Возраст старше 5 лет
        else:
            return self._calc_by_volume(engine_cc, 'rate_5plus')
    
    def _calc_by_value(self, value_eur: float, engine_cc: int) -> float:
        """Расчет пошлины по стоимости (для авто до 3 лет)"""
        brackets = self.rates['individuals']['by_value']['brackets']
        bracket = find_bracket_by_value(value_eur, brackets)
        
        # Расчет по процентам
        by_percent = value_eur * bracket['percent'] / 100
        
        # Расчет по минимальной ставке за куб.см
        by_min = bracket['min_per_cm3'] * engine_cc
        
        # Пошлина = максимум из двух вариантов
        duty_eur = max(by_percent, by_min)
        
        # Конвертируем в рубли
        return self.currency.convert(duty_eur, 'EUR', 'RUB')
    
    def _calc_by_volume(self, engine_cc: int, rate_key: str) -> float:
        """Расчет пошлины по объему (для авто старше 3 лет)"""
        categories = self.rates['individuals']['by_volume']['categories']
        category = find_category_by_engine(engine_cc, categories)
        
        if not category:
            return 0
        
        rate = category.get(rate_key, 0)
        duty_eur = engine_cc * rate
        
        return self.currency.convert(duty_eur, 'EUR', 'RUB')
    
    def calculate_legal(self, customs_value_rub: float, engine_cc: int, fuel_type: str, age_years: float) -> float:
        """
        Расчет пошлины для юридического лица
        
        Args:
            customs_value_rub: таможенная стоимость в рублях
            engine_cc: объем двигателя в куб.см
            fuel_type: тип топлива (Бензин/Дизель/Гибрид/Электричка)
            age_years: возраст автомобиля в годах
        
        Returns:
            пошлина в рублях
        """
        # Для юрлиц пошлина считается только для авто до 3 лет
        if age_years >= 3:
            # после 3 лет — пошлина по объему как у физлиц
            return self._calc_by_volume(engine_cc, 'rate_3_5')
        
        # Для авто до 3 лет — процент от таможенной стоимости
        if fuel_type == 'Бензин':
            rates = self.rates['legal']['petrol']
        elif fuel_type == 'Дизель':
            rates = self.rates['legal']['diesel']
        else:
            # Для гибридов и электричек — как бензин
            rates = self.rates['legal']['petrol']
        
        category = find_category_by_engine(engine_cc, rates)
        if category:
            rate = category.get('rate_0_3', 0.15)
            return customs_value_rub * rate
        
        return customs_value_rub * 0.15  # default