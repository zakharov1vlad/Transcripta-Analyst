import pandas as pd
from db.queries import fetch_df, fetch_one

BASE_FILTER = "WHERE COALESCE(u.is_test, '0') != '1'"

# Платные тарифы (source of truth = build/gen_product_finance.py в Marketing Assistant).
# ВАЖНО: в БД free-тарифы называются 'Бесплатный'/'Гостевой', НЕ 'Free' — поэтому
# фильтр "subscription_plan != 'Free'" их НЕ отсекал и раздувал метрики (активные
# подписки, ожидаемые списания, churn). Считаем подписчиком только платный тариф.
PAID_PLANS = ('Базовый', 'Стандартный', 'Экспертный', 'Профессиональный')
_PAID_SQL = "('Базовый','Стандартный','Экспертный','Профессиональный')"

def get_dau_series(days: int = 30) -> pd.DataFrame:
    """DAU за последние N дней."""
    return fetch_df(f"""
        SELECT DATE(CONVERT_TZ(created_at, '+00:00', '+03:00')) as date, COUNT(DISTINCT id) as dau
        FROM users
        WHERE COALESCE(is_test, '0') != '1'
          AND created_at >= DATE_SUB(DATE(CONVERT_TZ(NOW(), '+00:00', '+03:00')), INTERVAL :days DAY)
        GROUP BY DATE(CONVERT_TZ(created_at, '+00:00', '+03:00'))
        ORDER BY date
    """, {"days": days})

def get_dau_today(date_str: str = None) -> int:
    """Уникальные пользователи, сделавшие транскрипцию в дату date_str (МСК), по умолчанию — сегодня."""
    d = f"'{date_str}'" if date_str else "DATE(CONVERT_TZ(NOW(), '+00:00', '+03:00'))"
    return fetch_one(f"""
        SELECT COUNT(DISTINCT t.user_id) FROM transcriptions t
        JOIN users u ON u.id = t.user_id
        WHERE COALESCE(u.is_test, '0') != '1'
          AND DATE(CONVERT_TZ(t.created_at, '+00:00', '+03:00')) = {d}
    """) or 0

def get_verified_registrations_today(date_str: str = None) -> int:
    """Верифицированные регистрации в дату date_str (МСК), по умолчанию — сегодня."""
    d = f"'{date_str}'" if date_str else "DATE(CONVERT_TZ(NOW(), '+00:00', '+03:00'))"
    return fetch_one(f"""
        SELECT COUNT(*) FROM users
        WHERE COALESCE(is_test, '0') != '1'
          AND email_verified = 1
          AND DATE(CONVERT_TZ(created_at, '+00:00', '+03:00')) = {d}
    """) or 0

def get_new_subscriptions_today() -> int:
    """Новые оплаченные подписки сегодня (МСК)."""
    return fetch_one("""
        SELECT COUNT(*) FROM payment_history ph
        JOIN users u ON u.id = ph.user_id
        WHERE COALESCE(u.is_test, '0') != '1'
          AND ph.status = 'succeeded'
          AND ph.refunded_at IS NULL
          AND DATE(CONVERT_TZ(ph.created_at, '+00:00', '+03:00')) = DATE(CONVERT_TZ(NOW(), '+00:00', '+03:00'))
    """) or 0

def get_mau(months_back: int = 1) -> int:
    return fetch_one("""
        SELECT COUNT(DISTINCT id) FROM users
        WHERE COALESCE(is_test, '0') != '1'
          AND created_at >= DATE_SUB(DATE(CONVERT_TZ(NOW(), '+00:00', '+03:00')), INTERVAL :m MONTH)
    """, {"m": months_back}) or 0

def get_wau() -> int:
    return fetch_one("""
        SELECT COUNT(DISTINCT id) FROM users
        WHERE COALESCE(is_test, '0') != '1'
          AND created_at >= DATE_SUB(DATE(CONVERT_TZ(NOW(), '+00:00', '+03:00')), INTERVAL 7 DAY)
    """) or 0

def get_total_users() -> int:
    return fetch_one("SELECT COUNT(*) FROM users WHERE COALESCE(is_test, '0') != '1'") or 0

