import asyncio
import logging
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import telegram
from telegram.request import HTTPXRequest
from config.settings import TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID
from db.queries import fetch_one, fetch_df
from metrics.users import get_activations_today, get_dau_today, get_total_users, get_active_subscribers
from metrics.international import get_intl_payments_today, format_intl_payment
from metrics.product import (
    get_transcriptions_today,
    get_transcriptions_hours_today,
    get_ai_reports_today,
    get_chat_messages_today,
)
from metrics.direct import get_direct_spend_today

logger = logging.getLogger(__name__)

# Одна неудачная отправка = пропущенный час (ретраев не было до 04.08.2026).
# За 21.05–04.08 так потерялось 10 часов: сеть/DNS на VPS, лежащая БД, таймауты Telegram.
SEND_ATTEMPTS = 3
SEND_RETRY_DELAYS = (5, 20)  # пауза перед 2-й и 3-й попыткой, сек


def _get_new_subscribers_today(d: str) -> int:
    """Первичные подписки за дату d (первая оплата юзера, не минуты, не autopay).

    Возвраты не учитываются (см. _get_payment_breakdown_today).
    """
    return fetch_one(f"""
        SELECT COUNT(*)
        FROM payment_history ph
        JOIN users u ON u.id = ph.user_id
        INNER JOIN (
            SELECT user_id, MIN(id) AS first_id
            FROM payment_history
            WHERE status = 'succeeded'
              AND refunded_at IS NULL
              AND plan_name != 'Дополнительные минуты'
              AND is_autopay = 0
            GROUP BY user_id
        ) fp ON fp.user_id = ph.user_id AND fp.first_id = ph.id
        WHERE COALESCE(u.is_test, '0') != '1'
          AND ph.status = 'succeeded'
          AND ph.refunded_at IS NULL
          AND DATE(CONVERT_TZ(ph.created_at, '+00:00', '+03:00')) = '{d}'
    """) or 0


