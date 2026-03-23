import pandas as pd
import numpy as np
from typing import List, Dict
from db.queries import fetch_df

def detect_anomalies(series: pd.Series, metric_name: str, threshold: float = 2.0) -> List[Dict]:
    """Z-score + IQR детектор аномалий."""
    anomalies = []
    if len(series) < 7:
        return anomalies

    # Z-score
    mean = series.mean()
    std = series.std()
    if std == 0:
        return anomalies

    last_val = series.iloc[-1]
    z_score = abs((last_val - mean) / std)

    # IQR
    q1 = series.quantile(0.25)
    q3 = series.quantile(0.75)
    iqr = q3 - q1
    lower = q1 - 1.5 * iqr
    upper = q3 + 1.5 * iqr
    iqr_anomaly = last_val < lower or last_val > upper

    if z_score > threshold or iqr_anomaly:
        direction = "выше" if last_val > mean else "ниже"
        severity = "high" if z_score > 3 else "medium"
        anomalies.append({
            "metric": metric_name,
            "value": round(float(last_val), 2),
            "expected": round(float(mean), 2),
            "z_score": round(float(z_score), 2),
            "direction": direction,
            "severity": severity,
        })

    return anomalies

def check_all_metrics() -> List[Dict]:
    """Проверяет все ключевые метрики на аномалии за последние 30 дней."""
    all_anomalies = []

    # DAU
    try:
        df = fetch_df("""
            SELECT DATE(CONVERT_TZ(created_at, '+00:00', '+03:00')) as date, COUNT(DISTINCT id) as val
            FROM users WHERE COALESCE(is_test, '0') != '1'
            AND created_at >= DATE_SUB(DATE(CONVERT_TZ(NOW(), '+00:00', '+03:00')), INTERVAL 30 DAY)
            GROUP BY DATE(CONVERT_TZ(created_at, '+00:00', '+03:00')) ORDER BY date
        """)
        if not df.empty:
            all_anomalies += detect_anomalies(df['val'], "DAU (новые пользователи)")
    except Exception:
        pass

    # Выручка
    try:
        df = fetch_df("""
            SELECT DATE(CONVERT_TZ(ph.created_at, '+00:00', '+03:00')) as date, SUM(ph.amount) as val
            FROM payment_history ph JOIN users u ON u.id = ph.user_id
            WHERE COALESCE(u.is_test, '0') != '1' AND ph.status = 'succeeded'
            AND ph.created_at >= DATE_SUB(DATE(CONVERT_TZ(NOW(), '+00:00', '+03:00')), INTERVAL 30 DAY)
            GROUP BY DATE(CONVERT_TZ(ph.created_at, '+00:00', '+03:00')) ORDER BY date
        """)
        if not df.empty:
            all_anomalies += detect_anomalies(df['val'], "Выручка (руб)")
    except Exception:
        pass

    # Транскрипции
    try:
        df = fetch_df("""
            SELECT DATE(CONVERT_TZ(t.created_at, '+00:00', '+03:00')) as date, COUNT(*) as val
            FROM transcriptions t JOIN users u ON u.id = t.user_id
            WHERE COALESCE(u.is_test, '0') != '1'
            AND t.created_at >= DATE_SUB(DATE(CONVERT_TZ(NOW(), '+00:00', '+03:00')), INTERVAL 30 DAY)
            GROUP BY DATE(CONVERT_TZ(t.created_at, '+00:00', '+03:00')) ORDER BY date
        """)
        if not df.empty:
            all_anomalies += detect_anomalies(df['val'], "Кол-во транскрипций")
    except Exception:
        pass

    # Средний рейтинг
    try:
        df = fetch_df("""
            SELECT DATE(CONVERT_TZ(r.created_at, '+00:00', '+03:00')) as date, AVG(r.rating) as val
            FROM reviews r JOIN users u ON u.id = r.user_id
            WHERE COALESCE(u.is_test, '0') != '1'
            AND r.created_at >= DATE_SUB(DATE(CONVERT_TZ(NOW(), '+00:00', '+03:00')), INTERVAL 30 DAY)
            GROUP BY DATE(CONVERT_TZ(r.created_at, '+00:00', '+03:00')) ORDER BY date
        """)
        if not df.empty:
            all_anomalies += detect_anomalies(df['val'], "Средний рейтинг")
    except Exception:
        pass

    return all_anomalies
