"""
Модуль расчета акциза
"""

from typing import Dict, Any, Optional
from utils_helpers import find_category_by_engine


class ExciseCalculator:
    """Калькулятор акциза на автомобили"""
    
    def __init__(self, excise_rates: Dict[str, Any]):
        self.rates = excise_rates
    
    def calculate(self, horsepower: float, fuel_type: str = "Бензин") -> float:
        """
        Расчет акциза
        
        Args:
            horsepower: мощность в л.с.
            fuel_type: тип топлива (для определения ставки)
        
        Returns:
            сумма акциза в рублях
        """
        # Для электромобилей акциз = 0
        if fuel_type == "Электричка":
            return 0
        
        # Находим ставку по мощности
        rate_per_hp = self._find_rate(horsepower)
        
        if rate_per_hp is None:
            return 0
        
        return horsepower * rate_per_hp
    
    def _find_rate(self, horsepower: float) -> Optional[float]:
        """Находит ставку акциза по мощности"""
        rates_list = self.rates.get('rates', [])
        
        for bracket in rates_list:
            min_hp = bracket.get('min_hp', 0)
            max_hp = bracket.get('max_hp')
            
            if max_hp is None:
                if horsepower >= min_hp:
                    return bracket.get('rate')
            else:
                if min_hp <= horsepower <= max_hp:
                    return bracket.get('rate')
        
        return None