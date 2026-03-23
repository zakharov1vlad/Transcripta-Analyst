import streamlit as st
import sys
import os
import hashlib

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dashboard.theme import STREAMLIT_CSS, PRIMARY, SECONDARY, BG
from dashboard.components.overview import render_overview
from dashboard.components.charts import (
    dau_chart, revenue_chart, transcriptions_chart, rating_series_chart,
    rating_distribution_chart, plan_distribution_chart, media_type_chart,
    utm_chart, cohort_heatmap, arpu_arppu_chart,
    direct_spend_chart, roi_chart, revenue_vs_spend_chart
)
from metrics.direct import get_direct_spend_today, get_direct_spend_period, get_direct_spend_series, get_roi_series, get_roi_today
from dashboard.components.tables import render_daily_table, render_cohort_table, render_segmentation_table
from dashboard.components.hypotheses import render_hypotheses
from db.queries import fetch_df
from metrics.users import (
    get_dau_today, get_registrations_today, get_mau, get_active_subscribers,
    get_churn_rate, get_plan_distribution
)
from metrics.revenue import (
    get_revenue_today, get_revenue_month, get_arppu, get_arpu, get_ltv
)
from metrics.product import (
    get_transcriptions_today, get_transcriptions_minutes_today,
    get_media_type_split, get_landing_funnel_stats
)
from metrics.satisfaction import (
    get_avg_review_rating, get_rating_distribution, get_reviews_series
)
from cohorts.analysis import get_weekly_cohorts
from segmentation.slices import by_utm, by_plan


st.set_page_config(
    page_title="Transcripta Analytics",
    page_icon="🎙",
    layout="wide",
    initial_sidebar_state="expanded"
)

st.markdown(STREAMLIT_CSS, unsafe_allow_html=True)


# ─── Auth ─────────────────────────────────────────────────────────────────────

USERS = {
    "vlad": hashlib.sha256("Tr@nscr1pt@2026!".encode()).hexdigest(),
}

def _check_password(username: str, password: str) -> bool:
    h = USERS.get(username.lower().strip())
    return h is not None and h == hashlib.sha256(password.encode()).hexdigest()

if "authenticated" not in st.session_state:
    st.session_state.authenticated = False

if not st.session_state.authenticated:
    st.markdown(f"<h2 style='color:{PRIMARY}; text-align:center; margin-top:80px;'>🎙 Transcripta Analytics</h2>", unsafe_allow_html=True)
    st.markdown("<p style='text-align:center; color:#94A3B8;'>Введите логин и пароль для доступа</p>", unsafe_allow_html=True)
    col_l, col_c, col_r = st.columns([1, 1, 1])
    with col_c:
        username = st.text_input("Логин", placeholder="vlad")
        password = st.text_input("Пароль", type="password")
        if st.button("Войти", use_container_width=True, type="primary"):
            if _check_password(username, password):
                st.session_state.authenticated = True
                st.rerun()
            else:
                st.error("Неверный логин или пароль")
    st.stop()


# ─── Sidebar ─────────────────────────────────────────────────────────────────

with st.sidebar:
    st.markdown(f"<h2 style='color:{PRIMARY};'>🎙 Transcripta</h2>", unsafe_allow_html=True)
    st.markdown("**Analytics Dashboard**")
    if st.button("Выйти", use_container_width=True):
        st.session_state.authenticated = False
        st.rerun()
    st.divider()

    period_days = st.selectbox(
        "Период",
        [7, 14, 30, 60, 90],
        index=2,
        format_func=lambda x: f"Последние {x} дней"
    )

    st.divider()
    st.caption("Обновление данных: каждый час")


# ─── Cached data loaders ─────────────────────────────────────────────────────

@st.cache_data(ttl=3600)
def load_dau_series(days):
    return fetch_df(f"""
        SELECT DATE(CONVERT_TZ(created_at, '+00:00', '+03:00')) AS date, COUNT(DISTINCT id) AS val
        FROM users WHERE COALESCE(is_test, '0') != '1'
        AND created_at >= DATE_SUB(DATE(CONVERT_TZ(NOW(), '+00:00', '+03:00')), INTERVAL {days} DAY)
        GROUP BY DATE(CONVERT_TZ(created_at, '+00:00', '+03:00')) ORDER BY date
    """)


