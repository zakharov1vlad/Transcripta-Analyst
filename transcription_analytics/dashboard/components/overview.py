import streamlit as st
from dashboard.theme import PRIMARY, SUCCESS, DANGER, MUTED


def metric_card(col, label: str, value: str, delta: str = None, delta_positive: bool = True):
    with col:
        delta_html = ""
        if delta:
            color = SUCCESS if delta_positive else DANGER
            arrow = "▲" if delta_positive else "▼"
            delta_html = f'<div style="font-size:0.85rem; color:{color}; margin-top:4px;">{arrow} {delta}</div>'

        st.markdown(f"""
        <div class="metric-card">
            <div style="font-size:0.8rem; color:{MUTED}; text-transform:uppercase; letter-spacing:0.05em;">{label}</div>
            <div class="metric-value">{value}</div>
            {delta_html}
        </div>
        """, unsafe_allow_html=True)


def render_overview(metrics: dict):
    st.subheader("Ключевые метрики")

    cols = st.columns(3)

    dau = metrics.get("dau_today", 0)
    reg = metrics.get("registrations_today", 0)
    mau = metrics.get("mau", 0)
    subs = metrics.get("active_subscribers", 0)
    revenue_today = metrics.get("revenue_today", 0)
    revenue_month = metrics.get("revenue_month", 0)
    transcriptions = metrics.get("transcriptions_today", 0)
    avg_rating = metrics.get("avg_rating_7d", 0)
    churn = metrics.get("churn_rate_30d", 0)
    arppu = metrics.get("arppu_30d", 0)

    metric_card(cols[0], "DAU (активных сегодня)", f"{dau:,}")
    metric_card(cols[1], "Новых регистраций", f"{reg:,}")
    metric_card(cols[2], "MAU (активных за месяц)", f"{mau:,}")

    cols2 = st.columns(3)
    metric_card(cols2[0], "Выручка сегодня", f"{revenue_today:,.0f} ₽")
    metric_card(cols2[1], "Выручка за месяц", f"{revenue_month:,.0f} ₽")
    metric_card(cols2[2], "Активных подписок", f"{subs:,}")

    cols3 = st.columns(3)
    metric_card(cols3[0], "Транскрипций сегодня", f"{transcriptions:,}")
    metric_card(cols3[1], "Ср. оценка (7 дн)", f"{avg_rating:.2f} / 5.0")
    metric_card(cols3[2], "Churn 30д / ARPPU", f"{churn:.1f}% / {arppu:,.0f}₽")