def _get_autopays_for_day(d: str) -> dict:
    """Автопродления за дату d — 1:1 методика дашборда DataLens (датасет «Autopays»,
    вкладка Cohort-Payments). Возвращает:
      plan_total  — ожидаемые списания (все запланированные продления этого дня),
      plan_auto   — из них с включённым автопродлением,
      plan_amount — сумма ожидаемых списаний, ₽ (цена тарифа из `plans` по `users.plan_id`,
                    годовая/месячная по subscription_type; фолбэк — сумма прошлой оплаты),
      fact_paid   — фактически прошедшие (нашлась оплата в ±2 дня от плана),
      conversion  — fact_paid/plan_total, %.

    ВАЖНО: расписание НЕ берётся из active_subscriptions.end_date (оно уже сдвинуто
    вперёд у продлившихся, поэтому наивный запрос давал заниженные/неверные цифры).
    Дашборд восстанавливает график из payment_history + 1 месяц (monthly) + orphan-
    autopay, плюс будущие active_subscriptions (для сегодня даёт 0 — там end_date
    строго > today). Именно поэтому эти числа совпадают с бордом «Autopays user».

    Возвращённые оплаты (refunded_at IS NOT NULL) не создают плана продления и не
    считаются фактическим списанием — как в датасете «Autopays» дашборда.

    ⚠️ Ветка 1 (будущие active_subscriptions) считает только ПЛАТНЫЕ подписки:
    `a.plan_name NOT IN ('Бесплатный','Гостевой')`. С переходом на биллинг
    monthly_refill (снятие стены регистрации, ~27.07.2026) бесплатным юзерам стали
    писать active_subscriptions с будущим end_date → без фильтра ветка 1 раздувала
    «ожидаемые списания» на будущие дни до 400-650/день (21 900+ строк 'Бесплатный',
    auto_renewal=0, цена 0). Списание = только с платного тарифа. Фикс синхронен с
    датасетами DataLens «Autopays»/«Autopays user» (2026-07-31).
    """
    row = fetch_df(f"""
        SELECT
            COALESCE(SUM(plan_count), 0)                            AS plan_total,
            COALESCE(SUM(plan_auto), 0)                             AS plan_auto,
            COALESCE(SUM(plan_amount_total), 0)                     AS plan_amount_total,
            COALESCE(SUM(fact_count), 0)                            AS fact_paid,
            ROUND(SUM(fact_count) / NULLIF(SUM(plan_count), 0) * 100, 1) AS conversion
        FROM (
            /* 1) Будущие: active_subscriptions (для today = 0, end_date строго > today).
               Только платные тарифы — иначе бесплатные (monthly_refill) раздувают план. */
            SELECT DATE(CONVERT_TZ(a.end_date, '+00:00', '+03:00')) AS day, 1 AS plan_count,
                CASE WHEN a.auto_renewal = 1 THEN 1 ELSE 0 END AS plan_auto,
                COALESCE(CASE WHEN u.subscription_type = 'yearly' THEN pl.yearly_price
                              ELSE pl.monthly_price END, 0) AS plan_amount_total,
                0 AS fact_count
            FROM active_subscriptions a JOIN users u ON u.id = a.user_id
            LEFT JOIN plans pl ON pl.id = u.plan_id
            WHERE COALESCE(u.is_test, '0') != '1'
              AND a.plan_name NOT IN ('Бесплатный', 'Гостевой')
              AND DATE(CONVERT_TZ(a.end_date, '+00:00', '+03:00')) > DATE(CONVERT_TZ(NOW(), '+00:00', '+03:00'))

            UNION ALL

            /* 2) Прошлые: оплата + 1 месяц (только monthly) */
            SELECT DATE(CONVERT_TZ(DATE_ADD(ph.created_at, INTERVAL 1 MONTH), '+00:00', '+03:00')) AS day, 1 AS plan_count,
                MAX(CASE WHEN COALESCE(a.auto_renewal, 0) = 1 THEN 1 ELSE 0 END) AS plan_auto,
                MAX(COALESCE(pl.monthly_price, ph.amount)) AS plan_amount_total,
                MAX(CASE WHEN ph2.id IS NOT NULL THEN 1 ELSE 0 END) AS fact_count
            FROM payment_history ph JOIN users u ON u.id = ph.user_id
            LEFT JOIN plans pl ON pl.id = u.plan_id
            LEFT JOIN active_subscriptions a ON a.user_id = ph.user_id
            LEFT JOIN payment_history ph2 ON ph2.user_id = ph.user_id AND ph2.id != ph.id
                AND ph2.status = 'succeeded' AND ph2.refunded_at IS NULL
                AND ph2.plan_name != 'Дополнительные минуты'
                AND DATE(CONVERT_TZ(ph2.created_at, '+00:00', '+03:00'))
                    BETWEEN DATE_SUB(DATE(CONVERT_TZ(DATE_ADD(ph.created_at, INTERVAL 1 MONTH), '+00:00', '+03:00')), INTERVAL 2 DAY)
                        AND DATE_ADD(DATE(CONVERT_TZ(DATE_ADD(ph.created_at, INTERVAL 1 MONTH), '+00:00', '+03:00')), INTERVAL 2 DAY)
            WHERE ph.status = 'succeeded' AND ph.refunded_at IS NULL
              AND ph.plan_name != 'Дополнительные минуты'
              AND COALESCE(u.is_test, '0') != '1' AND COALESCE(a.subscription_type, 'monthly') != 'yearly'
              AND DATE(CONVERT_TZ(DATE_ADD(ph.created_at, INTERVAL 1 MONTH), '+00:00', '+03:00')) <= DATE(CONVERT_TZ(NOW(), '+00:00', '+03:00'))
            GROUP BY ph.id, ph.user_id, DATE(CONVERT_TZ(DATE_ADD(ph.created_at, INTERVAL 1 MONTH), '+00:00', '+03:00'))

            UNION ALL

            /* 3) Orphan autopay (списание есть, но плана под него нет) */
            SELECT DATE(CONVERT_TZ(ap.created_at, '+00:00', '+03:00')) AS day, 1 AS plan_count, 1 AS plan_auto,
                COALESCE(CASE WHEN u.subscription_type = 'yearly' THEN pl.yearly_price
                              ELSE pl.monthly_price END, ap.amount) AS plan_amount_total,
                1 AS fact_count
            FROM payment_history ap JOIN users u ON u.id = ap.user_id
            LEFT JOIN plans pl ON pl.id = u.plan_id
            WHERE ap.status = 'succeeded' AND ap.refunded_at IS NULL
              AND ap.plan_name != 'Дополнительные минуты' AND ap.is_autopay = 1
              AND COALESCE(u.is_test, '0') != '1'
              AND NOT EXISTS (SELECT 1 FROM payment_history prev WHERE prev.user_id = ap.user_id AND prev.id != ap.id
                  AND prev.status = 'succeeded' AND prev.refunded_at IS NULL
                  AND prev.plan_name != 'Дополнительные минуты'
                  AND DATE(CONVERT_TZ(ap.created_at, '+00:00', '+03:00'))
                      BETWEEN DATE_SUB(DATE(CONVERT_TZ(DATE_ADD(prev.created_at, INTERVAL 1 MONTH), '+00:00', '+03:00')), INTERVAL 2 DAY)
                          AND DATE_ADD(DATE(CONVERT_TZ(DATE_ADD(prev.created_at, INTERVAL 1 MONTH), '+00:00', '+03:00')), INTERVAL 2 DAY))
        ) src
        WHERE day = '{d}'
    """)
    r = row.iloc[0]
    return {
        "plan_total": int(r["plan_total"] or 0),
        "plan_auto": int(r["plan_auto"] or 0),
        "plan_amount": float(r["plan_amount_total"] or 0),
        "fact_paid": int(r["fact_paid"] or 0),
        "conversion": float(r["conversion"] or 0),
    }


