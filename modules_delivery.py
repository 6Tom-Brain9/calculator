"""
Модуль расчета доставки
"""

from typing import Dict, Any
from utils_currency_api import converter


class DeliveryCalculator:
    """Калькулятор доставки"""
    
    def __init__(self, delivery_costs: Dict[str, Any], coefficients: Dict[str, Any]):
        self.delivery_costs = delivery_costs.get('delivery_costs', {})
        self.oversize_coeff = delivery_costs.get('oversize_coefficient', 1.2)
        self.coefficients = coefficients
    
    def calculate_delivery_russia(self, city: str, vehicle_type: str = "Легковой") -> float:
        """
        Расчет доставки по РФ автовозом из Владивостока
        
        Args:
            city: город доставки
            vehicle_type: тип авто (для коэффициента негабарита)
        
        Returns:
            стоимость доставки в рублях
        """
        cost = self.delivery_costs.get(city, 0)
        
        # Для пикапов и грузовых - повышенный коэффициент
        if vehicle_type in ["Грузовой", "Пикап"]:
            cost = cost * self.oversize_coeff
        
        return cost
    
    def calculate_delivery_abroad(self, country: str, vehicle_type: str = "Легковой") -> float:
        """
        Расчет доставки от границы до города в Киргизии/Казахстане
        
        Args:
            country: страна (Киргизия/Казахстан)
            vehicle_type: тип авто
        
        Returns:
            стоимость доставки в рублях (конвертируется из местной валюты)
        """
        if country == "Киргизия":
            # Доставка до Бишкека ~ $500-1000
            cost_usd = 800
            return converter.convert(cost_usd, 'USD', 'RUB')
        elif country == "Казахстан":
            # Доставка до Алма-Аты ~ $600-1200
            cost_usd = 900
            return converter.convert(cost_usd, 'USD', 'RUB')
        
        return 0
    
    def calculate_total_delivery(
        self,
        city: str,
        country_export: str,
        vehicle_type: str = "Легковой"
    ) -> Dict[str, float]:
        """
        Полный расчет доставки
        
        Returns:
            словарь с компонентами доставки
        """
        result = {
            'from_border_to_city': 0,
            'from_vladivostok': 0,
            'total': 0
        }
        
        # Доставка от границы до города (для Киргизии/Казахстана)
        if city in ["Бишкек", "Алма-Аты"]:
            country = "Киргизия" if city == "Бишкек" else "Казахстан"
            result['from_border_to_city'] = self.calculate_delivery_abroad(country, vehicle_type)
        else:
            # Доставка по РФ из Владивостока
            result['from_vladivostok'] = self.calculate_delivery_russia(city, vehicle_type)
        
        result['total'] = result['from_border_to_city'] + result['from_vladivostok']
        
        return result