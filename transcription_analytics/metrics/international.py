"""Международный контур (Scriptario) — оплаты через Paddle.

Продуктовая БД международки — `transcription_ai_scriptario` (на том же MySQL-сервере,
что и RU-контур `transcription_ai`), поэтому запросы идут с явным префиксом схемы.
Методика 1:1 с дашбордом DataLens «Scriptario — CRM International»
(каноны SQL — `data/datalens-intl/*.sql` в проекте Marketing Assistant):

* **Дни — по МСК** (`CONVERT_TZ(+03:00)`), как в RU.
* **Деньги — БЕЗ налога** (решение владельца 2026-08-24): налог (испанский IVA и
  аналоги) собирает и перечисляет Paddle как Merchant of Record, нам он не достаётся.
  Сумма без налога = `metadata.subtotal` (в `payment_history.amount` налог включён).
* **USD** — по курсу самой транзакции Paddle
  (`paddle_transactions.raw_json → details.payout_totals.exchange_rate`, у части
  записей ключи в camelCase); фолбэк — грубый курс BRL/EUR.
* **«Страна» = РЫНОК (языковая версия сайта), а не гео по IP** (решение владельца
  2026-08-14): каскад `transcriptions.locale` → `paddle_customers.raw_json.locale`,
  фолбэк — валюта платежа. Бразильскую версию смотрят и из России, и из Германии,
  поэтому гео по IP отвергнуто осознанно.
* **Возвраты не считаем** (`refunded_at IS NULL`) — как везде в проекте.

⚠️ Оплаты контура на 2026-08-25 — внутренние (партнёр + владелец), флага `is_test`
у них нет. Пока их не пометят, бот показывает их как реальные.
"""

from db.queries import fetch_df

CURRENCY_SIGN = {"USD": "$", "EUR": "€", "BRL": "R$", "RUB": "₽"}
PERIOD_RU = {"monthly": "месячная", "yearly": "годовая"}


def get_intl_payments_today(date_str: str = None) -> list:
    """Успешные (невозвращённые) оплаты международки за дату date_str (МСК).

    Возвращает список словарей: country / plan_name / billing_period /
    amount_net_local / currency / amount_net_usd — по одной записи на оплату,
    в хронологическом порядке.
    """
    d = f"'{date_str}'" if date_str else "DATE(CONVERT_TZ(NOW(), '+00:00', '+03:00'))"
    df = fetch_df(f"""
        SELECT
            CASE WHEN LOWER(uc.lc) LIKE 'pt%' THEN 'Бразилия (BR)'
                 WHEN LOWER(uc.lc) LIKE 'es%' THEN 'Испания (ES)'
                 WHEN LOWER(uc.lc) LIKE 'en%' THEN 'Английская (EN)'
                 ELSE CASE p.currency
                          WHEN 'BRL' THEN 'Бразилия (BR)'
                          WHEN 'EUR' THEN 'Испания (ES)'
                          WHEN 'USD' THEN 'Английская (EN)'
                          ELSE '(страна не определена)' END
            END                                                        AS country,
            p.plan_name                                                AS plan_name,
            COALESCE(pm.billing_period, 'monthly')                     AS billing_period,
            ROUND(COALESCE(
                CAST(JSON_UNQUOTE(JSON_EXTRACT(p.metadata, '$.subtotal')) AS DECIMAL(18,2)),
                p.amount), 2)                                          AS amount_net_local,
            p.currency                                                 AS currency,
            ROUND(COALESCE(
                CAST(JSON_UNQUOTE(JSON_EXTRACT(p.metadata, '$.subtotal')) AS DECIMAL(18,2)),
                p.amount)
                * CASE WHEN p.currency = 'USD' THEN 1 ELSE COALESCE(
                    CAST(JSON_UNQUOTE(JSON_EXTRACT(pt.raw_json, '$.details.payout_totals.exchange_rate')) AS DECIMAL(18,8)),
                    CAST(JSON_UNQUOTE(JSON_EXTRACT(pt.raw_json, '$.details.payoutTotals.exchangeRate'))   AS DECIMAL(18,8)),
                    CASE p.currency WHEN 'BRL' THEN 0.19 WHEN 'EUR' THEN 1.16 END
                  ) END, 2)                                            AS amount_net_usd
        FROM transcription_ai_scriptario.payment_history p
        LEFT JOIN transcription_ai_scriptario.users u2 ON u2.id = p.user_id
        LEFT JOIN transcription_ai_scriptario.paddle_transactions pt
               ON pt.transaction_id = p.paddle_transaction_id
        LEFT JOIN transcription_ai_scriptario.paddle_price_mappings pm
               ON pm.price_id = JSON_UNQUOTE(JSON_EXTRACT(p.metadata, '$.priceId'))
        LEFT JOIN (
            SELECT u.id AS user_id,
                COALESCE(
                  (SELECT SUBSTRING_INDEX(GROUP_CONCAT(t.locale ORDER BY t.id), ',', 1)
                     FROM transcription_ai_scriptario.transcriptions t
                    WHERE t.user_id = u.id AND t.locale IS NOT NULL AND t.locale != ''),
                  (SELECT JSON_UNQUOTE(JSON_EXTRACT(pc.raw_json, '$.locale'))
                     FROM transcription_ai_scriptario.paddle_customers pc
                    WHERE pc.user_id = u.id
                      AND JSON_EXTRACT(pc.raw_json, '$.locale') IS NOT NULL LIMIT 1)
                ) AS lc
            FROM transcription_ai_scriptario.users u
        ) uc ON uc.user_id = p.user_id
        WHERE p.status = 'succeeded'
          AND p.refunded_at IS NULL
          AND p.plan_name != 'Дополнительные минуты'
          AND COALESCE(u2.is_test, '0') != '1'
          AND DATE(CONVERT_TZ(p.created_at, '+00:00', '+03:00')) = {d}
        ORDER BY p.created_at
    """)
    return df.to_dict("records")


def format_intl_payment(row: dict) -> str:
    """Строка отчёта по одной международной оплате."""
    sign = CURRENCY_SIGN.get(row["currency"], row["currency"])
    period = PERIOD_RU.get(row["billing_period"], row["billing_period"])
    local = f"{float(row['amount_net_local']):,.2f} {sign}"
    usd = f"{float(row['amount_net_usd']):,.2f} $" if row["amount_net_usd"] is not None else "— $"
    if row["currency"] == "USD":
        return f"• {row['country']}: {row['plan_name']}, {period} — {local}"
    return f"• {row['country']}: {row['plan_name']}, {period} — {local} / {usd}"