@st.cache_data(ttl=3600)
def load_revenue_series(days):
    return fetch_df(f"""
        SELECT DATE(CONVERT_TZ(ph.created_at, '+00:00', '+03:00')) AS date, SUM(ph.amount) AS val
        FROM payment_history ph JOIN users u ON u.id = ph.user_id
        WHERE COALESCE(u.is_test, '0') != '1' AND ph.status = 'succeeded'
        AND ph.created_at >= DATE_SUB(DATE(CONVERT_TZ(NOW(), '+00:00', '+03:00')), INTERVAL {days} DAY)
        GROUP BY DATE(CONVERT_TZ(ph.created_at, '+00:00', '+03:00')) ORDER BY date
    """)


@st.cache_data(ttl=3600)
def load_transcriptions_series(days):
    return fetch_df(f"""
        SELECT DATE(CONVERT_TZ(t.created_at, '+00:00', '+03:00')) AS date, COUNT(*) AS val
        FROM transcriptions t JOIN users u ON u.id = t.user_id
        WHERE COALESCE(u.is_test, '0') != '1'
        AND t.created_at >= DATE_SUB(DATE(CONVERT_TZ(NOW(), '+00:00', '+03:00')), INTERVAL {days} DAY)
        GROUP BY DATE(CONVERT_TZ(t.created_at, '+00:00', '+03:00')) ORDER BY date
    """)


@st.cache_data(ttl=3600)
def load_all_metrics():
    return {
        "dau_today": get_dau_today(),
        "registrations_today": get_registrations_today(),
        "mau": get_mau(),
        "active_subscribers": get_active_subscribers(),
        "churn_rate_30d": get_churn_rate(30),
        "revenue_today": float(get_revenue_today()),
        "revenue_month": float(get_revenue_month()),
        "arppu_30d": float(get_arppu(30)),
        "arpu_30d": float(get_arpu(30)),
        "ltv": float(get_ltv()),
        "transcriptions_today": get_transcriptions_today(),
        "avg_rating_7d": float(get_avg_review_rating(7)),
    }


@st.cache_data(ttl=3600)
def load_rating_series(days):
    return get_reviews_series(days)


@st.cache_data(ttl=3600)
def load_rating_distribution(days):
    return get_rating_distribution(days)


@st.cache_data(ttl=3600)
def load_plan_dist():
    return get_plan_distribution()


@st.cache_data(ttl=3600)
def load_media_type(days):
    return get_media_type_split(days)


@st.cache_data(ttl=3600)
def load_utm(days):
    return by_utm(days)


@st.cache_data(ttl=3600)
def load_weekly_cohorts():
    return get_weekly_cohorts()


@st.cache_data(ttl=3600)
def load_direct_spend_series(days):
    return get_direct_spend_series(days)


@st.cache_data(ttl=3600)
def load_roi_series(days):
    return get_roi_series(days)


# ─── Main content ─────────────────────────────────────────────────────────────

st.markdown(f"<h1 style='color:{PRIMARY}; margin-bottom:0;'>🎙 Transcripta Analytics</h1>", unsafe_allow_html=True)
st.caption("Продуктовая аналитика SaaS-сервиса транскрибации")
st.divider()

tabs = st.tabs(["📊 Обзор", "👥 Пользователи", "💰 Финансы", "🎙 Продукт", "🔄 Когорты", "🧠 Гипотезы"])


# ─── Tab: Обзор ───────────────────────────────────────────────────────────────

with tabs[0]:
    metrics = load_all_metrics()
    render_overview(metrics)
    st.divider()

    col1, col2 = st.columns(2)
    with col1:
        df_dau = load_dau_series(period_days)
        if not df_dau.empty:
            st.plotly_chart(dau_chart(df_dau), use_container_width=True, key="dau_overview")

    with col2:
        df_rev = load_revenue_series(period_days)
        if not df_rev.empty:
            st.plotly_chart(revenue_chart(df_rev), use_container_width=True, key="rev_overview")

    render_daily_table(period_days)


# ─── Tab: Пользователи ────────────────────────────────────────────────────────

with tabs[1]:
    st.subheader("Динамика пользователей")

    df_dau2 = load_dau_series(period_days)
    if not df_dau2.empty:
        st.plotly_chart(dau_chart(df_dau2), use_container_width=True, key="dau_users")

    col1, col2 = st.columns(2)
    with col1:
        df_plan = load_plan_dist()
        if not df_plan.empty:
            st.plotly_chart(plan_distribution_chart(df_plan), use_container_width=True, key="plan_dist")

    with col2:
        df_utm_data = load_utm(period_days)
        if not df_utm_data.empty:
            st.plotly_chart(utm_chart(df_utm_data), use_container_width=True, key="utm_chart")

    st.subheader("Воронка лендинга")
    try:
        funnel = get_landing_funnel_stats()
        if funnel:
            import plotly.graph_objects as go
            fig = go.Figure(go.Funnel(
                y=list(funnel.keys()),
                x=list(funnel.values()),
                marker_color=[PRIMARY, SECONDARY, "#06B6D4", "#10B981"]
            ))
            fig.update_layout(**{"paper_bgcolor": "#0F0F1A", "plot_bgcolor": "#1A1A2E",
                                  "font": {"color": "#E2E8F0"}, "title": "Конверсия лендинга"})
            st.plotly_chart(fig, use_container_width=True, key="funnel_chart")
    except Exception:
        pass


