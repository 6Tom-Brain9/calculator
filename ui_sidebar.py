"""
Боковая панель с дополнительной информацией
"""

import streamlit as st
from datetime import datetime
from typing import Dict, Any


def render_sidebar(rates: Dict[str, float], last_update: datetime = None):
    """
    Отрисовывает боковую панель
    """
    with st.sidebar:
        st.image("https://img.icons8.com/color/96/000000/car--v1.png", width=80)
        st.title("📌 О калькуляторе")
        
        st.markdown("""
        **Калькулятор растаможки автомобилей** рассчитывает полную стоимость 
        ввоза автомобиля из Китая или Кореи в Россию.
        """)
        
        st.markdown("---")
        
        # Курсы валют
        st.subheader("💱 Актуальные курсы")
        
        if rates:
            col1, col2 = st.columns(2)
            with col1:
                st.metric("🇺🇸 USD", f"{rates.get('USD', 0):.2f} ₽")
                st.metric("🇪🇺 EUR", f"{rates.get('EUR', 0):.2f} ₽")
                st.metric("🇨🇳 CNY", f"{rates.get('CNY', 0):.4f} ₽")
            with col2:
                st.metric("🇰🇷 KRW (1000)", f"{rates.get('KRW', 0):.2f} ₽")
                st.metric("🇰🇬 KGS (100)", f"{rates.get('KGS', 0):.2f} ₽")
                st.metric("🇰🇿 KZT (100)", f"{rates.get('KZT', 0):.2f} ₽")
            
            if last_update:
                st.caption(f"🕐 Обновлено: {last_update.strftime('%d.%m.%Y %H:%M')}")
        
        st.markdown("---")
        
        st.caption("""
        **Версия:** 1.0.0  
        **Источник курсов:** ЦБ РФ (автообновление раз в час)
        
        *Данные носят ознакомительный характер.  
        Для точного расчета обратитесь к таможенному брокеру.*
        """)


def render_error_state(error_message: str):
    """Отображает ошибку в боковой панели"""
    with st.sidebar:
        st.error(f"❌ {error_message}")
        st.warning("Проверьте интернет-соединение и обновите страницу")