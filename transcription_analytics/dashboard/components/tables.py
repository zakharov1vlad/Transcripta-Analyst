import streamlit as st
import pandas as pd
from db.queries import fetch_df


@st.cache_data(ttl=3600)
def get_daily_summary(days: int = 30) -> pd.DataFrame:
    """Сводная таблица метрик по дням."""
    df = fetch_df(f"""
        SELECT
            d.date,
            COALESCE(u.new_users, 0) AS new_users,
            COALESCE(t.transcriptions, 0) AS transcriptions,
            COALESCE(t.minutes, 0) AS minutes,
            COALESCE(p.revenue, 0) AS revenue,
            COALESCE(p.purchases, 0) AS purchases
        FROM (
            SELECT DATE_SUB(CURDATE(), INTERVAL n DAY) AS date
            FROM (SELECT 0 n UNION SELECT 1 UNION SELECT 2 UNION SELECT 3 UNION SELECT 4
                  UNION SELECT 5 UNION SELECT 6 UNION SELECT 7 UNION SELECT 8 UNION SELECT 9
                  UNION SELECT 10 UNION SELECT 11 UNION SELECT 12 UNION SELECT 13 UNION SELECT 14
                  UNION SELECT 15 UNION SELECT 16 UNION SELECT 17 UNION SELECT 18 UNION SELECT 19
                  UNION SELECT 20 UNION SELECT 21 UNION SELECT 22 UNION SELECT 23 UNION SELECT 24
                  UNION SELECT 25 UNION SELECT 26 UNION SELECT 27 UNION SELECT 28 UNION SELECT 29) nums
            WHERE DATE_SUB(CURDATE(), INTERVAL n DAY) >= DATE_SUB(CURDATE(), INTERVAL {days} DAY)
        ) d
        LEFT JOIN (
            SELECT DATE(created_at) AS date, COUNT(*) AS new_users
            FROM users WHERE COALESCE(is_test, '0') != '1'
            GROUP BY DATE(created_at)
        ) u ON u.date = d.date
        LEFT JOIN (
            SELECT DATE(tr.created_at) AS date,
                   COUNT(*) AS transcriptions,
                   SUM(tr.duration_seconds / 60.0) AS minutes
            FROM transcriptions tr JOIN users u2 ON u2.id = tr.user_id
            WHERE COALESCE(u2.is_test, '0') != '1'
            GROUP BY DATE(tr.created_at)
        ) t ON t.date = d.date
        LEFT JOIN (
            SELECT DATE(ph.created_at) AS date,
                   SUM(ph.amount) AS revenue,
                   COUNT(*) AS purchases
            FROM payment_history ph JOIN users u3 ON u3.id = ph.user_id
            WHERE COALESCE(u3.is_test, '0') != '1' AND ph.status = 'succeeded'
            GROUP BY DATE(ph.created_at)
        ) p ON p.date = d.date
        ORDER BY d.date DESC
    """)
    return df


def render_daily_table(days: int = 30):
    st.subheader(f"Метрики по дням (последние {days} дней)")
    df = get_daily_summary(days)
    if df.empty:
        st.info("Нет данных")
        return

    df = df.rename(columns={
        "date": "Дата",
        "new_users": "Новых польз.",
        "transcriptions": "Транскрипций",
        "minutes": "Минут",
        "revenue": "Выручка (₽)",
        "purchases": "Покупок"
    })
    df["Минут"] = df["Минут"].round(1)
    df["Выручка (₽)"] = df["Выручка (₽)"].apply(lambda x: f"{x:,.0f}")
    st.dataframe(df, use_container_width=True, hide_index=True)


def render_cohort_table(pivot: pd.DataFrame, title: str = "Когортная таблица"):
    st.subheader(title)
    if pivot.empty:
        st.info("Нет данных для когортного анализа")
        return
    styled = pivot.style.format("{:.1f}%", na_rep="-").background_gradient(
        cmap="Blues", axis=None, vmin=0, vmax=100
    )
    st.dataframe(styled, use_container_width=True)


def render_segmentation_table(df: pd.DataFrame, title: str):
    st.subheader(title)
    if df.empty:
        st.info("Нет данных")
        return
    st.dataframe(df, use_container_width=True, hide_index=True)
