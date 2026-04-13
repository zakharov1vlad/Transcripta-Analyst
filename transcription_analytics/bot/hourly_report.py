import asyncio
from datetime import datetime
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

TODAY_MSK = "DATE(CONVERT_TZ(NOW(), '+00:00', '+03:00'))"
TODAY_COL = "DATE(CONVERT_TZ({col}, '+00:00', '+03:00')) = " + TODAY_MSK


# ── Новые метрики ────────────────────────────────────────────────────────────

def _get_new_subscribers_today() -> int:
    """Первичные подписки сегодня (первая оплата юзера, не минуты, не autopay)."""
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
          AND {TODAY_COL.format(col='ph.created_at')}
    """) or 0


def _get_expected_renewals_today() -> int:
    """Ожидаемые списания сегодня = ещё не списанные + уже списанные autopay."""
    pending = fetch_one(f"""
        SELECT COUNT(*)
        FROM active_subscriptions a
        JOIN users u ON u.id = a.user_id
        WHERE COALESCE(u.is_test, '0') != '1'
          AND {TODAY_COL.format(col='a.end_date')}
    """) or 0
    actual = _get_actual_renewals_today()
    return pending + actual


def _get_actual_renewals_today() -> int:
    """Фактические autopay-списания сегодня."""
    return fetch_one(f"""
        SELECT COUNT(*)
        FROM payment_history ph
        JOIN users u ON u.id = ph.user_id
        WHERE COALESCE(u.is_test, '0') != '1'
          AND ph.status = 'succeeded'
          AND ph.is_autopay = 1
          AND ph.plan_name != 'Дополнительные минуты'
          AND {TODAY_COL.format(col='ph.created_at')}
    """) or 0


def _get_payment_breakdown_today() -> dict:
    """Разбивка оплат: первичные / повторные / минуты (кол-во, сумма, ср. чек)."""
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
          AND {TODAY_COL.format(col='ph.created_at')}
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


def _get_dau_old_today() -> int:
    """DAU по старым пользователям (зарегистрированы ДО сегодня)."""
    return fetch_one(f"""
        SELECT COUNT(DISTINCT t.user_id)
        FROM transcriptions t
        JOIN users u ON u.id = t.user_id
        WHERE COALESCE(u.is_test, '0') != '1'
          AND {TODAY_COL.format(col='t.created_at')}
          AND DATE(CONVERT_TZ(u.created_at, '+00:00', '+03:00')) < {TODAY_MSK}
    """) or 0


def _get_feedbacks_today() -> list:
    """Оценки из feedbacks за сегодня."""
    df = fetch_df(f"""
        SELECT f.rating, f.message, COALESCE(f.user_name, f.email, '—') AS who
        FROM feedbacks f
        LEFT JOIN users u ON u.id = f.user_id
        WHERE (u.is_test IS NULL OR COALESCE(u.is_test, '0') != '1')
          AND {TODAY_COL.format(col='f.created_at')}
        ORDER BY f.created_at DESC
    """)
    lines = []
    for _, row in df.iterrows():
        r = f"{int(row['rating'])}/5" if row["rating"] else "—"
        msg = str(row["message"]).strip()[:120] if row["message"] else "—"
        lines.append(f"  {r} — {msg}")
    return lines


def _get_surveys_contacts_today() -> list:
    """Контакты (willing_to_call) из surveys за сегодня."""
    df = fetch_df(f"""
        SELECT s.willing_to_call, s.user_email, s.profession
        FROM surveys s
        JOIN users u ON u.id = s.user_id
        WHERE COALESCE(u.is_test, '0') != '1'
          AND {TODAY_COL.format(col='s.created_at')}
          AND s.willing_to_call IS NOT NULL
          AND s.willing_to_call != ''
        ORDER BY s.created_at DESC
    """)
    lines = []
    for _, row in df.iterrows():
        contact = str(row["willing_to_call"]).strip()
        email = str(row["user_email"]).strip() if row["user_email"] else ""
        prof = str(row["profession"]).strip() if row["profession"] else ""
        parts = [contact]
        if email:
            parts.append(email)
        if prof:
            parts.append(prof)
        lines.append(f"  {' | '.join(parts)}")
    return lines


# ── Сборка сообщения ─────────────────────────────────────────────────────────

def build_hourly_message() -> str:
    msk = ZoneInfo("Europe/Moscow")
    now = datetime.now(msk).strftime("%d.%m.%Y %H:%M")

    # НОВЫЕ ПОЛЬЗОВАТЕЛИ
    total_users = get_total_users()
    active_subs = get_active_subscribers()
    registrations = get_verified_registrations_today()
    new_subs = _get_new_subscribers_today()
    conv_new = round(new_subs / registrations * 100, 1) if registrations > 0 else 0.0

    # СТАРЫЕ ПОЛЬЗОВАТЕЛИ
    expected = _get_expected_renewals_today()
    actual = _get_actual_renewals_today()
    conv_renew = round(actual / expected * 100, 1) if expected > 0 else 0.0

    # ФИНАНСЫ
    pay = _get_payment_breakdown_today()
    f, r, m = pay["first"], pay["repeat"], pay["minutes"]
    revenue = f["total"] + r["total"] + m["total"]
    spend = float(get_direct_spend_today() or 0)
    cac = round(spend / new_subs) if new_subs > 0 else 0
    income = revenue - spend

    # ПРОДУКТ
    dau_all = get_dau_today()
    dau_old = _get_dau_old_today()
    transcriptions = get_transcriptions_today()
    hours = float(get_transcriptions_hours_today() or 0)
    ai_reports = get_ai_reports_today()
    chat_msgs = get_chat_messages_today()

    # ОС
    feedbacks = _get_feedbacks_today()
    contacts = _get_surveys_contacts_today()

    fb_block = "\n".join(feedbacks) if feedbacks else "  нет"
    ct_block = "\n".join(contacts) if contacts else "  нет"

    msg = f"""📊 *Transcripta — сводка на {now} МСК*

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

⭐️ *ОС*
{fb_block}

📞 *Контакты*
{ct_block}
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
