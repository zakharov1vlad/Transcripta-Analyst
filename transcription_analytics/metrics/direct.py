import pandas as pd
from db.queries import fetch_df, fetch_one


def get_direct_spend_today() -> float:
    """Расход в Яндекс Директ за сегодня (МСК)."""
    result = fetch_one("""
        SELECT COALESCE(SUM(cost), 0)
        FROM campaign_stats_daily
        WHERE stat_date = DATE(CONVERT_TZ(NOW(), '+00:00', '+03:00'))
    """)
    return round(float(result), 2) if result else 0.0


def get_direct_spend_period(days: int = 30) -> float:
    """Расход в Яндекс Директ за период."""
    result = fetch_one("""
        SELECT COALESCE(SUM(cost), 0)
        FROM campaign_stats_daily
        WHERE stat_date >= DATE_SUB(DATE(CONVERT_TZ(NOW(), '+00:00', '+03:00')), INTERVAL :days DAY)
    """, {"days": days})
    return round(float(result), 2) if result else 0.0


def get_direct_spend_series(days: int = 30) -> pd.DataFrame:
    """Динамика расхода в Директ по дням."""
    return fetch_df("""
        SELECT stat_date AS date, SUM(cost) AS spend, SUM(clicks) AS clicks, SUM(impressions) AS impressions
        FROM campaign_stats_daily
        WHERE stat_date >= DATE_SUB(DATE(CONVERT_TZ(NOW(), '+00:00', '+03:00')), INTERVAL :days DAY)
        GROUP BY stat_date
        ORDER BY stat_date
    """, {"days": days})


def get_roi_series(days: int = 30) -> pd.DataFrame:
    """ROI по дням: (выручка - расход) / расход * 100."""
    return fetch_df("""
        SELECT
            d.stat_date AS date,
            d.spend,
            COALESCE(r.revenue, 0) AS revenue,
            CASE WHEN d.spend > 0
                 THEN ROUND((COALESCE(r.revenue, 0) - d.spend) / d.spend * 100, 1)
                 ELSE NULL
            END AS roi
        FROM (
            SELECT stat_date, SUM(cost) AS spend
            FROM campaign_stats_daily
            WHERE stat_date >= DATE_SUB(DATE(CONVERT_TZ(NOW(), '+00:00', '+03:00')), INTERVAL :days DAY)
            GROUP BY stat_date
        ) d
        LEFT JOIN (
            SELECT DATE(CONVERT_TZ(ph.created_at, '+00:00', '+03:00')) AS dt, SUM(ph.amount) AS revenue
            FROM payment_history ph
            JOIN users u ON u.id = ph.user_id
            WHERE COALESCE(u.is_test, '0') != '1' AND ph.status = 'succeeded'
              AND ph.created_at >= DATE_SUB(DATE(CONVERT_TZ(NOW(), '+00:00', '+03:00')), INTERVAL :days DAY)
            GROUP BY DATE(CONVERT_TZ(ph.created_at, '+00:00', '+03:00'))
        ) r ON r.dt = d.stat_date
        ORDER BY d.stat_date
    """, {"days": days})


def get_roi_today() -> float | None:
    """ROI за сегодня."""
    from metrics.revenue import get_revenue_today
    spend = get_direct_spend_today()
    if spend == 0:
        return None
    revenue = float(get_revenue_today())
    return round((revenue - spend) / spend * 100, 1)


def get_direct_campaigns_today() -> pd.DataFrame:
    """Топ кампаний по расходу сегодня."""
    return fetch_df("""
        SELECT campaign_name, SUM(cost) AS spend, SUM(clicks) AS clicks, SUM(impressions) AS impressions
        FROM campaign_stats_daily
        WHERE stat_date = DATE(CONVERT_TZ(NOW(), '+00:00', '+03:00'))
        GROUP BY campaign_name
        ORDER BY spend DESC
        LIMIT 10
    """)
