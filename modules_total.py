"""
Модуль сборки итоговой калькуляции
"""

from typing import Dict, Any
from modules_customs import CustomsCalculator
from modules_utilization import UtilizationCalculator
from modules_excise import ExciseCalculator
from modules_vat import VatCalculator
from modules_delivery import DeliveryCalculator
from modules_services import ServicesCalculator
from utils_currency_api import converter
from utils_validators import calculate_age


class TotalCalculator:
    """Главный калькулятор, собирающий все компоненты"""
    
    def __init__(self, configs: Dict[str, Any]):
        self.customs = CustomsCalculator(configs['customs_rates'])
        self.utilization = UtilizationCalculator(configs['utilization_rates'], configs['coefficients'])
        self.excise = ExciseCalculator(configs['excise_rates'])
        self.vat = VatCalculator(configs['coefficients'])
        self.delivery = DeliveryCalculator(configs['delivery_costs'], configs['coefficients'])
        self.services = ServicesCalculator(configs['services'], configs['coefficients'])
        self.coefficients = configs['coefficients']
    
    def calculate(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Полный расчет себестоимости автомобиля "под ключ"
        
        Args:
            input_data: словарь с входными параметрами
                - country_export: Китай / Корея
                - city: город доставки
                - client_type: Физическое лицо / Юридическое лицо
                - vehicle_type: Легковой / Грузовой / Пикап / Мотоцикл / Электричка
                - fuel_type: Бензин / Дизель / Гибрид / Гибрид послед. / Электричка
                - condition: Новый / С пробегом
                - price: float (стоимость в валюте страны экспорта)
                - engine_cc: int (объем, куб.см)
                - horsepower: float (мощность, л.с.)
                - weight: float (масса, кг)
                - manufacture_date: str (YYYY-MM-DD)
        
        Returns:
            словарь с результатами расчета
        """
        
        # 1. Базовые параметры
        age_years = calculate_age(datetime.strptime(input_data['manufacture_date'], '%Y-%m-%d'))
        manufacture_year = datetime.strptime(input_data['manufacture_date'], '%Y-%m-%d').year
        is_electric = input_data['fuel_type'] == "Электричка"
        
        # 2. Конвертация стоимости в рубли
        if input_data['country_export'] == "Китай":
            price_rub = converter.convert(input_data['price'], 'CNY', 'RUB')
        else:  # Корея
            price_rub = converter.convert(input_data['price'], 'KRW', 'RUB')
        
        # 3. Комиссия дилера
        dealer_commission_coeff = self.coefficients['dealer_commission']
        if input_data['country_export'] == "Китай":
            dealer_commission = price_rub * dealer_commission_coeff['Китай']['value']
        else:
            dealer_commission_usd = dealer_commission_coeff['Корея']['value']
            dealer_commission = converter.convert(dealer_commission_usd, 'USD', 'RUB')
        
        # 4. Комиссия CarStar
        carstar_commission = self.coefficients['carstar_commission'].get(input_data['country_export'], 0)
        
        # 5. Доставка до границы (фрахт)
        delivery_to_border_usd = 1500  # фиксированно в USD
        delivery_to_border_rub = converter.convert(delivery_to_border_usd, 'USD', 'RUB')
        
        # 6. Стоимость на границе (таможенная стоимость)
        customs_value_rub = price_rub + dealer_commission + carstar_commission + delivery_to_border_rub
        
        # 7. Таможенная пошлина
        if input_data['client_type'] == "Физическое лицо":
            customs_duty = self.customs.calculate_individual(
                customs_value_rub, input_data['engine_cc'], age_years
            )
        else:
            customs_duty = self.customs.calculate_legal(
                customs_value_rub, input_data['engine_cc'], input_data['fuel_type'], age_years
            )
        
        # 8. Утильсбор
        utilization = self.utilization.calculate(
            engine_cc=input_data['engine_cc'],
            manufacture_year=manufacture_year,
            age_years=age_years,
            is_electric=is_electric,
            vehicle_type=input_data['vehicle_type'],
            client_type=input_data['client_type'],
            destination=input_data['city']
        )
        
        # 9. Акциз
        excise = self.excise.calculate(input_data['horsepower'], input_data['fuel_type'])
        
        # 10. НДС при ввозе
        vat_import = self.vat.calculate_import_vat(
            customs_value_rub, customs_duty, excise,
            input_data['client_type'], input_data['city']
        )
        
        # 11. Доставка по РФ/до города
        delivery = self.delivery.calculate_total_delivery(
            input_data['city'], input_data['country_export'], input_data['vehicle_type']
        )
        
        # 12. Услуги (брокер, ЭПТС, ГЛОНАС и т.д.)
        services = self.services.calculate_total_services(
            vehicle_type=input_data['vehicle_type'],
            country_export=input_data['country_export'],
            age_years=age_years,
            destination=input_data['city'],
            customs_value_rub=customs_value_rub
        )
        
        # 13. Страхование (необязательное)
        insurance_coeff = self.coefficients.get('insurance', {}).get('default_percent', 0.002)
        insurance = customs_value_rub * insurance_coeff
        
        # 14. Итого себестоимость
        total_cost = (
            customs_value_rub +           # стоимость на границе
            customs_duty +                # пошлина
            utilization +                 # утильсбор
            excise +                      # акциз
            vat_import +                  # НДС при ввозе
            delivery['total'] +           # доставка
            services['total'] +           # услуги
            insurance                     # страховка
        )
        
        # 15. Расчет для юридических лиц (налоги при перепродаже)
        markup_rate = self.coefficients.get('markup', {}).get('default', 0.20)
        sale_price = total_cost * (1 + markup_rate)
        
        profit_before_tax = sale_price - total_cost
        
        vat_sale = self.vat.calculate_sale_vat(sale_price, input_data['client_type'])
        profit_tax = self.vat.calculate_profit_tax(profit_before_tax, input_data['client_type'])
        social_tax = self.vat.calculate_social_tax(profit_before_tax, input_data['client_type'])
        
        net_profit = profit_before_tax - vat_sale - profit_tax - social_tax
        
        # 16. Формируем результат
        result = {
            'input': input_data,
            'age_years': age_years,
            'cost_components': {
                'price_abroad_rub': price_rub,
                'dealer_commission_rub': dealer_commission,
                'carstar_commission_rub': carstar_commission,
                'delivery_to_border_rub': delivery_to_border_rub,
                'customs_value_rub': customs_value_rub,
                'customs_duty_rub': customs_duty,
                'utilization_rub': utilization,
                'excise_rub': excise,
                'vat_import_rub': vat_import,
                'delivery_russia_rub': delivery['total'],
                'services_total_rub': services['total'],
                'insurance_rub': insurance
            },
            'total_cost_rub': total_cost,
            'markup_rate': markup_rate,
            'sale_price_rub': sale_price,
            'profit_breakdown': {
                'profit_before_tax_rub': profit_before_tax,
                'vat_sale_rub': vat_sale,
                'profit_tax_rub': profit_tax,
                'social_tax_rub': social_tax,
                'net_profit_rub': net_profit
            } if input_data['client_type'] == "Юридическое лицо" else None
        }
        
        return result