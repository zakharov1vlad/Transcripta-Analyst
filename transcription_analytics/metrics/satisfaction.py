import pandas as pd
from db.queries import fetch_df, fetch_one

def get_avg_review_rating(days: int = 30) -> float:
    result = fetch_one("""
        SELECT ROUND(AVG(r.rating), 2)
        FROM reviews r
        JOIN users u ON u.id = r.user_id
        WHERE COALESCE(u.is_test, '0') != '1'
          AND r.created_at >= DATE_SUB(DATE(CONVERT_TZ(NOW(), '+00:00', '+03:00')), INTERVAL :days DAY)
    """, {"days": days})
    return float(result) if result else 0.0

def get_avg_feedback_rating(days: int = 30) -> float:
    result = fetch_one("""
        SELECT ROUND(AVG(f.rating), 2)
        FROM feedbacks f
        LEFT JOIN users u ON u.id = f.user_id
        WHERE (u.is_test IS NULL OR COALESCE(u.is_test, '0') != '1')
          AND f.rating IS NOT NULL
          AND f.created_at >= DATE_SUB(DATE(CONVERT_TZ(NOW(), '+00:00', '+03:00')), INTERVAL :days DAY)
    """, {"days": days})
    return float(result) if result else 0.0

def get_rating_distribution(days: int = 30) -> pd.DataFrame:
    return fetch_df("""
        SELECT r.rating, COUNT(*) as count
        FROM reviews r
        JOIN users u ON u.id = r.user_id
        WHERE COALESCE(u.is_test, '0') != '1'
          AND r.created_at >= DATE_SUB(DATE(CONVERT_TZ(NOW(), '+00:00', '+03:00')), INTERVAL :days DAY)
        GROUP BY r.rating
        ORDER BY r.rating
    """, {"days": days})

def get_reviews_series(days: int = 30) -> pd.DataFrame:
    return fetch_df("""
        SELECT DATE(CONVERT_TZ(r.created_at, '+00:00', '+03:00')) as date,
               COUNT(*) as count,
               ROUND(AVG(r.rating), 2) as avg_rating
        FROM reviews r
        JOIN users u ON u.id = r.user_id
        WHERE COALESCE(u.is_test, '0') != '1'
          AND r.created_at >= DATE_SUB(DATE(CONVERT_TZ(NOW(), '+00:00', '+03:00')), INTERVAL :days DAY)
        GROUP BY DATE(CONVERT_TZ(r.created_at, '+00:00', '+03:00'))
        ORDER BY date
    """, {"days": days})

def get_reviews_count(days: int = 30) -> int:
    return fetch_one("""
        SELECT COUNT(*) FROM reviews r
        JOIN users u ON u.id = r.user_id
        WHERE COALESCE(u.is_test, '0') != '1'
          AND r.created_at >= DATE_SUB(DATE(CONVERT_TZ(NOW(), '+00:00', '+03:00')), INTERVAL :days DAY)
    """, {"days": days}) or 0

def get_feedbacks_count(days: int = 30) -> int:
    return fetch_one("""
        SELECT COUNT(*) FROM feedbacks f
        LEFT JOIN users u ON u.id = f.user_id
        WHERE (u.is_test IS NULL OR COALESCE(u.is_test, '0') != '1')
          AND f.created_at >= DATE_SUB(DATE(CONVERT_TZ(NOW(), '+00:00', '+03:00')), INTERVAL :days DAY)
    """, {"days": days}) or 0

def get_reviews_today() -> pd.DataFrame:
    """Оценки и комментарии за сегодня (МСК)."""
    return fetch_df("""
        SELECT r.rating, r.review_text, u.email
        FROM reviews r
        JOIN users u ON u.id = r.user_id
        WHERE COALESCE(u.is_test, '0') != '1'
          AND DATE(CONVERT_TZ(r.created_at, '+00:00', '+03:00')) = DATE(CONVERT_TZ(NOW(), '+00:00', '+03:00'))
        ORDER BY r.created_at DESC
    """)

def get_recent_reviews(limit: int = 10) -> pd.DataFrame:
    return fetch_df("""
        SELECT r.rating, r.review_text, r.created_at, u.email
        FROM reviews r
        JOIN users u ON u.id = r.user_id
        WHERE COALESCE(u.is_test, '0') != '1' AND r.review_text IS NOT NULL
        ORDER BY r.created_at DESC
        LIMIT :limit
    """, {"limit": limit})
