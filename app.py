import streamlit as st
from datetime import datetime
from pathlib import Path
import requests
import urllib3
import yaml

# Отключаем SSL предупреждения
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

st.set_page_config(
    page_title="Калькулятор растаможки автомобилей",
    page_icon="🚗",
    layout="wide"
)

# ==================== ИНИЦИАЛИЗАЦИЯ SESSION_STATE ====================
if 'hp_kw' not in st.session_state:
    st.session_state.hp_kw = 0.0
if 'hp_hp' not in st.session_state:
    st.session_state.hp_hp = 0.0

# ==================== ЗАГРУЗКА YAML ====================

def load_yaml_config(file_path):
    try:
        if Path(file_path).exists():
            with open(file_path, 'r', encoding='utf-8') as f:
                data = yaml.safe_load(f) or {}
                return data
        else:
            st.warning(f"Файл не найден: {file_path}")
            return {}
    except Exception as e:
        st.warning(f"Ошибка загрузки {file_path}: {e}")
        return {}

def load_all_configs():
    DATA_DIR = Path(__file__).parent / "data"
    return {
        'utilization_rates': load_yaml_config(DATA_DIR / "data_utilization_rates.yaml"),
        'currencies': load_yaml_config(DATA_DIR / "data_currencies.yaml"),
        'customs_rates': load_yaml_config(DATA_DIR / "data_customs_rates.yaml"),
        'excise_rates': load_yaml_config(DATA_DIR / "data_excise_rates.yaml"),
        'delivery_costs': load_yaml_config(DATA_DIR / "data_delivery_costs.yaml"),
        'services': load_yaml_config(DATA_DIR / "data_services.yaml"),
        'coefficients': load_yaml_config(DATA_DIR / "data_coefficients.yaml"),
    }

# Загружаем конфигурации
if 'configs' not in st.session_state:
    st.session_state.configs = load_all_configs()

CONFIGS = st.session_state.configs

# ==================== КУРСЫ ВАЛЮТ ====================

@st.cache_data(ttl=3600, show_spinner=False)
def fetch_currency_rates():
    try:
        response = requests.get("http://www.cbr-xml-daily.ru/daily_json.js", timeout=10)
        if response.status_code == 200:
            data = response.json()
            return {
                'USD': data['Valute']['USD']['Value'],
                'EUR': data['Valute']['EUR']['Value'],
                'CNY': data['Valute']['CNY']['Value'],
                'KRW': data['Valute']['KRW']['Value'] / 1000,
                'date': data['Date'],
                'success': True
            }
    except Exception as e:
        print(f"Ошибка получения курсов: {e}")
    return {'success': False}

def get_exchange_rates(force_refresh=False):
    if force_refresh:
        st.cache_data.clear()
    rates = fetch_currency_rates()
    if rates['success']:
        return rates
    currencies = CONFIGS.get('currencies', {})
    rates_data = currencies.get('currencies', {})
    return {
        'success': False,
        'USD': rates_data.get('USD', {}).get('rate', 90.0),
        'EUR': rates_data.get('EUR', {}).get('rate', 98.0),
        'CNY': rates_data.get('CNY', {}).get('rate', 12.5),
        'KRW': rates_data.get('KRW', {}).get('rate', 0.065),
        'date': datetime.now().strftime('%Y-%m-%dT%H:%M:%S')
    }

# ==================== ТАМОЖЕННЫЙ СБОР ====================

def calculate_customs_fee(customs_value_rub):
    """
    Расчет таможенного сбора за оформление
    Постановление Правительства РФ от 28.12.2004 № 863
    """
    if customs_value_rub <= 200000:
        return 1231
    elif customs_value_rub <= 450000:
        return 2462
    elif customs_value_rub <= 1200000:
        return 4924
    elif customs_value_rub <= 2700000:
        return 13541
    elif customs_value_rub <= 4200000:
        return 18465
    elif customs_value_rub <= 5500000:
        return 21344
    elif customs_value_rub <= 7000000:
        return 49240
    else:
        return 73860

