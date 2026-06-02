"""
Модуль расчета НДС
"""

from typing import Dict, Any


class VatCalculator:
    """Калькулятор НДС"""
    
    def __init__(self, coefficients: Dict[str, Any]):
        self.taxes = coefficients.get('taxes', {})
    
    def calculate_import_vat(
        self,
        customs_value: float,
        customs_duty: float,
        excise: float,
        client_type: str,
        destination: str = "РФ"
    ) -> float:
        """
        Расчет НДС при ввозе
        
        Args:
            customs_value: таможенная стоимость
            customs_duty: таможенная пошлина
            excise: акциз
            client_type: Физ.лицо / Юр.лицо
            destination: РФ / Бишкек / Алма-Аты
        
        Returns:
            сумма НДС в рублях
        """
        # Физические лица не платят НДС при ввозе
        if client_type == "Физическое лицо":
            return 0
        
        # Определяем ставку
        if destination == "Бишкек":
            rate = self.taxes.get('vat_import', {}).get('kyrgyzstan_legal', 0.12)
        else:
            rate = self.taxes.get('vat_import', {}).get('legal', 0.20)
        
        # База для НДС = стоимость + пошлина + акциз
        base = customs_value + customs_duty + excise
        
        return base * rate
    
    def calculate_sale_vat(self, sale_price: float, client_type: str) -> float:
        """
        Расчет НДС при продаже (для юрлиц-перекупщиков)
        
        Args:
            sale_price: цена продажи (с НДС или без?)
            client_type: тип клиента
        
        Returns:
            сумма НДС к уплате
        """
        # Физические лица не платят НДС при продаже
        if client_type == "Физическое лицо":
            return 0
        
        rate = self.taxes.get('vat_sale', 0.20)
        
        # Если цена уже с НДС, выделяем
        return sale_price * rate / (1 + rate)
    
    def calculate_profit_tax(self, profit: float, client_type: str) -> float:
        """
        Расчет налога на прибыль (для юрлиц)
        
        Args:
            profit: прибыль до налогообложения
            client_type: тип клиента
        
        Returns:
            сумма налога на прибыль
        """
        if client_type == "Физическое лицо":
            return 0
        
        rate = self.taxes.get('profit_tax', 0.20)
        return profit * rate
    
    def calculate_social_tax(self, profit: float, client_type: str) -> float:
        """
        Расчет НСП (2% от прибыли) для юрлиц
        
        Args:
            profit: прибыль до налогообложения
            client_type: тип клиента
        
        Returns:
            сумма НСП
        """
        if client_type == "Физическое лицо":
            return 0
        
        rate = self.taxes.get('social_tax', 0.02)
        return profit * rate