import asyncio
import json
import os
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import telegram
from config.settings import TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID
from db.queries import fetch_one, fetch_df
from metrics.users import get_verified_registrations_today, get_dau_today, get_total_users, get_active_subscribers
from metrics.product import (
    get_transcriptions_today,
    get_transcriptions_hours_today,
    get_ai_reports_today,
    get_chat_messages_today,
)
from metrics.direct import get_direct_spend_today

_CACHE_FILE = os.path.join(os.path.dirname(__file__), "..", "data", "renewals_cache.json")


def _load_renewals_cache() -> dict:
    try:
        with open(_CACHE_FILE) as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def _save_renewals_cache(cache: dict):
    os.makedirs(os.path.dirname(_CACHE_FILE), exist_ok=True)
    with open(_CACHE_FILE, "w") as f:
        json.dump(cache, f)


def _get_new_subscribers_today(d: str) -> int:
    """Первичные подписки за дату d (первая оплата юзера, не минуты, не autopay)."""
    return fetch_one(f"""
        SELECT COUNT(*)
        FROM payment_history ph
        JOIN users u ON u.id = ph.user_id
        INNER JOIN (
            SELECT user_id, MIN(id) AS first_id
            FROM payment_history
            WHERE status = 'succeeded'
              AND plan_name != 'Дополнительные минуты'
              AND is_autopay = 0
            GROUP BY user_id
        ) fp ON fp.user_id = ph.user_id AND fp.first_id = ph.id
        WHERE COALESCE(u.is_test, '0') != '1'
          AND ph.status = 'succeeded'
          AND DATE(CONVERT_TZ(ph.created_at, '+00:00', '+03:00')) = '{d}'
    """) or 0


def _get_actual_renewals_today(d: str) -> int:
    """Фактические autopay-списания за дату d."""
    return fetch_one(f"""
        SELECT COUNT(*)
        FROM payment_history ph
        JOIN users u ON u.id = ph.user_id
        WHERE COALESCE(u.is_test, '0') != '1'
          AND ph.status = 'succeeded'
          AND ph.is_autopay = 1
          AND ph.plan_name != 'Дополнительные минуты'
          AND DATE(CONVERT_TZ(ph.created_at, '+00:00', '+03:00')) = '{d}'
    """) or 0


def _get_expected_renewals_today(d: str) -> int:
    """Ожидаемые списания за дату d — фиксируется при первом запросе дня (файловый кэш)."""
    cache = _load_renewals_cache()
    if d in cache:
        return cache[d]
    pending = fetch_one(f"""
        SELECT COUNT(*)
        FROM active_subscriptions a
        JOIN users u ON u.id = a.user_id
        WHERE COALESCE(u.is_test, '0') != '1'
          AND DATE(CONVERT_TZ(a.end_date, '+00:00', '+03:00')) = '{d}'
    """) or 0
    actual = _get_actual_renewals_today(d)
    count = pending + actual
    cache[d] = count
    _save_renewals_cache(cache)
    return count


def _get_payment_breakdown_today(d: str) -> dict:
    """Разбивка оплат: первичные / повторные / минуты за дату d."""
    df = fetch_df(f"""
        SELECT
            CASE
                WHEN ph.plan_name = 'Дополнительные минуты' THEN 'minutes'
                WHEN ph.id = fp.first_id THEN 'first'
                ELSE 'repeat'
            END AS ptype,
            COUNT(*)              AS cnt,
            SUM(ph.amount)        AS total,
            ROUND(AVG(ph.amount)) AS avg_check
        FROM payment_history ph
        JOIN users u ON u.id = ph.user_id
        LEFT JOIN (
            SELECT user_id, MIN(id) AS first_id
            FROM payment_history
            WHERE status = 'succeeded'
              AND plan_name != 'Дополнительные минуты'
              AND is_autopay = 0
            GROUP BY user_id
        ) fp ON fp.user_id = ph.user_id
        WHERE COALESCE(u.is_test, '0') != '1'
          AND ph.status = 'succeeded'
          AND DATE(CONVERT_TZ(ph.created_at, '+00:00', '+03:00')) = '{d}'
        GROUP BY ptype
    """)
    result = {}
    for _, row in df.iterrows():
        result[row["ptype"]] = {
            "cnt": int(row["cnt"]),
            "total": float(row["total"] or 0),
            "avg": float(row["avg_check"] or 0),
        }
    for key in ("first", "repeat", "minutes"):
        result.setdefault(key, {"cnt": 0, "total": 0, "avg": 0})
    return result


