"""
Модуль расчета утилизационного сбора
"""

from typing import Dict, Any, Optional
from datetime import datetime
from utils_helpers import find_category_by_engine
from utils_currency_api import converter


class UtilizationCalculator:
    """Калькулятор утилизационного сбора"""
    
    def __init__(self, utilization_rates: Dict[str, Any], coefficients: Dict[str, Any]):
        self.rates = utilization_rates
        self.coefficients = coefficients
        self.base_rate = utilization_rates.get('base_rate', 20000)
    
    def calculate(
        self,
        engine_cc: int,
        manufacture_year: int,
        age_years: float,
        is_electric: bool = False,
        vehicle_type: str = "Легковой",
        client_type: str = "Физическое лицо",
        destination: str = "РФ"
    ) -> float:
        """
        Расчет утилизационного сбора
        
        Args:
            engine_cc: объем двигателя в куб.см
            manufacture_year: год выпуска
            age_years: возраст в годах
            is_electric: электромобиль или гибрид
            vehicle_type: тип авто (Легковой/Грузовой/Пикап)
            client_type: Физ.лицо / Юр.лицо
            destination: РФ / Киргизия / Казахстан
        
        Returns:
            сумма утильсбора в рублях
        """
        # Особые условия для Киргизии и Казахстана
        if destination in ["Бишкек", "Алма-Аты"]:
            return self._calculate_abroad(engine_cc, age_years, vehicle_type, destination)
        
        # Для физических лиц
        if client_type == "Физическое лицо":
            return self._calculate_individual(engine_cc, age_years, is_electric)
        
        # Для юридических лиц
        return self._calculate_legal(engine_cc, manufacture_year, age_years, is_electric, vehicle_type)
    
    def _calculate_individual(self, engine_cc: int, age_years: float, is_electric: bool) -> float:
        """Расчет для физических лиц"""
        # Для электромобилей
        if is_electric:
            # До 2025 года - льготный коэффициент
            if age_years < 3:
                coeff = 0.17
            else:
                coeff = 0.26
            return self.base_rate * coeff
        
        # Для авто с ДВС
        if age_years < 3:
            # Новые авто (до 3 лет)
            if engine_cc <= 1000:
                coeff = 0.17
            elif engine_cc <= 2000:
                coeff = 0.17
            elif engine_cc <= 3000:
                coeff = 0.17
            elif engine_cc <= 3500:
                coeff = 89.73  # специальный коэффициент для 3000-3500
            else:
                coeff = 114.26
        else:
            # Старые авто (старше 3 лет)
            if engine_cc <= 1000:
                coeff = 0.26
            elif engine_cc <= 2000:
                coeff = 0.26
            elif engine_cc <= 3000:
                coeff = 0.26
            elif engine_cc <= 3500:
                coeff = 137.36
            else:
                coeff = 150.2
        
        return self.base_rate * coeff
    
    def _calculate_legal(
        self,
        engine_cc: int,
        manufacture_year: int,
        age_years: float,
        is_electric: bool,
        vehicle_type: str
    ) -> float:
        """Расчет для юридических лиц"""
        # Определяем текущий год для коэффициента
        current_year = datetime.now().year
        is_new = age_years < 3
        
        # Определяем категорию
        category = self._get_category(engine_cc, is_electric, vehicle_type)
        if not category:
            return 0
        
        # Получаем коэффициент по году
        coeff = self._get_coefficient_by_year(category, current_year, is_new)
        
        # Для грузовых и пикапов базовая ставка 150000
        if vehicle_type in ["Грузовой", "Пикап"]:
            base_rate = 150000
        else:
            base_rate = self.base_rate
        
        return base_rate * coeff
    
    def _get_category(self, engine_cc: int, is_electric: bool, vehicle_type: str) -> Optional[Dict]:
        """Определяет категорию для юридических лиц"""
        if vehicle_type in ["Грузовой", "Пикап"]:
            # Для грузовых отдельная логика
            categories = self.rates.get('legal_truck', {}).get('categories', [])
        else:
            categories = self.rates.get('legal', {}).get('categories', [])
        
        if is_electric:
            # Ищем категорию "электромобили"
            for cat in categories:
                if cat.get('is_electric'):
                    return cat
        
        return find_category_by_engine(engine_cc, categories)
    
    def _get_coefficient_by_year(self, category: Dict, year: int, is_new: bool) -> float:
        """Получает коэффициент по году"""
        years_data = category.get('years', {})
        
        # Ищем подходящий год (если нет точного, берем ближайший предыдущий)
        available_years = sorted(years_data.keys())
        target_year = None
        
        for y in available_years:
            if y <= year:
                target_year = y
            else:
                break
        
        if target_year is None:
            target_year = available_years[0] if available_years else 2024
        
        year_coeffs = years_data.get(target_year, {})
        key = 'new' if is_new else 'old'
        
        return year_coeffs.get(key, 1.0)
    
    def _calculate_abroad(self, engine_cc: int, age_years: float, vehicle_type: str, destination: str) -> float:
        """Расчет для Киргизии и Казахстана"""
        # В Киргизии и Казахстане утильсбор рассчитывается по местным правилам
        if destination == "Бишкек":
            # Киргизия: зависит от объема и возраста
            if vehicle_type == "Грузовой":
                # Грузовые платят больше
                base = 50000
                if age_years < 3:
                    coeff = 0.5
                else:
                    coeff = 1.0
            else:
                # Легковые
                base = 20000
                if engine_cc <= 1000:
                    coeff = 0.5
                elif engine_cc <= 2000:
                    coeff = 0.8
                elif engine_cc <= 3000:
                    coeff = 1.0
                else:
                    coeff = 1.5
            return base * coeff
        
        elif destination == "Алма-Аты":
            # Казахстан: утильсбор через МРП
            mrp = 3692  # Месячный расчетный показатель
            if engine_cc <= 1000:
                mrp_count = 5
            elif engine_cc <= 2000:
                mrp_count = 10
            elif engine_cc <= 3000:
                mrp_count = 20
            else:
                mrp_count = 35
            
            if age_years > 7:
                mrp_count = mrp_count * 1.5
            
            return mrp * mrp_count * converter.get_rate('KZT')
        
        return 0