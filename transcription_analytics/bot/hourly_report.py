import asyncio
import telegram
from config.settings import TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID
from metrics.users import get_dau_today, get_registrations_today, get_active_subscribers
from metrics.revenue import get_revenue_today, get_purchases_today
from metrics.product import get_transcriptions_today, get_transcriptions_minutes_today
from metrics.satisfaction import get_avg_review_rating

def build_hourly_message() -> str:
    from datetime import datetime
    now = datetime.now().strftime("%d.%m.%Y %H:%M")

    dau = get_dau_today()
    registrations = get_registrations_today()
    subscribers = get_active_subscribers()
    revenue = get_revenue_today()
    purchases = get_purchases_today()
    transcriptions = get_transcriptions_today()
    minutes = get_transcriptions_minutes_today()
    rating = get_avg_review_rating(days=7)

    msg = f"""📊 *Transcripta — сводка на {now}*

👥 *Пользователи*
• Новых сегодня: {registrations:,}
• Активных сегодня: {dau:,}
• Активных подписок: {subscribers:,}

💰 *Финансы*
• Выручка сегодня: {revenue:,.0f} ₽
• Покупок сегодня: {purchases}

🎙 *Продукт*
• Транскрипций сегодня: {transcriptions:,}
• Минут расшифровано: {minutes:,.1f}

⭐️ *Качество*
• Ср. оценка (7 дней): {rating:.2f}/5.0
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