def _get_dau_old_today(d: str) -> int:
    """DAU по старым пользователям (зарегистрированы ДО даты d)."""
    return fetch_one(f"""
        SELECT COUNT(DISTINCT t.user_id)
        FROM transcriptions t
        JOIN users u ON u.id = t.user_id
        WHERE COALESCE(u.is_test, '0') != '1'
          AND DATE(CONVERT_TZ(t.created_at, '+00:00', '+03:00')) = '{d}'
          AND DATE(CONVERT_TZ(u.created_at, '+00:00', '+03:00')) < '{d}'
    """) or 0


def _get_ratings_today(d: str) -> str:
    """Оценки (rating) из reviews за дату d — через запятую."""
    df = fetch_df(f"""
        SELECT r.rating
        FROM reviews r
        JOIN users u ON u.id = r.user_id
        WHERE COALESCE(u.is_test, '0') != '1'
          AND r.rating IS NOT NULL
          AND DATE(CONVERT_TZ(r.created_at, '+00:00', '+03:00')) = '{d}'
        ORDER BY r.created_at
    """)
    if df.empty:
        return "нет"
    return ", ".join(str(int(r)) for r in df["rating"])


# ── Сборка сообщения ─────────────────────────────────────────────────────────

def build_hourly_message() -> str:
    msk = ZoneInfo("Europe/Moscow")
    now = datetime.now(msk)

    if now.hour == 0:
        report_dt = now - timedelta(days=1)
        d = report_dt.strftime("%Y-%m-%d")
        label = report_dt.strftime("%d.%m.%Y") + " (итог дня)"
    else:
        d = now.strftime("%Y-%m-%d")
        label = now.strftime("%d.%m.%Y %H:%M")

    # НОВЫЕ ПОЛЬЗОВАТЕЛИ
    total_users = get_total_users()
    active_subs = get_active_subscribers()
    registrations = get_verified_registrations_today(d)
    new_subs = _get_new_subscribers_today(d)
    conv_new = round(new_subs / registrations * 100, 1) if registrations > 0 else 0.0

    # СТАРЫЕ ПОЛЬЗОВАТЕЛИ
    expected = _get_expected_renewals_today(d)
    actual = _get_actual_renewals_today(d)
    conv_renew = round(actual / expected * 100, 1) if expected > 0 else 0.0

    # ФИНАНСЫ
    pay = _get_payment_breakdown_today(d)
    f, r, m = pay["first"], pay["repeat"], pay["minutes"]
    revenue = f["total"] + r["total"] + m["total"]
    spend = float(get_direct_spend_today(d) or 0)
    cac = round(spend / new_subs) if new_subs > 0 else 0
    income = revenue - spend

    # ПРОДУКТ
    dau_all = get_dau_today(d)
    dau_old = _get_dau_old_today(d)
    transcriptions = get_transcriptions_today(d)
    hours = float(get_transcriptions_hours_today(d) or 0)
    ai_reports = get_ai_reports_today(d)
    chat_msgs = get_chat_messages_today(d)

    # ОЦЕНКИ
    ratings = _get_ratings_today(d)

    msg = f"""📊 *Transcripta — сводка на {label} МСК*

👥 *НОВЫЕ ПОЛЬЗОВАТЕЛИ*
• Всего юзеров: {total_users:,}
• Активных подписок: {active_subs:,}
• Регистрации сегодня: {registrations}
• Новые подписки сегодня: {new_subs}
• Конверсия рег → оплата: {conv_new:.1f}%

🔄 *СТАРЫЕ ПОЛЬЗОВАТЕЛИ*
• Ожидаемые списания: {expected}
• Фактические списания: {actual}
• Конверсия в списание: {conv_renew:.1f}%

💰 *ФИНАНСЫ*
• Первичные: {f['cnt']} шт / {f['total']:,.0f} ₽ / ср. {f['avg']:,.0f} ₽
• Повторные: {r['cnt']} шт / {r['total']:,.0f} ₽ / ср. {r['avg']:,.0f} ₽
• Минуты: {m['cnt']} шт / {m['total']:,.0f} ₽ / ср. {m['avg']:,.0f} ₽
• Выручка: {revenue:,.0f} ₽
• Расход Директ: {spend:,.0f} ₽
• CAC: {cac:,.0f} ₽
• Доход: {income:+,.0f} ₽

🎙 *ПРОДУКТ*
• DAU всего: {dau_all}
• DAU старые: {dau_old}
• Транскрипций: {transcriptions}
• Часов: {hours:.2f}
• AI-отчётов: {ai_reports}
• AI-сообщений: {chat_msgs}

⭐️ *Оценки*
{ratings}
"""
    return msg


async def send_hourly_report():
    bot = telegram.Bot(token=TELEGRAM_BOT_TOKEN)
    msg = build_hourly_message()
    await bot.send_message(
        chat_id=TELEGRAM_CHAT_ID,
        text=msg,
        parse_mode="Markdown"
    )


def run():
    asyncio.run(send_hourly_report())


if __name__ == "__main__":
    run()
