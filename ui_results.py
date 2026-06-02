"""
Компоненты отображения результатов
"""

import streamlit as st
import pandas as pd
from datetime import datetime
from typing import Dict, Any
from utils_helpers import format_currency


def render_currency_info(rates: Dict[str, float], last_update: datetime):
    """
    Отображает информацию о курсах валют
    
    Args:
        rates: словарь с курсами
        last_update: дата последнего обновления
    """
    with st.expander("📈 Курсы валют", expanded=False):
        col1, col2, col3, col4 = st.columns(4)
        
        currencies_info = [
            ("🇺🇸 USD", f"{rates.get('USD', 0):.2f} ₽"),
            ("🇪🇺 EUR", f"{rates.get('EUR', 0):.2f} ₽"),
            ("🇨🇳 CNY", f"{rates.get('CNY', 0):.4f} ₽"),
            ("🇰🇷 KRW (1000)", f"{rates.get('KRW', 0):.2f} ₽"),
            ("🇰🇬 KGS (100)", f"{rates.get('KGS', 0):.2f} ₽"),
            ("🇰🇿 KZT (100)", f"{rates.get('KZT', 0):.2f} ₽"),
        ]
        
        for i, (currency, rate) in enumerate(currencies_info):
            if i < 4:
                with col1 if i == 0 else col2 if i == 1 else col3 if i == 2 else col4:
                    st.metric(currency, rate)
            else:
                with col1 if i == 4 else col2:
                    st.metric(currency, rate)
        
        st.caption(f"🕐 Курсы обновлены: {last_update.strftime('%d.%m.%Y %H:%M') if last_update else 'неизвестно'}")


def render_total_cost(total_cost_rub: float):
    """
    Отображает итоговую стоимость крупно
    
    Args:
        total_cost_rub: итоговая стоимость в рублях
    """
    st.markdown("---")
    
    # Крупная цифра
    if total_cost_rub >= 1_000_000:
        cost_display = f"{total_cost_rub/1_000_000:.2f} млн ₽"
    else:
        cost_display = f"{total_cost_rub:,.0f} ₽".replace(',', ' ')
    
    st.markdown(
        f"""
        <div style="
            background: linear-gradient(135deg, #1e3c72 0%, #2a5298 100%);
            padding: 2rem;
            border-radius: 1rem;
            text-align: center;
            margin: 1rem 0;
        ">
            <h2 style="color: white; margin: 0;">СТОИМОСТЬ ПОД КЛЮЧ</h2>
            <p style="color: #ffd700; font-size: 3rem; font-weight: bold; margin: 0.5rem 0;">
                {cost_display}
            </p>
            <p style="color: #ccc; margin: 0;">включая все налоги и сборы</p>
        </div>
        """,
        unsafe_allow_html=True
    )


def render_cost_breakdown(components: Dict[str, float]):
    """
    Отображает детальную разбивку расходов
    
    Args:
        components: словарь с компонентами стоимости
    """
    st.subheader("📋 Детальная разбивка расходов")
    
    # Создаем DataFrame для отображения
    df_data = []
    
    labels = {
        'price_abroad_rub': '💰 Стоимость авто за границей',
        'dealer_commission_rub': '🏢 Комиссия дилера',
        'carstar_commission_rub': '⭐ Комиссия CarStar',
        'delivery_to_border_rub': '🚢 Доставка до границы РФ',
        'customs_value_rub': '📦 Таможенная стоимость',
        'customs_duty_rub': '🛃 Таможенная пошлина',
        'utilization_rub': '♻️ Утилизационный сбор',
        'excise_rub': '📊 Акциз',
        'vat_import_rub': '🧾 НДС при ввозе',
        'delivery_russia_rub': '🚛 Доставка по РФ',
        'services_total_rub': '🔧 Услуги (брокер, ЭПТС, ГЛОНАС)',
        'insurance_rub': '🛡️ Страхование'
    }
    
    for key, label in labels.items():
        if key in components:
            df_data.append({
                'Статья расходов': label,
                'Сумма, ₽': f"{components[key]:,.0f}".replace(',', ' ')
            })
    
    # Добавляем итог
    total = sum([v for k, v in components.items() if k != 'customs_value_rub'])
    df_data.append({
        'Статья расходов': '🏁 ИТОГО СЕБЕСТОИМОСТЬ',
        'Сумма, ₽': f"{total:,.0f}".replace(',', ' ')
    })
    
    df = pd.DataFrame(df_data)
    st.dataframe(df, use_container_width=True, hide_index=True)


def render_profit_breakdown(profit_data: Dict[str, float], markup_rate: float, sale_price: float):
    """
    Отображает разбивку прибыли для юридических лиц
    
    Args:
        profit_data: словарь с данными о прибыли
        markup_rate: ставка наценки
        sale_price: цена продажи
    """
    st.subheader("📈 Коммерческий расчет (юридическое лицо)")
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.metric(
            "Наценка от себестоимости",
            f"{markup_rate * 100:.0f}%"
        )
        st.metric(
            "Цена продажи (с НДС)",
            format_currency(sale_price, 'RUB')
        )
    
    with col2:
        st.metric(
            "Валовая прибыль",
            format_currency(profit_data.get('profit_before_tax_rub', 0), 'RUB')
        )
        st.metric(
            "Чистая прибыль",
            format_currency(profit_data.get('net_profit_rub', 0), 'RUB'),
            delta=f"-{profit_data.get('profit_before_tax_rub', 0) - profit_data.get('net_profit_rub', 0):,.0f} ₽ налоги"
        )
    
    # Детали налогов
    with st.expander("Подробнее о налогах"):
        tax_data = {
            'НДС при продаже (20%)': profit_data.get('vat_sale_rub', 0),
            'Налог на прибыль (20%)': profit_data.get('profit_tax_rub', 0),
            'НСП (2%)': profit_data.get('social_tax_rub', 0),
            'ИТОГО НАЛОГОВ': (
                profit_data.get('vat_sale_rub', 0) +
                profit_data.get('profit_tax_rub', 0) +
                profit_data.get('social_tax_rub', 0)
            )
        }
        
        for label, value in tax_data.items():
            st.write(f"**{label}:** {format_currency(value, 'RUB')}")


def render_export_buttons(result_data: Dict[str, Any]):
    """
    Кнопки для экспорта результатов
    
    Args:
        result_data: полный результат расчета
    """
    st.markdown("---")
    st.subheader("📎 Экспорт результата")
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        if st.button("📄 Сохранить в PDF", use_container_width=True):
            # Здесь будет логика генерации PDF
            st.info("PDF экспорт будет добавлен в следующей версии")
    
    with col2:
        if st.button("📊 Сохранить в Excel", use_container_width=True):
            st.info("Excel экспорт будет добавлен в следующей версии")
    
    with col3:
        if st.button("📋 Копировать в буфер", use_container_width=True):
            st.info("Копирование будет добавлено в следующей версии")