def _get_payment_breakdown_today(d: str) -> dict:
    """Разбивка оплат: первичные / повторные / минуты за дату d — НЕТТО, без возвратов.

    Возврат в БД = `payment_history.refunded_at IS NOT NULL` (status при этом остаётся
    'succeeded', поэтому фильтра по статусу мало). Правило нетто — как в датасетах
    дашборда DataLens (knowledge/datalens/, data/datalens-refunds/*.sql): возвращённая
    оплата исчезает из дня, в котором прошла.
    """
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
              AND refunded_at IS NULL
              AND plan_name != 'Дополнительные минуты'
              AND is_autopay = 0
            GROUP BY user_id
        ) fp ON fp.user_id = ph.user_id
        WHERE COALESCE(u.is_test, '0') != '1'
          AND ph.status = 'succeeded'
          AND ph.refunded_at IS NULL
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
    # «Активации» (не «регистрации»): со снятия стены регистрации 27.07.2026 строка в
    # `users` создаётся при любом из трёх входов — регистрация / первая транскрибация
    # гостя / начало оплаты гостем. Разбивка — по канону entry_type СТО.
    # В отчёте разбивка идёт БЕЗ подписей, голыми числами в скобках; порядок закреплён
    # владельцем 25.08.2026 и менять его нельзя:
    #   (транскрибация / регистрация / начало оплаты / прочее).
    total_users = get_total_users()
    active_subs = get_active_subscribers()
    act = get_activations_today(d)
    activations = act["total"]
    new_subs = _get_new_subscribers_today(d)
    conv_new = round(new_subs / activations * 100, 1) if activations > 0 else 0.0

    # СТАРЫЕ ПОЛЬЗОВАТЕЛИ (автопродления — методика дашборда DataLens «Autopays»)
    ap = _get_autopays_for_day(d)
    expected = ap["plan_total"]
    expected_amount = ap["plan_amount"]
    actual = ap["fact_paid"]
    conv_renew = ap["conversion"]

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

    # МЕЖДУНАРОДКА (Scriptario / Paddle) — деньги без налога, страна = рынок сайта.
    # Оплат не было → под заголовком пусто (решение владельца 25.08.2026).
    intl_rows = get_intl_payments_today(d)
    intl_block = "🌍 *МЕЖДУНАРОДКА*"
    if intl_rows:
        intl_block += "\n" + "\n".join(format_intl_payment(row) for row in intl_rows)

    # ОЦЕНКИ
    ratings = _get_ratings_today(d)

    msg = f"""📊 *Transcripta — сводка на {label} МСК*

👥 *НОВЫЕ ПОЛЬЗОВАТЕЛИ*
• Всего юзеров: {total_users:,}
• Активных подписок: {active_subs:,}
• Активации сегодня: {activations} ({act['transcription']} / {act['registration']} / {act['payment']} / {act['other']})
• Новые подписки сегодня: {new_subs}
• Конверсия активация → оплата: {conv_new:.1f}%

🔄 *СТАРЫЕ ПОЛЬЗОВАТЕЛИ*
• Ожидаемые списания: {expected} ({expected_amount:,.0f} ₽)
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

{intl_block}

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
    # Дефолтный read_timeout PTB — 5 с, этого мало: 04.08 отправка оборвалась на 8.8 с.
    bot = telegram.Bot(
        token=TELEGRAM_BOT_TOKEN,
        request=HTTPXRequest(
            connect_timeout=10.0,
            read_timeout=30.0,
            write_timeout=30.0,
            pool_timeout=10.0,
        ),
    )

    msg = None
    for attempt in range(1, SEND_ATTEMPTS + 1):
        try:
            if msg is None:  # собранное сообщение переиспользуем — БД не дёргаем повторно
                msg = build_hourly_message()
            await bot.send_message(
                chat_id=TELEGRAM_CHAT_ID,
                text=msg,
                parse_mode="Markdown"
            )
            if attempt > 1:
                logger.info(f"Hourly report sent on attempt {attempt}/{SEND_ATTEMPTS}")
            return
        except Exception as e:
            if attempt == SEND_ATTEMPTS:
                raise
            delay = SEND_RETRY_DELAYS[attempt - 1]
            logger.warning(
                f"Hourly report attempt {attempt}/{SEND_ATTEMPTS} failed: "
                f"{type(e).__name__}: {e}; retry in {delay}s"
            )
            await asyncio.sleep(delay)


def run():
    asyncio.run(send_hourly_report())


if __name__ == "__main__":
    run()