def get_registrations_series(days: int = 30) -> pd.DataFrame:
    return fetch_df("""
        SELECT DATE(CONVERT_TZ(created_at, '+00:00', '+03:00')) as date, COUNT(*) as registrations
        FROM users
        WHERE COALESCE(is_test, '0') != '1'
          AND created_at >= DATE_SUB(DATE(CONVERT_TZ(NOW(), '+00:00', '+03:00')), INTERVAL :days DAY)
        GROUP BY DATE(CONVERT_TZ(created_at, '+00:00', '+03:00'))
        ORDER BY date
    """, {"days": days})

def get_registrations_today() -> int:
    return fetch_one("""
        SELECT COUNT(*) FROM users
        WHERE COALESCE(is_test, '0') != '1' AND DATE(CONVERT_TZ(created_at, '+00:00', '+03:00')) = DATE(CONVERT_TZ(NOW(), '+00:00', '+03:00'))
    """) or 0

def get_active_subscribers() -> int:
    return fetch_one(f"""
        SELECT COUNT(DISTINCT u.id) FROM users u
        WHERE COALESCE(u.is_test, '0') != '1'
          AND u.subscription_plan IN {_PAID_SQL}
          AND u.subscription_expires_at > NOW()
    """) or 0

def get_churn_rate(days: int = 30) -> float:
    """Процент пользователей у кого истекла подписка и не продлили."""
    expired = fetch_one(f"""
        SELECT COUNT(DISTINCT u.id) FROM users u
        WHERE COALESCE(u.is_test, '0') != '1'
          AND u.subscription_expires_at BETWEEN DATE_SUB(DATE(CONVERT_TZ(NOW(), '+00:00', '+03:00')), INTERVAL :days DAY) AND DATE(CONVERT_TZ(NOW(), '+00:00', '+03:00'))
          AND u.subscription_plan IN {_PAID_SQL}
    """, {"days": days}) or 0

    renewed = fetch_one("""
        SELECT COUNT(DISTINCT ph.user_id) FROM payment_history ph
        JOIN users u ON u.id = ph.user_id
        WHERE COALESCE(u.is_test, '0') != '1'
          AND ph.status = 'succeeded'
          AND ph.refunded_at IS NULL
          AND ph.created_at >= DATE_SUB(DATE(CONVERT_TZ(NOW(), '+00:00', '+03:00')), INTERVAL :days DAY)
    """, {"days": days}) or 0

    if expired == 0:
        return 0.0
    churned = max(0, expired - renewed)
    return round(churned / expired * 100, 2)

def get_retention_series() -> pd.DataFrame:
    """Retention Day 1/7/30 по когортам регистрации (последние 60 дней)."""
    return fetch_df("""
        SELECT
            DATE(CONVERT_TZ(u.created_at, '+00:00', '+03:00')) as cohort_date,
            COUNT(DISTINCT u.id) as cohort_size,
            COUNT(DISTINCT CASE
                WHEN t.created_at >= DATE_ADD(u.created_at, INTERVAL 1 DAY)
                 AND t.created_at < DATE_ADD(u.created_at, INTERVAL 2 DAY)
                THEN t.user_id END) as ret_d1,
            COUNT(DISTINCT CASE
                WHEN t.created_at >= DATE_ADD(u.created_at, INTERVAL 7 DAY)
                 AND t.created_at < DATE_ADD(u.created_at, INTERVAL 8 DAY)
                THEN t.user_id END) as ret_d7,
            COUNT(DISTINCT CASE
                WHEN t.created_at >= DATE_ADD(u.created_at, INTERVAL 30 DAY)
                 AND t.created_at < DATE_ADD(u.created_at, INTERVAL 31 DAY)
                THEN t.user_id END) as ret_d30
        FROM users u
        LEFT JOIN transcriptions t ON t.user_id = u.id
        WHERE COALESCE(u.is_test, '0') != '1'
          AND u.created_at >= DATE_SUB(DATE(CONVERT_TZ(NOW(), '+00:00', '+03:00')), INTERVAL 60 DAY)
        GROUP BY DATE(CONVERT_TZ(u.created_at, '+00:00', '+03:00'))
        ORDER BY cohort_date
    """)