# ─── Tab: Финансы ─────────────────────────────────────────────────────────────

with tabs[2]:
    metrics2 = load_all_metrics()
    spend_today = get_direct_spend_today()
    spend_period = get_direct_spend_period(period_days)
    roi_today = get_roi_today()

    col1, col2, col3 = st.columns(3)
    col1.metric("Выручка сегодня", f"{metrics2['revenue_today']:,.0f} ₽")
    col2.metric("Выручка за месяц", f"{metrics2['revenue_month']:,.0f} ₽")
    col3.metric("LTV", f"{metrics2['ltv']:,.0f} ₽")

    col4, col5, col6, col7 = st.columns(4)
    col4.metric("ARPU 30д", f"{metrics2['arpu_30d']:,.0f} ₽")
    col5.metric("ARPPU 30д", f"{metrics2['arppu_30d']:,.0f} ₽")
    col6.metric("Расход Директ сегодня", f"{spend_today:,.0f} ₽" if spend_today > 0 else "н/д")
    col7.metric(f"Расход Директ {period_days}д", f"{spend_period:,.0f} ₽" if spend_period > 0 else "н/д")

    if roi_today is not None:
        st.metric("ROI сегодня", f"{roi_today:+.1f}%", delta=f"{roi_today:+.1f}%")

    st.divider()

    df_rev2 = load_revenue_series(period_days)
    df_spend2 = load_direct_spend_series(period_days)

    if not df_rev2.empty or not df_spend2.empty:
        st.plotly_chart(revenue_vs_spend_chart(df_rev2, df_spend2), use_container_width=True, key="rev_vs_spend")

    col_r1, col_r2 = st.columns(2)
    with col_r1:
        if not df_rev2.empty:
            st.plotly_chart(revenue_chart(df_rev2), use_container_width=True, key="rev_finance")
    with col_r2:
        if not df_spend2.empty:
            st.plotly_chart(direct_spend_chart(df_spend2), use_container_width=True, key="spend_finance")

    df_roi = load_roi_series(period_days)
    if not df_roi.empty and df_roi["roi"].notna().any():
        st.plotly_chart(roi_chart(df_roi), use_container_width=True, key="roi_chart")


# ─── Tab: Продукт ─────────────────────────────────────────────────────────────

with tabs[3]:
    col1, col2 = st.columns(2)

    df_tr = load_transcriptions_series(period_days)
    with col1:
        if not df_tr.empty:
            st.plotly_chart(transcriptions_chart(df_tr), use_container_width=True, key="tr_chart")

    with col2:
        df_media = load_media_type(period_days)
        if not df_media.empty:
            st.plotly_chart(media_type_chart(df_media), use_container_width=True, key="media_chart")

    st.divider()
    st.subheader("Качество (оценки)")

    col3, col4 = st.columns(2)
    df_rating_series = load_rating_series(period_days)
    with col3:
        if not df_rating_series.empty:
            st.plotly_chart(rating_series_chart(df_rating_series), use_container_width=True, key="rating_series")

    df_dist = load_rating_distribution(period_days)
    with col4:
        if df_dist is not None and len(df_dist) > 0:
            st.plotly_chart(rating_distribution_chart(df_dist), use_container_width=True, key="rating_dist")


# ─── Tab: Когорты ─────────────────────────────────────────────────────────────

with tabs[4]:
    try:
        pivot = load_weekly_cohorts()
        if not pivot.empty:
            st.plotly_chart(cohort_heatmap(pivot), use_container_width=True, key="cohort_heatmap")
            render_cohort_table(pivot, "Retention по неделям (%)")
        else:
            st.info("Нет данных для когортного анализа")
    except Exception as e:
        st.error(f"Ошибка загрузки когорт: {e}")


# ─── Tab: Гипотезы ────────────────────────────────────────────────────────────

with tabs[5]:
    render_hypotheses()