# ==================== ТАМОЖЕННАЯ ПОШЛИНА ====================

def get_customs_rate_by_value(customs_value_eur, rates_config):
    brackets = rates_config.get('individuals', {}).get('by_value', {}).get('brackets', [])
    for bracket in brackets:
        max_euro = bracket.get('max_euro')
        if max_euro is None or customs_value_eur <= max_euro:
            return bracket
    return brackets[-1] if brackets else {'percent': 48, 'min_per_cm3': 20}

def get_customs_rate_by_volume(engine_cc, age_years, rates_config):
    categories = rates_config.get('individuals', {}).get('by_volume', {}).get('categories', [])
    if 3 <= age_years <= 5:
        rate_key = 'rate_3_5'
    else:
        rate_key = 'rate_5plus'
    for cat in categories:
        min_cm3 = cat.get('min_cm3', 0)
        max_cm3 = cat.get('max_cm3')
        in_category = False
        if max_cm3 is None:
            if engine_cc >= min_cm3:
                in_category = True
        else:
            if min_cm3 <= engine_cc <= max_cm3:
                in_category = True
        if in_category:
            rate = cat.get(rate_key, 0)
            if rate == 0:
                return 3.6 if rate_key == 'rate_3_5' else 5.7
            return rate
    return 3.6 if (3 <= age_years <= 5) else 5.7

def calculate_customs_duty_individual(customs_value_rub, engine_cc, age_years, eur_rate):
    customs_value_eur = customs_value_rub / eur_rate
    rates_config = CONFIGS.get('customs_rates', {})
    if age_years < 3:
        bracket = get_customs_rate_by_value(customs_value_eur, rates_config)
        by_percent = customs_value_eur * bracket['percent'] / 100
        by_volume = engine_cc * bracket['min_per_cm3']
        duty_eur = max(by_percent, by_volume)
        return duty_eur * eur_rate
    else:
        rate = get_customs_rate_by_volume(engine_cc, age_years, rates_config)
        duty_eur = engine_cc * rate
        return duty_eur * eur_rate

# ==================== УТИЛЬСБОР ====================

