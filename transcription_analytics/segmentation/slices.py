import pandas as pd
from db.queries import fetch_df

def by_plan(days: int = 30) -> pd.DataFrame:
    """Метрики по плану подписки."""
    return fetch_df("""
        SELECT
            u.subscription_plan,
            COUNT(DISTINCT u.id) as users,
            COUNT(DISTINCT t.id) as transcriptions,
            ROUND(SUM(COALESCE(t.duration, 0)) / 60, 1) as minutes,
            COALESCE(SUM(ph.amount), 0) as revenue
        FROM users u
        LEFT JOIN transcriptions t ON t.user_id = u.id
            AND t.created_at >= DATE_SUB(DATE(CONVERT_TZ(NOW(), '+00:00', '+03:00')), INTERVAL :days DAY)
        LEFT JOIN payment_history ph ON ph.user_id = u.id
            AND ph.status = 'succeeded'
            AND ph.created_at >= DATE_SUB(DATE(CONVERT_TZ(NOW(), '+00:00', '+03:00')), INTERVAL :days DAY)
        WHERE COALESCE(u.is_test, '0') != '1'
        GROUP BY u.subscription_plan
        ORDER BY revenue DESC
    """, {"days": days})

def by_utm(days: int = 30) -> pd.DataFrame:
    """Метрики по UTM source."""
    return fetch_df("""
        SELECT
            COALESCE(u.utm_source, 'organic') as utm_source,
            COUNT(DISTINCT u.id) as users,
            COUNT(DISTINCT t.id) as transcriptions,
            COALESCE(SUM(ph.amount), 0) as revenue
        FROM users u
        LEFT JOIN transcriptions t ON t.user_id = u.id
            AND t.created_at >= DATE_SUB(DATE(CONVERT_TZ(NOW(), '+00:00', '+03:00')), INTERVAL :days DAY)
        LEFT JOIN payment_history ph ON ph.user_id = u.id
            AND ph.status = 'succeeded'
            AND ph.created_at >= DATE_SUB(DATE(CONVERT_TZ(NOW(), '+00:00', '+03:00')), INTERVAL :days DAY)
        WHERE COALESCE(u.is_test, '0') != '1'
          AND u.created_at >= DATE_SUB(DATE(CONVERT_TZ(NOW(), '+00:00', '+03:00')), INTERVAL :days DAY)
        GROUP BY utm_source
        ORDER BY users DESC
        LIMIT 20
    """, {"days": days})

def by_subscription_type(days: int = 30) -> pd.DataFrame:
    """Monthly vs Yearly."""
    return fetch_df("""
        SELECT
            COALESCE(u.subscription_type, 'free') as subscription_type,
            COUNT(DISTINCT u.id) as users,
            COALESCE(SUM(ph.amount), 0) as revenue
        FROM users u
        LEFT JOIN payment_history ph ON ph.user_id = u.id
            AND ph.status = 'succeeded'
            AND ph.created_at >= DATE_SUB(DATE(CONVERT_TZ(NOW(), '+00:00', '+03:00')), INTERVAL :days DAY)
        WHERE COALESCE(u.is_test, '0') != '1'
        GROUP BY subscription_type
        ORDER BY revenue DESC
    """, {"days": days})

def by_landing_funnel(days: int = 30) -> pd.DataFrame:
    """Конверсия лендинговой воронки по дням."""
    return fetch_df("""
        SELECT
            DATE(CONVERT_TZ(t.created_at, '+00:00', '+03:00')) as date,
            COUNT(CASE WHEN t.from_landing_funnel = 1 THEN 1 END) as from_landing,
            COUNT(CASE WHEN t.full_transcript_paid = 1 THEN 1 END) as paid_upsell,
            COUNT(*) as total_transcriptions
        FROM transcriptions t
        JOIN users u ON u.id = t.user_id
        WHERE COALESCE(u.is_test, '0') != '1'
          AND t.created_at >= DATE_SUB(DATE(CONVERT_TZ(NOW(), '+00:00', '+03:00')), INTERVAL :days DAY)
        GROUP BY DATE(CONVERT_TZ(t.created_at, '+00:00', '+03:00'))
        ORDER BY date
    """, {"days": days})

def by_utm_campaign(days: int = 30) -> pd.DataFrame:
    return fetch_df("""
        SELECT
            COALESCE(u.utm_campaign, 'none') as utm_campaign,
            COALESCE(u.utm_medium, 'none') as utm_medium,
            COUNT(DISTINCT u.id) as users,
            COALESCE(SUM(ph.amount), 0) as revenue
        FROM users u
        LEFT JOIN payment_history ph ON ph.user_id = u.id
            AND ph.status = 'succeeded'
        WHERE COALESCE(u.is_test, '0') != '1'
          AND u.created_at >= DATE_SUB(DATE(CONVERT_TZ(NOW(), '+00:00', '+03:00')), INTERVAL :days DAY)
          AND u.utm_campaign IS NOT NULL
        GROUP BY utm_campaign, utm_medium
        ORDER BY users DESC
        LIMIT 20
    """, {"days": days})
