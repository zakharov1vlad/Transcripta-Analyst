import asyncio
from datetime import datetime
from zoneinfo import ZoneInfo

import telegram
from config.settings import TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID
from metrics.users import (
    get_verified_registrations_today,
    get_new_subscriptions_today,
    get_dau_today,
    get_active_subscribers,
)
from metrics.revenue import get_revenue_today, get_purchases_today
from metrics.product import (
    get_transcriptions_today,
    get_transcriptions_hours_today,
    get_ai_reports_today,
    get_chat_messages_today,
)
from metrics.satisfaction import get_reviews_today
from metrics.direct import get_direct_spend_today

# Стоимость транскрипции: $0.20/час, курс USD/RUB
TRANSCRIPTION_COST_USD_PER_HOUR = 0.20
USD_TO_RUB = 90.0


def build_hourly_message() -> str:
    msk = ZoneInfo("Europe/Moscow")
    now = datetime.now(msk).strftime("%d.%m.%Y %H:%M")

    registrations = get_verified_registrations_today()
    new_subs = get_new_subscriptions_today()
    conversion = round(new_subs / registrations * 100, 1) if registrations > 0 else 0.0
    dau = get_dau_today()
    active_subs = get_active_subscribers()

    purchases = get_purchases_today()
    revenue = get_revenue_today()

    spend = get_direct_spend_today()
    hours = get_transcriptions_hours_today()
    transcription_cost = round(hours * TRANSCRIPTION_COST_USD_PER_HOUR * USD_TO_RUB, 0)
    total_cost = spend + transcription_cost
    profit = round(revenue - total_cost, 0)

    transcriptions = get_transcriptions_today()
    ai_reports = get_ai_reports_today()
    chat_msgs = get_chat_messages_today()

    reviews_df = get_reviews_today()

    # Блок оценок
    if reviews_df.empty:
        reviews_block = "• Оценок сегодня нет"
    else:
        lines = []
        for _, row in reviews_df.iterrows():
            rating = int(row["rating"])
            comment = str(row["review_text"]).strip() if row["review_text"] else "—"
            lines.append(f"• {rating}/5 — {comment}")
        reviews_block = "\n".join(lines)

    msg = f"""📊 *Transcripta — сводка на {now} МСК*

👥 *Пользователи*
• Регистраций сегодня: {registrations:,}
• Подписок сегодня: {new_subs:,}
• Конверсия рег → подписка: {conversion:.1f}%
• DAU (транскрипции): {dau:,}
• Активных подписок: {active_subs:,}

💰 *Финансы*
• Оплат сегодня: {purchases}
• Выручка сегодня: {revenue:,.0f} ₽
• Расход Директ: {spend:,.0f} ₽
• Расход транскрипция: {transcription_cost:,.0f} ₽ ({hours:.2f} ч × ${TRANSCRIPTION_COST_USD_PER_HOUR} × {USD_TO_RUB} ₽)
• Прибыль: {profit:+,.0f} ₽

🎙 *Продукт*
• Транскрипций: {transcriptions:,}
• Расшифровано: {hours:.2f} ч
• AI-отчётов: {ai_reports:,}
• Сообщений AI-чат: {chat_msgs:,}

⭐️ *Оценки сегодня*
{reviews_block}
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
