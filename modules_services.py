"""
Модуль расчета услуг (брокер, ЭПТС, ГЛОНАС и т.д.)
"""

from typing import Dict, Any
from utils_currency_api import converter


class ServicesCalculator:
    """Калькулятор дополнительных услуг"""
    
    def __init__(self, services: Dict[str, Any], coefficients: Dict[str, Any]):
        self.services = services.get('services', {})
        self.kyrgyzstan = services.get('kyrgyzstan', {})
        self.kazakhstan = services.get('kazakhstan', {})
        self.coefficients = coefficients
    
    def calculate_broker(self, vehicle_type: str) -> float:
        """Услуги таможенного брокера"""
        rates = self.services.get('broker', {})
        return rates.get(vehicle_type, 10000)
    
    def calculate_epts(self, vehicle_type: str, country_export: str = "Корея") -> float:
        """ЭПТС (электронный ПТС)"""
        epts = self.services.get('epts', 15000)
        
        # Для Китая нужен СБКТС (дороже)
        if country_export == "Китай":
            sbkts = self.services.get('sbkts', 20000)
            return max(epts, sbkts)
        
        return epts
    
    def calculate_glonas(self, vehicle_type: str, age_years: float) -> float:
        """ГЛОНАС (только для авто до 3 лет?)"""
        glonas = self.services.get('glonas', 40000)
        
        # Для старых авто ГЛОНАС не требуется
        if age_years > 3:
            return 0
        
        return glonas
    
    def calculate_prr(self) -> float:
        """Погрузо-разгрузочные работы"""
        return self.services.get('prr', 35000)
    
    def calculate_expertize(self) -> float:
        """Экспертиза, досмотр"""
        return self.services.get('expertize', 2500)
    
    def calculate_transfer(self) -> float:
        """Перегон (СВХ → лаборатория → стоянка → ТК)"""
        return self.services.get('transfer', 7000)
    
    def calculate_parking(self, days: int = 5) -> float:
        """Стоянка"""
        daily = self.services.get('parking', 150)
        free_days = self.services.get('storage_free_days', 5)
        
        if days <= free_days:
            return 0
        
        return (days - free_days) * daily
    
    def calculate_kyrgyzstan_services(self, customs_value_rub: float) -> Dict[str, float]:
        """Услуги в Киргизии"""
        kgs_rate = converter.get_rate('KGS') / 100  # за 1 сом
        
        registration_first = self.kyrgyzstan.get('registration_first', 1000) * kgs_rate
        registration_second = self.kyrgyzstan.get('registration_second', 3000) * kgs_rate
        laboratory = self.kyrgyzstan.get('laboratory', 2000) * kgs_rate
        
        customs_percent = self.kyrgyzstan.get('customs_service_percent', 0.05)
        customs_min = self.kyrgyzstan.get('customs_service_min', 4000) * kgs_rate
        customs_service = max(customs_value_rub * customs_percent, customs_min)
        
        return {
            'registration_first': registration_first,
            'registration_second': registration_second,
            'laboratory': laboratory,
            'customs_service': customs_service
        }
    
    def calculate_total_services(
        self,
        vehicle_type: str,
        country_export: str,
        age_years: float,
        destination: str,
        customs_value_rub: float = 0
    ) -> Dict[str, float]:
        """
        Полный расчет всех услуг
        
        Returns:
            словарь со всеми услугами и итогом
        """
        result = {
            'broker': self.calculate_broker(vehicle_type),
            'epts': self.calculate_epts(vehicle_type, country_export),
            'glonas': self.calculate_glonas(vehicle_type, age_years),
            'prr': self.calculate_prr(),
            'expertize': self.calculate_expertize(),
            'transfer': self.calculate_transfer(),
            'parking': self.calculate_parking(),
            'total': 0
        }
        
        # Для Киргизии добавляем местные услуги
        if destination == "Бишкек":
            kyrgyz_services = self.calculate_kyrgyzstan_services(customs_value_rub)
            result.update(kyrgyz_services)
        
        result['total'] = sum([v for k, v in result.items() if k != 'total'])
        
        return result