def calculate_utilization_fee(engine_cc, horsepower_hp, age_years, is_electric=False, vehicle_type="Легковой", client_type="Физическое лицо"):
    rates_config = CONFIGS.get('utilization_rates', {})
    is_old = age_years >= 3
    power_kw = horsepower_hp / 1.3596
    base_rate = rates_config.get('base_rate', 20000)

    if client_type == "Физическое лицо":
        if horsepower_hp <= 160 and engine_cc <= 3000:
            coeff = 0.17 if not is_old else 0.26
            return base_rate * coeff

        if is_electric:
            electric_rates = rates_config.get('individuals', {}).get('electric', [])
            for bracket in electric_rates:
                power_max_kw = bracket.get('power_max_kw')
                if power_max_kw is None:
                    continue
                if power_kw <= power_max_kw:
                    coeff = bracket.get('old' if is_old else 'new', 1.0)
                    return base_rate * coeff
            if electric_rates:
                last = electric_rates[-1]
                coeff = last.get('old' if is_old else 'new', 1.0)
                return base_rate * coeff
            return base_rate * 100.0

        if 1000 < engine_cc <= 2000:
            rates_list = rates_config.get('individuals', {}).get('engine_1000_2000', [])
            if not rates_list:
                if 160 < horsepower_hp <= 190:
                    coeff = 37.5 if not is_old else 74.64
                    return base_rate * coeff
                elif 190 < horsepower_hp <= 220:
                    coeff = 39.7 if not is_old else 79.20
                elif 220 < horsepower_hp <= 250:
                    coeff = 42.1 if not is_old else 83.88
                elif 250 < horsepower_hp <= 280:
                    coeff = 47.6 if not is_old else 91.92
                elif 280 < horsepower_hp <= 310:
                    coeff = 53.8 if not is_old else 100.56
                elif 310 < horsepower_hp <= 340:
                    coeff = 60.8 if not is_old else 110.16
                elif 340 < horsepower_hp <= 370:
                    coeff = 69.3 if not is_old else 120.60
                elif 370 < horsepower_hp <= 400:
                    coeff = 79.0 if not is_old else 132.00
                elif 400 < horsepower_hp <= 430:
                    coeff = 90.0 if not is_old else 144.60
                elif 430 < horsepower_hp <= 460:
                    coeff = 102.7 if not is_old else 158.40
                elif 460 < horsepower_hp <= 500:
                    coeff = 117.0 if not is_old else 173.40
                else:
                    coeff = 133.4 if not is_old else 189.84
                return base_rate * coeff
            
            for bracket in rates_list:
                p_min = bracket.get('power_min_kw', 0)
                p_max = bracket.get('power_max_kw')
                if p_max is None:
                    if power_kw >= p_min:
                        coeff = bracket.get('old' if is_old else 'new', 1.0)
                        return base_rate * coeff
                else:
                    if p_min <= power_kw <= p_max:
                        coeff = bracket.get('old' if is_old else 'new', 1.0)
                        return base_rate * coeff
            return base_rate * 100.0

        elif 2000 < engine_cc <= 3000:
            rates_list = rates_config.get('individuals', {}).get('engine_2000_3000', [])
            if not rates_list:
                if 160 < horsepower_hp <= 190:
                    coeff = 115.34 if not is_old else 172.80
                elif 190 < horsepower_hp <= 220:
                    coeff = 118.20 if not is_old else 175.08
                elif 220 < horsepower_hp <= 250:
                    coeff = 120.12 if not is_old else 177.60
                elif 250 < horsepower_hp <= 280:
                    coeff = 126.00 if not is_old else 183.00
                elif 280 < horsepower_hp <= 310:
                    coeff = 131.04 if not is_old else 188.52
                elif 310 < horsepower_hp <= 340:
                    coeff = 136.32 if not is_old else 193.68
                elif 340 < horsepower_hp <= 370:
                    coeff = 141.72 if not is_old else 199.08
                elif 370 < horsepower_hp <= 400:
                    coeff = 147.48 if not is_old else 204.72
                elif 400 < horsepower_hp <= 430:
                    coeff = 153.36 if not is_old else 210.48
                elif 430 < horsepower_hp <= 460:
                    coeff = 159.48 if not is_old else 216.36
                elif 460 < horsepower_hp <= 500:
                    coeff = 165.84 if not is_old else 222.36
                else:
                    coeff = 172.44 if not is_old else 228.60
                return base_rate * coeff
            
            for bracket in rates_list:
                p_min = bracket.get('power_min_kw', 0)
                p_max = bracket.get('power_max_kw')
                if p_max is None:
                    if power_kw >= p_min:
                        coeff = bracket.get('old' if is_old else 'new', 1.0)
                        return base_rate * coeff
                else:
                    if p_min <= power_kw <= p_max:
                        coeff = bracket.get('old' if is_old else 'new', 1.0)
                        return base_rate * coeff
            return base_rate * 100.0

        elif 3000 < engine_cc <= 3500:
            rates = rates_config.get('individuals', {}).get('engine_3000_3500', {})
            coeff = rates.get('old' if is_old else 'new', 100.0)
            return base_rate * coeff

        elif engine_cc > 3500:
            rates = rates_config.get('individuals', {}).get('engine_over_3500', {})
            coeff = rates.get('old' if is_old else 'new', 100.0)
            return base_rate * coeff

        return base_rate * 100.0

    else:
        if vehicle_type in ["Грузовой", "Пикап"]:
            return rates_config.get('truck_base_rate', 150000) * 1.0

        if is_electric:
            electric_rates = rates_config.get('legal', {}).get('electric', [])
            for bracket in electric_rates:
                p_min = bracket.get('power_min_kw', 0)
                p_max = bracket.get('power_max_kw')
                if p_max is None:
                    if power_kw >= p_min:
                        coeff = bracket.get('old' if is_old else 'new', 1.0)
                        return base_rate * coeff
                else:
                    if p_min <= power_kw <= p_max:
                        coeff = bracket.get('old' if is_old else 'new', 1.0)
                        return base_rate * coeff
            return base_rate * 100.0

        if 1000 < engine_cc <= 2000:
            rates_list = rates_config.get('legal', {}).get('engine_1000_2000', [])
            for bracket in rates_list:
                p_min = bracket.get('power_min_kw', 0)
                p_max = bracket.get('power_max_kw')
                if p_max is None:
                    if power_kw >= p_min:
                        coeff = bracket.get('old' if is_old else 'new', 1.0)
                        return base_rate * coeff
                else:
                    if p_min <= power_kw <= p_max:
                        coeff = bracket.get('old' if is_old else 'new', 1.0)
                        return base_rate * coeff
            return base_rate * 100.0

        elif 2000 < engine_cc <= 3000:
            rates_list = rates_config.get('legal', {}).get('engine_2000_3000', [])
            for bracket in rates_list:
                p_min = bracket.get('power_min_kw', 0)
                p_max = bracket.get('power_max_kw')
                if p_max is None:
                    if power_kw >= p_min:
                        coeff = bracket.get('old' if is_old else 'new', 1.0)
                        return base_rate * coeff
                else:
                    if p_min <= power_kw <= p_max:
                        coeff = bracket.get('old' if is_old else 'new', 1.0)
                        return base_rate * coeff
            return base_rate * 100.0

        elif 3000 < engine_cc <= 3500:
            rates_list = rates_config.get('legal', {}).get('engine_3000_3500', [])
            for bracket in rates_list:
                p_min = bracket.get('power_min_kw', 0)
                p_max = bracket.get('power_max_kw')
                if p_max is None:
                    if power_kw >= p_min:
                        coeff = bracket.get('old' if is_old else 'new', 1.0)
                        return base_rate * coeff
                else:
                    if p_min <= power_kw <= p_max:
                        coeff = bracket.get('old' if is_old else 'new', 1.0)
                        return base_rate * coeff
            return base_rate * 100.0

        elif engine_cc > 3500:
            rates_list = rates_config.get('legal', {}).get('engine_over_3500', [])
            for bracket in rates_list:
                p_min = bracket.get('power_min_kw', 0)
                p_max = bracket.get('power_max_kw')
                if p_max is None:
                    if power_kw >= p_min:
                        coeff = bracket.get('old' if is_old else 'new', 1.0)
                        return base_rate * coeff
                else:
                    if p_min <= power_kw <= p_max:
                        coeff = bracket.get('old' if is_old else 'new', 1.0)
                        return base_rate * coeff
            return base_rate * 100.0

        return base_rate * 100.0