def get_plan_distribution() -> pd.DataFrame:
    return fetch_df("""
        SELECT subscription_plan, COUNT(*) as count
        FROM users
        WHERE COALESCE(is_test, '0') != '1'
        GROUP BY subscription_plan
        ORDER BY count DESC
    """)

def get_subscription_type_split() -> pd.DataFrame:
    return fetch_df(f"""
        SELECT subscription_type, COUNT(*) as count
        FROM users
        WHERE COALESCE(is_test, '0') != '1' AND subscription_plan IN {_PAID_SQL}
        GROUP BY subscription_type
    """)


def get_activations_today(date_str: str = None) -> dict:
    """Активации за дату date_str (МСК) — ВСЕ нетестовые строки `users`, созданные в этот день.

    Со снятия стены регистрации (27.07.2026) строка в `users` создаётся при любом из
    трёх событий: (1) регистрация, (2) первая транскрибация гостя, (3) начало оплаты
    гостем. Поэтому «регистрации» ≠ строки таблицы, и метрика дня называется
    «Активации» (тот же канон, что «Активированные юзеры» в ежедневном отчёте
    Продукт+Финансы, build/gen_product_finance.py в Marketing Assistant).

    Разбивка = канон `entry_type` СТО (04.08.2026, живёт в датасете DataLens Users):
    смотрим, какое событие произошло РАНЬШЕ —
      registered_at ≤ min(первая транскрипция, первый платёж любого статуса) → «Регистрация»;
      платёж строго раньше обоих                                             → «Начало оплаты»;
      есть транскрипция                                                      → «Транскрибация»;
      ничего из этого                                                        → «Не определено»
      (брошенные загрузки: строка создана, транскрипции так и не появилось).

    Возвращает {'total', 'transcription', 'registration', 'payment', 'other'}.
    """
    d = date_str or None
    day = f"'{d}'" if d else "DATE(CONVERT_TZ(NOW(), '+00:00', '+03:00'))"
    # Диапазон по UTC — чтобы MySQL взял индекс по created_at (МСК-сутки = UTC [d-3ч, d+21ч)).
    df = fetch_df(f"""
        SELECT
            COUNT(*)                                          AS total,
            SUM(entry_type = 'transcription')                 AS transcription,
            SUM(entry_type = 'registration')                  AS registration,
            SUM(entry_type = 'payment')                       AS payment,
            SUM(entry_type = 'other')                         AS other
        FROM (
            SELECT
                CASE
                    WHEN u.registered_at IS NOT NULL
                         AND (first_tr  IS NULL OR u.registered_at <= first_tr)
                         AND (first_pay IS NULL OR u.registered_at <= first_pay)
                        THEN 'registration'
                    WHEN first_pay IS NOT NULL
                         AND (first_tr IS NULL OR first_pay < first_tr)
                         AND (u.registered_at IS NULL OR first_pay < u.registered_at)
                        THEN 'payment'
                    WHEN first_tr IS NOT NULL
                        THEN 'transcription'
                    ELSE 'other'
                END AS entry_type
            FROM (
                SELECT u.id, u.registered_at,
                       (SELECT MIN(t.created_at)  FROM transcriptions  t WHERE t.user_id  = u.id) AS first_tr,
                       (SELECT MIN(ph.created_at) FROM payment_history ph WHERE ph.user_id = u.id) AS first_pay
                FROM users u
                WHERE COALESCE(u.is_test, '0') != '1'
                  AND u.created_at >= DATE_SUB({day}, INTERVAL 3 HOUR)
                  AND u.created_at <  DATE_ADD({day}, INTERVAL 21 HOUR)
                  AND DATE(CONVERT_TZ(u.created_at, '+00:00', '+03:00')) = {day}
            ) u
        ) x
    """)
    r = df.iloc[0]
    return {
        "total":         int(r["total"] or 0),
        "transcription": int(r["transcription"] or 0),
        "registration":  int(r["registration"] or 0),
        "payment":       int(r["payment"] or 0),
        "other":         int(r["other"] or 0),
    }
