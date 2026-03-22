import pandas as pd
from db.queries import fetch_df, fetch_one

def get_revenue_today() -> float:
    return fetch_one("""
        SELECT COALESCE(SUM(ph.amount), 0)
        FROM payment_history ph
        JOIN users u ON u.id = ph.user_id
        WHERE COALESCE(u.is_test, '0') != '1'
          AND ph.status = 'succeeded'
          AND DATE(ph.created_at) = CURDATE()
    """) or 0.0

def get_revenue_series(days: int = 30) -> pd.DataFrame:
    return fetch_df("""
        SELECT DATE(ph.created_at) as date, SUM(ph.amount) as revenue, COUNT(*) as payments
        FROM payment_history ph
        JOIN users u ON u.id = ph.user_id
        WHERE COALESCE(u.is_test, '0') != '1'
          AND ph.status = 'succeeded'
          AND ph.created_at >= DATE_SUB(CURDATE(), INTERVAL :days DAY)
        GROUP BY DATE(ph.created_at)
        ORDER BY date
    """, {"days": days})

def get_revenue_total() -> float:
    return fetch_one("""
        SELECT COALESCE(SUM(ph.amount), 0)
        FROM payment_history ph
        JOIN users u ON u.id = ph.user_id
        WHERE COALESCE(u.is_test, '0') != '1' AND ph.status = 'succeeded'
    """) or 0.0

def get_revenue_month() -> float:
    return fetch_one("""
        SELECT COALESCE(SUM(ph.amount), 0)
        FROM payment_history ph
        JOIN users u ON u.id = ph.user_id
        WHERE COALESCE(u.is_test, '0') != '1'
          AND ph.status = 'succeeded'
          AND ph.created_at >= DATE_FORMAT(CURDATE(), '%Y-%m-01')
    """) or 0.0

def get_arppu(days: int = 30) -> float:
    """ARPPU = revenue / платящие пользователи за период."""
    result = fetch_one("""
        SELECT
            COALESCE(SUM(ph.amount), 0) / NULLIF(COUNT(DISTINCT ph.user_id), 0)
        FROM payment_history ph
        JOIN users u ON u.id = ph.user_id
        WHERE COALESCE(u.is_test, '0') != '1'
          AND ph.status = 'succeeded'
          AND ph.created_at >= DATE_SUB(CURDATE(), INTERVAL :days DAY)
    """, {"days": days})
    return round(float(result), 2) if result else 0.0

def get_arpu(days: int = 30) -> float:
    """ARPU = revenue / все активные пользователи (включая бесплатных)."""
    revenue = fetch_one("""
        SELECT COALESCE(SUM(ph.amount), 0)
        FROM payment_history ph
        JOIN users u ON u.id = ph.user_id
        WHERE COALESCE(u.is_test, '0') != '1'
          AND ph.status = 'succeeded'
          AND ph.created_at >= DATE_SUB(CURDATE(), INTERVAL :days DAY)
    """, {"days": days}) or 0.0

    users = fetch_one("""
        SELECT COUNT(DISTINCT id) FROM users
        WHERE COALESCE(is_test, '0') != '1'
          AND created_at >= DATE_SUB(CURDATE(), INTERVAL :days DAY)
    """, {"days": days}) or 0

    if users == 0:
        return 0.0
    return round(float(revenue) / users, 2)

def get_ltv() -> float:
    """LTV = среднее суммарное revenue по пользователю за всё время."""
    result = fetch_one("""
        SELECT AVG(user_total) FROM (
            SELECT ph.user_id, SUM(ph.amount) as user_total
            FROM payment_history ph
            JOIN users u ON u.id = ph.user_id
            WHERE COALESCE(u.is_test, '0') != '1' AND ph.status = 'succeeded'
            GROUP BY ph.user_id
        ) t
    """)
    return round(float(result), 2) if result else 0.0

def get_purchases_today() -> int:
    return fetch_one("""
        SELECT COUNT(*)
        FROM payment_history ph
        JOIN users u ON u.id = ph.user_id
        WHERE COALESCE(u.is_test, '0') != '1'
          AND ph.status = 'succeeded'
          AND DATE(ph.created_at) = CURDATE()
    """) or 0

def get_purchases_series(days: int = 30) -> pd.DataFrame:
    return fetch_df("""
        SELECT DATE(ph.created_at) as date, COUNT(*) as purchases, SUM(ph.amount) as amount
        FROM payment_history ph
        JOIN users u ON u.id = ph.user_id
        WHERE COALESCE(u.is_test, '0') != '1'
          AND ph.status = 'succeeded'
          AND ph.created_at >= DATE_SUB(CURDATE(), INTERVAL :days DAY)
        GROUP BY DATE(ph.created_at)
        ORDER BY date
    """, {"days": days})

def get_revenue_by_plan(days: int = 30) -> pd.DataFrame:
    return fetch_df("""
        SELECT ph.plan_name, SUM(ph.amount) as revenue, COUNT(*) as purchases
        FROM payment_history ph
        JOIN users u ON u.id = ph.user_id
        WHERE COALESCE(u.is_test, '0') != '1'
          AND ph.status = 'succeeded'
          AND ph.created_at >= DATE_SUB(CURDATE(), INTERVAL :days DAY)
        GROUP BY ph.plan_name
        ORDER BY revenue DESC
    """, {"days": days})

def get_autopay_rate() -> float:
    """Доля платежей через автопродление."""
    total = fetch_one("""
        SELECT COUNT(*) FROM payment_history ph
        JOIN users u ON u.id = ph.user_id
        WHERE COALESCE(u.is_test, '0') != '1' AND ph.status = 'succeeded'
    """) or 0
    auto = fetch_one("""
        SELECT COUNT(*) FROM payment_history ph
        JOIN users u ON u.id = ph.user_id
        WHERE COALESCE(u.is_test, '0') != '1' AND ph.status = 'succeeded' AND ph.is_autopay = 1
    """) or 0
    return round(auto / total * 100, 2) if total > 0 else 0.0