# ==================== АКЦИЗ ====================

def get_excise_rate(horsepower, rates_config):
    rates = rates_config.get('rates', [])
    for bracket in rates:
        min_hp = bracket.get('min_hp', 0)
        max_hp = bracket.get('max_hp')
        if max_hp is None:
            if horsepower >= min_hp:
                return bracket.get('rate', 0)
        else:
            if min_hp <= horsepower <= max_hp:
                return bracket.get('rate', 0)
    return 0

def calculate_excise(horsepower_hp, fuel_type):
    if fuel_type == "Электричка":
        return 0
    rate = get_excise_rate(horsepower_hp, CONFIGS.get('excise_rates', {}))
    return horsepower_hp * rate

# ==================== НДС ====================

def calculate_vat(customs_value, customs_duty, excise, client_type, destination):
    if client_type == "Физическое лицо":
        return 0
    base = customs_value + customs_duty + excise
    vat_rates = CONFIGS.get('coefficients', {}).get('taxes', {}).get('vat_import', {})
    if destination == "Бишкек":
        rate = vat_rates.get('kyrgyzstan_legal', 0.12)
    else:
        rate = vat_rates.get('legal', 0.20)
    return base * rate

# ==================== ДОСТАВКА И УСЛУГИ ====================

def get_delivery_cost(city, vehicle_type, delivery_config):
    costs = delivery_config.get('delivery_costs', {})
    oversize_coeff = delivery_config.get('oversize_coefficient', 1.2)
    cost = costs.get(city, 150000)
    if vehicle_type in ["Грузовой", "Пикап"]:
        cost = cost * oversize_coeff
    return cost

