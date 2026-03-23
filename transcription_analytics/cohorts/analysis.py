import pandas as pd
from db.queries import fetch_df

def get_weekly_cohorts() -> pd.DataFrame:
    """Retention матрица по неделям регистрации."""
    df = fetch_df("""
        SELECT
            DATE_FORMAT(DATE_SUB(u.created_at, INTERVAL WEEKDAY(u.created_at) DAY), '%Y-%m-%d') as cohort_week,
            DATE_FORMAT(DATE_SUB(t.created_at, INTERVAL WEEKDAY(t.created_at) DAY), '%Y-%m-%d') as activity_week,
            COUNT(DISTINCT u.id) as cohort_size,
            COUNT(DISTINCT t.user_id) as active_users
        FROM users u
        LEFT JOIN transcriptions t ON t.user_id = u.id
            AND t.created_at >= u.created_at
        WHERE COALESCE(u.is_test, '0') != '1'
          AND u.created_at >= DATE_SUB(DATE(CONVERT_TZ(NOW(), '+00:00', '+03:00')), INTERVAL 12 WEEK)
        GROUP BY cohort_week, activity_week
        ORDER BY cohort_week, activity_week
    """)
    if df.empty:
        return df

    # Pivot для heatmap
    cohort_sizes = df.groupby('cohort_week')['cohort_size'].max()
    pivot = df.pivot_table(index='cohort_week', columns='activity_week', values='active_users', aggfunc='sum')

    # Нормализуем по размеру когорты
    for col in pivot.columns:
        pivot[col] = (pivot[col] / cohort_sizes * 100).round(1)

    return pivot

def get_monthly_cohorts() -> pd.DataFrame:
    """Retention матрица по месяцам регистрации."""
    df = fetch_df("""
        SELECT
            DATE_FORMAT(u.created_at, '%Y-%m') as cohort_month,
            DATE_FORMAT(t.created_at, '%Y-%m') as activity_month,
            COUNT(DISTINCT u.id) as cohort_size,
            COUNT(DISTINCT t.user_id) as active_users
        FROM users u
        LEFT JOIN transcriptions t ON t.user_id = u.id
            AND t.created_at >= u.created_at
        WHERE COALESCE(u.is_test, '0') != '1'
          AND u.created_at >= DATE_SUB(DATE(CONVERT_TZ(NOW(), '+00:00', '+03:00')), INTERVAL 12 MONTH)
        GROUP BY cohort_month, activity_month
        ORDER BY cohort_month, activity_month
    """)
    if df.empty:
        return df

    cohort_sizes = df.groupby('cohort_month')['cohort_size'].max()
    pivot = df.pivot_table(index='cohort_month', columns='activity_month', values='active_users', aggfunc='sum')

    for col in pivot.columns:
        pivot[col] = (pivot[col] / cohort_sizes * 100).round(1)

    return pivot

def get_cohort_revenue() -> pd.DataFrame:
    """Выручка по когортам регистрации (месяц)."""
    return fetch_df("""
        SELECT
            DATE_FORMAT(u.created_at, '%Y-%m') as cohort_month,
            DATE_FORMAT(ph.created_at, '%Y-%m') as payment_month,
            COUNT(DISTINCT ph.user_id) as paying_users,
            SUM(ph.amount) as revenue
        FROM users u
        JOIN payment_history ph ON ph.user_id = u.id
        WHERE COALESCE(u.is_test, '0') != '1' AND ph.status = 'succeeded'
          AND u.created_at >= DATE_SUB(DATE(CONVERT_TZ(NOW(), '+00:00', '+03:00')), INTERVAL 12 MONTH)
        GROUP BY cohort_month, payment_month
        ORDER BY cohort_month, payment_month
    """)
