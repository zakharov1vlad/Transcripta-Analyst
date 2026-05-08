import pandas as pd
from db.queries import fetch_df, fetch_one

def get_transcriptions_today(date_str: str = None) -> int:
    """Транскрипции за дату date_str (МСК), по умолчанию — сегодня."""
    d = f"'{date_str}'" if date_str else "DATE(CONVERT_TZ(NOW(), '+00:00', '+03:00'))"
    return fetch_one(f"""
        SELECT COUNT(*) FROM transcriptions
        WHERE DATE(CONVERT_TZ(created_at, '+00:00', '+03:00')) = {d}
    """) or 0

def get_transcriptions_series(days: int = 30) -> pd.DataFrame:
    return fetch_df("""
        SELECT DATE(CONVERT_TZ(t.created_at, '+00:00', '+03:00')) as date,
               COUNT(*) as count,
               ROUND(SUM(COALESCE(t.duration, 0)) / 60, 1) as minutes
        FROM transcriptions t
        JOIN users u ON u.id = t.user_id
        WHERE COALESCE(u.is_test, '0') != '1'
          AND t.created_at >= DATE_SUB(DATE(CONVERT_TZ(NOW(), '+00:00', '+03:00')), INTERVAL :days DAY)
        GROUP BY DATE(CONVERT_TZ(t.created_at, '+00:00', '+03:00'))
        ORDER BY date
    """, {"days": days})

def get_transcriptions_hours_today(date_str: str = None) -> float:
    """Часов расшифровано за дату date_str (МСК), по умолчанию — сегодня."""
    d = f"'{date_str}'" if date_str else "DATE(CONVERT_TZ(NOW(), '+00:00', '+03:00'))"
    result = fetch_one(f"""
        SELECT ROUND(SUM(COALESCE(duration, 0)) / 3600, 2)
        FROM transcriptions
        WHERE DATE(CONVERT_TZ(created_at, '+00:00', '+03:00')) = {d}
    """)
    return float(result) if result else 0.0

def get_transcriptions_minutes_today() -> float:
    return get_transcriptions_hours_today() * 60

def get_ai_reports_today(date_str: str = None) -> int:
    """AI-отчёты за дату date_str (МСК), по умолчанию — сегодня."""
    d = f"'{date_str}'" if date_str else "DATE(CONVERT_TZ(NOW(), '+00:00', '+03:00'))"
    return fetch_one(f"""
        SELECT COUNT(*) FROM ai_reports ar
        JOIN users u ON u.id = ar.user_id
        WHERE COALESCE(u.is_test, '0') != '1'
          AND DATE(CONVERT_TZ(ar.created_at, '+00:00', '+03:00')) = {d}
    """) or 0

def get_chat_messages_today(date_str: str = None) -> int:
    """Сообщений в AI-чат за дату date_str (МСК), по умолчанию — сегодня."""
    d = f"'{date_str}'" if date_str else "DATE(CONVERT_TZ(NOW(), '+00:00', '+03:00'))"
    return fetch_one(f"""
        SELECT COUNT(*) FROM chat_history ch
        JOIN users u ON u.id = ch.user_id
        WHERE COALESCE(u.is_test, '0') != '1'
          AND DATE(CONVERT_TZ(ch.created_at, '+00:00', '+03:00')) = {d}
    """) or 0

def get_total_transcriptions() -> int:
    return fetch_one("""
        SELECT COUNT(*) FROM transcriptions t
        JOIN users u ON u.id = t.user_id
        WHERE COALESCE(u.is_test, '0') != '1'
    """) or 0

def get_media_type_split(days: int = 30) -> pd.DataFrame:
    return fetch_df("""
        SELECT media_type, COUNT(*) as count
        FROM transcriptions t
        JOIN users u ON u.id = t.user_id
        WHERE COALESCE(u.is_test, '0') != '1'
          AND t.created_at >= DATE_SUB(DATE(CONVERT_TZ(NOW(), '+00:00', '+03:00')), INTERVAL :days DAY)
        GROUP BY media_type
    """, {"days": days})

def get_landing_funnel_stats(days: int = 30) -> dict:
    """Конверсия с лендинга: загрузка → регистрация."""
    from_landing = fetch_one("""
        SELECT COUNT(*) FROM transcriptions t
        JOIN users u ON u.id = t.user_id
        WHERE COALESCE(u.is_test, '0') != '1'
          AND t.from_landing_funnel = 1
          AND t.created_at >= DATE_SUB(DATE(CONVERT_TZ(NOW(), '+00:00', '+03:00')), INTERVAL :days DAY)
    """, {"days": days}) or 0

    paid_upsell = fetch_one("""
        SELECT COUNT(*) FROM transcriptions t
        JOIN users u ON u.id = t.user_id
        WHERE COALESCE(u.is_test, '0') != '1'
          AND t.full_transcript_paid = 1
          AND t.created_at >= DATE_SUB(DATE(CONVERT_TZ(NOW(), '+00:00', '+03:00')), INTERVAL :days DAY)
    """, {"days": days}) or 0

    return {"from_landing": from_landing, "paid_upsell": paid_upsell}

def get_ai_reports_series(days: int = 30) -> pd.DataFrame:
    return fetch_df("""
        SELECT DATE(ar.created_at) as date, COUNT(*) as count
        FROM ai_reports ar
        JOIN users u ON u.id = ar.user_id
        WHERE COALESCE(u.is_test, '0') != '1'
          AND ar.created_at >= DATE_SUB(DATE(CONVERT_TZ(NOW(), '+00:00', '+03:00')), INTERVAL :days DAY)
        GROUP BY DATE(ar.created_at)
        ORDER BY date
    """, {"days": days})

def get_chat_usage_series(days: int = 30) -> pd.DataFrame:
    return fetch_df("""
        SELECT DATE(ch.created_at) as date, COUNT(*) as messages
        FROM chat_history ch
        JOIN users u ON u.id = ch.user_id
        WHERE COALESCE(u.is_test, '0') != '1'
          AND ch.created_at >= DATE_SUB(DATE(CONVERT_TZ(NOW(), '+00:00', '+03:00')), INTERVAL :days DAY)
        GROUP BY DATE(ch.created_at)
        ORDER BY date
    """, {"days": days})

def get_avg_transcription_duration(days: int = 30) -> float:
    result = fetch_one("""
        SELECT ROUND(AVG(COALESCE(duration, 0)) / 60, 1)
        FROM transcriptions t
        JOIN users u ON u.id = t.user_id
        WHERE COALESCE(u.is_test, '0') != '1'
          AND t.created_at >= DATE_SUB(DATE(CONVERT_TZ(NOW(), '+00:00', '+03:00')), INTERVAL :days DAY)
          AND t.duration > 0
    """, {"days": days})
    return float(result) if result else 0.0

def get_shared_transcriptions(days: int = 30) -> int:
    return fetch_one("""
        SELECT COUNT(*) FROM transcriptions t
        JOIN users u ON u.id = t.user_id
        WHERE COALESCE(u.is_test, '0') != '1'
          AND t.is_shared = 1
          AND t.created_at >= DATE_SUB(DATE(CONVERT_TZ(NOW(), '+00:00', '+03:00')), INTERVAL :days DAY)
    """, {"days": days}) or 0