def get_service_cost(service_name, vehicle_type="Легковой", country_export="Корея"):
    services = CONFIGS.get('services', {}).get('services', {})
    if service_name == 'broker':
        return services.get('broker', {}).get(vehicle_type, 10000)
    elif service_name == 'epts':
        epts = services.get('epts', 15000)
        if country_export == "Китай":
            sbkts = services.get('sbkts', 20000)
            return max(epts, sbkts)
        return epts
    return 0

# ==================== КОЛБЭКИ ДЛЯ СИНХРОНИЗАЦИИ МОЩНОСТИ ====================

def update_hp_from_kw():
    st.session_state.hp_hp = st.session_state.hp_kw * 1.3596

def update_kw_from_hp():
    st.session_state.hp_kw = st.session_state.hp_hp / 1.3596

# ==================== ФОРМАТИРОВАНИЕ ЧИСЕЛ ====================

def format_number(num):
    return f"{num:,.0f}".replace(',', ' ')

def format_money(num, currency="₽"):
    return f"{format_number(num)} {currency}"

# ==================== КОМПОНЕНТЫ ДЛЯ ОТОБРАЖЕНИЯ ====================

def render_collapsible_block(title, total, items, default_open=False):
    """Рендерит сворачиваемый блок с итогом"""
    with st.expander(f"**{title}**", expanded=default_open):
        st.write(f"**ИТОГО: {format_money(total)}**")
        st.write("---")
        for label, value in items:
            st.write(f"• {label}: {format_money(value)}")

# ==================== ИНТЕРФЕЙС ====================

def main():
    st.title("🚗 Калькулятор растаможки автомобилей")
    st.markdown("---")

    rates = get_exchange_rates()

    col_date, col_btn = st.columns([3, 1])
    with col_date:
        if rates.get('success'):
            date_str = rates.get('date', '')
            try:
                date_obj = datetime.fromisoformat(date_str.replace('Z', '+00:00'))
                st.caption(f"💱 Курсы валют от {date_obj.strftime('%d.%m.%Y %H:%M')} (источник: ЦБ РФ)")
            except:
                st.caption(f"💱 Курсы валют от {date_str}")
        else:
            st.caption("⚠️ Курсы валют из резервного источника (ЦБ РФ недоступен)")
    with col_btn:
        if st.button("🔄 Обновить курсы", use_container_width=True):
            rates = get_exchange_rates(force_refresh=True)
            st.rerun()

    with st.sidebar:
        st.header("💱 Текущие курсы")
        st.metric("🇺🇸 USD", f"{rates['USD']:.2f} ₽")
        st.metric("🇪🇺 EUR", f"{rates['EUR']:.2f} ₽")
        st.metric("🇨🇳 CNY", f"{rates['CNY']:.4f} ₽ (за 1 юань)")
        st.metric("🇰🇷 KRW", f"{rates['KRW']:.4f} ₽ (за 1 вону)")
        st.caption(f"*Курс воны: {rates['KRW']*1000:.2f} ₽ за 1000 вон")
        st.markdown("---")
        st.markdown("**📌 Коэффициенты утильсбора:**")
        st.caption("• До 160 л.с. → 0.17 / 0.26")
        st.caption("• 160-190 л.с. → 37.5 / 74.64")
        st.caption("• 430-460 л.с. → 159.48 / 216.36")
        st.caption("• Основание: ПП РФ № 1713 от 01.11.2025")

    col1, col2 = st.columns(2)
    with col1:
        country_export = st.selectbox("🌏 Страна экспорта", ["Китай", "Корея"])
        city = st.selectbox("📍 Город доставки", [
            "Владивосток", "Москва", "Санкт-Петербург", "Новосибирск",
            "Екатеринбург", "Казань", "Краснодар", "Бишкек", "Алма-Аты"
        ])
        client_type = st.selectbox("👤 Тип клиента", ["Физическое лицо", "Юридическое лицо"])
        vehicle_type = st.selectbox("🚙 Тип транспорта", ["Легковой", "Грузовой", "Пикап", "Электричка"])
        fuel_type = st.selectbox("⛽ Тип топлива", ["Бензин", "Дизель", "Гибрид", "Электричка"])

    with col2:
        if country_export == "Китай":
            price_currency = "CNY (юань)"
            price_rate = rates['CNY']
        else:
            price_currency = "KRW (вона)"
            price_rate = rates['KRW']
        st.metric("💵 Актуальный курс", f"1 {price_currency.split()[0]} = {price_rate:.4f} ₽")

        price = st.number_input(f"💰 Стоимость авто ({price_currency})", min_value=0.0, value=138000000.0, step=5000000.0)
        price_rub_preview = price * price_rate
        st.caption(f"📌 Примерно: {format_number(price_rub_preview)} ₽ по текущему курсу")

        engine_cc = st.number_input("🔧 Объем двигателя", min_value=0, value=2999, step=100, help="куб.см")

        col_hp1, col_hp2 = st.columns(2)
        with col_hp1:
            st.number_input(
                "⚡ Мощность (кВт)",
                min_value=0.0,
                step=1.0,
                key='hp_kw',
                on_change=update_hp_from_kw,
                value=331.0,
                help="Мощность двигателя в киловаттах"
            )
        with col_hp2:
            st.number_input(
                "⚡ Мощность (л.с.)",
                min_value=0.0,
                step=1.0,
                key='hp_hp',
                on_change=update_kw_from_hp,
                help="Мощность двигателя в лошадиных силах"
            )

        horsepower_kw = st.session_state.hp_kw
        horsepower_hp = st.session_state.hp_hp

        weight = st.number_input("🏋️ Масса", min_value=0, value=1800, step=100, help="кг")
        manufacture_date = st.date_input("📅 Дата выпуска", value=datetime(2022, 1, 1))

    st.markdown("---")
    calculate = st.button("🧮 РАССЧИТАТЬ", type="primary", use_container_width=True)

    if calculate:
        age_years = (datetime.now() - datetime(manufacture_date.year, manufacture_date.month, manufacture_date.day)).days / 365.25
        age_years = round(age_years, 2)
        is_electric = fuel_type == "Электричка"

        # Конвертация цены
        if country_export == "Китай":
            price_rub = price * rates['CNY']
            price_currency_short = "CNY"
        else:
            price_rub = price * rates['KRW']
            price_currency_short = "KRW"

        # Комиссия дилера (отдельно!)
        dealer_commission_coeff = CONFIGS.get('coefficients', {}).get('dealer_commission', {})
        if country_export == "Китай":
            dealer_commission = price_rub * dealer_commission_coeff.get('Китай', {}).get('value', 0.15)
        else:
            dealer_commission_usd = dealer_commission_coeff.get('Корея', {}).get('value', 2500)
            dealer_commission = dealer_commission_usd * rates['USD']

        # Фрахт (отдельно!)
        delivery_to_border = 1500 * rates['USD']

        # Таможенная стоимость (без комиссии дилера и фрахта)
        customs_value = price_rub

        # Таможенные платежи
        customs_fee = calculate_customs_fee(customs_value)
        customs_duty = calculate_customs_duty_individual(customs_value, engine_cc, age_years, rates['EUR'])
        utilization = calculate_utilization_fee(engine_cc, horsepower_hp, age_years, is_electric, vehicle_type, client_type)
        excise = calculate_excise(horsepower_hp, fuel_type)
        vat = calculate_vat(customs_value, customs_duty, excise, client_type, city)

        # Расходы в РФ
        delivery_cost = get_delivery_cost(city, vehicle_type, CONFIGS.get('delivery_costs', {}))
        broker_cost = get_service_cost('broker', vehicle_type, country_export)
        epts_cost = get_service_cost('epts', vehicle_type, country_export)

        # Итоговые суммы по блокам
        total_customs = customs_fee + customs_duty + utilization + excise + vat
        total_abroad = price_rub + dealer_commission + delivery_to_border
        total_russia = delivery_cost + broker_cost + epts_cost
        total_cost = total_abroad + total_customs + total_russia

        # ==================== ОТОБРАЖЕНИЕ РЕЗУЛЬТАТОВ ====================
        st.markdown("---")
        st.header("📊 РЕЗУЛЬТАТ РАСЧЕТА")

        # ИТОГОВАЯ СУММА (крупно)
        st.markdown(
            f"""
            <div style="background: linear-gradient(135deg, #1e3c72 0%, #2a5298 100%); 
                        padding: 1.5rem; border-radius: 1rem; text-align: center; margin: 1rem 0;">
                <h2 style="color: white; margin: 0;">СТОИМОСТЬ ПОД КЛЮЧ</h2>
                <p style="color: #ffd700; font-size: 2.5rem; font-weight: bold; margin: 0.5rem 0;">
                    {format_money(total_cost)}
                </p>
                <p style="color: #ccc; margin: 0;">
                    {format_number(price)} {price_currency_short} × {price_rate:.4f} ₽ = {format_number(price_rub)} ₽
                </p>
            </div>
            """,
            unsafe_allow_html=True
        )

        # Блок 1: Расходы за границей (сворачиваемый)
        render_collapsible_block(
            "💰 Расходы за границей (стоимость авто + комиссия + фрахт)",
            total_abroad,
            [
                ("Стоимость авто", price_rub),
                ("Комиссия дилера", dealer_commission),
                ("Фрахт (доставка до границы)", delivery_to_border),
            ],
            default_open=True
        )

        # Блок 2: Таможенные платежи (сворачиваемый)
        render_collapsible_block(
            "🛃 Таможенные платежи (пошлина + утиль + сбор + акциз + НДС)",
            total_customs,
            [
                ("Таможенный сбор (оформление)", customs_fee),
                ("Таможенная пошлина", customs_duty),
                ("Утилизационный сбор", utilization),
                ("Акциз", excise),
                ("НДС", vat),
            ],
            default_open=True
        )

        # Блок 3: Расходы в РФ (сворачиваемый)
        render_collapsible_block(
            "🚛 Расходы в РФ (доставка + брокер + ЭПТС)",
            total_russia,
            [
                ("Доставка по РФ", delivery_cost),
                ("Услуги брокера", broker_cost),
                ("ЭПТС/СБКТС", epts_cost),
            ],
            default_open=True
        )

        # Информация о ставке утильсбора
        if client_type == "Физическое лицо":
            if horsepower_hp <= 160 and engine_cc <= 3000 and not is_electric:
                st.success(f"✅ Применена **льготная ставка** утильсбора (авто до 160 л.с., {horsepower_hp:.1f} л.с.)")
            elif is_electric and horsepower_hp <= 80:
                st.success(f"✅ Применена **льготная ставка** утильсбора (электромобиль до 80 л.с., {horsepower_hp:.1f} л.с.)")
            else:
                st.warning(f"⚠️ Применена **коммерческая ставка** утильсбора (авто свыше 160 л.с., {horsepower_hp:.1f} л.с.)")

        st.info(
            f"📅 Возраст: **{age_years} лет** | "
            f"💪 Мощность: **{horsepower_hp:.1f} л.с.** ({horsepower_kw:.1f} кВт) | "
            f"⚙️ Объем: **{engine_cc} см³**"
        )

        st.caption("⚠️ **Важно:** Данный расчет является ознакомительным. Точная сумма может отличаться.")

if __name__ == "__main__":
    main()
