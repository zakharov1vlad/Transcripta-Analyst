import asyncio
from datetime import datetime
from zoneinfo import ZoneInfo

import telegram
from config.settings import TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID
from anomaly.detector import check_all_metrics
from ai_agent.claude import generate_hypotheses
from metrics.users import (
    get_verified_registrations_today, get_new_subscriptions_today,
    get_dau_today, get_active_subscribers, get_mau, get_churn_rate,
)
from metrics.revenue import (
    get_revenue_today, get_revenue_month, get_purchases_today,
    get_arppu, get_arpu, get_ltv,
)
from metrics.product import (
    get_transcriptions_today, get_transcriptions_hours_today,
    get_ai_reports_today, get_chat_messages_today,
)
from metrics.satisfaction import get_avg_review_rating, get_reviews_today
from metrics.direct import get_direct_spend_today

TRANSCRIPTION_COST_USD_PER_HOUR = 0.20
USD_TO_RUB = 90.0


def build_metrics_summary() -> dict:
    msk = ZoneInfo("Europe/Moscow")
    today = datetime.now(msk).strftime("%Y-%m-%d")

    registrations = get_verified_registrations_today()
    new_subs = get_new_subscriptions_today()
    conversion = round(new_subs / registrations * 100, 1) if registrations > 0 else 0.0
    revenue = float(get_revenue_today())
    spend = get_direct_spend_today()
    hours = get_transcriptions_hours_today()
    transcription_cost = round(hours * TRANSCRIPTION_COST_USD_PER_HOUR * USD_TO_RUB, 0)
    profit = round(revenue - spend - transcription_cost, 0)

    return {
        "date": today,
        # Пользователи
        "registrations_verified": registrations,
        "new_subscriptions": new_subs,
        "conversion_reg_to_sub_pct": conversion,
        "dau_active_transcribers": get_dau_today(),
        "active_subscribers_total": get_active_subscribers(),
        "mau": get_mau(),
        "churn_rate_30d_pct": get_churn_rate(30),
        # Финансы
        "purchases_today": get_purchases_today(),
        "revenue_today_rub": revenue,
        "revenue_month_rub": float(get_revenue_month()),
        "direct_spend_rub": spend,
        "transcription_cost_rub": transcription_cost,
        "profit_today_rub": profit,
        "arpu_30d": float(get_arpu(30)),
        "arppu_30d": float(get_arppu(30)),
        "ltv": float(get_ltv()),
        # Продукт
        "transcriptions_today": get_transcriptions_today(),
        "transcription_hours_today": hours,
        "ai_reports_today": get_ai_reports_today(),
        "chat_messages_today": get_chat_messages_today(),
        # Качество
        "avg_rating_7d": float(get_avg_review_rating(7)),
    }


async def send_daily_report():
    msk = ZoneInfo("Europe/Moscow")
    today = datetime.now(msk).strftime("%d.%m.%Y")

    bot = telegram.Bot(token=TELEGRAM_BOT_TOKEN)
    metrics = build_metrics_summary()
    anomalies = check_all_metrics()

    # Генерируем гипотезы
    try:
        hypotheses = generate_hypotheses(metrics, anomalies)
    except Exception as e:
        hypotheses = []
        print(f"Ошибка генерации гипотез: {e}")

    # ── Итоги дня ──────────────────────────────────────────────────────
    profit = metrics["profit_today_rub"]
    profit_str = f"{profit:+,.0f} ₽"

    summary = f"""📅 *Итоги дня — {today}*

👥 *Пользователи*
• Регистраций: {metrics['registrations_verified']:,}
• Новых подписок: {metrics['new_subscriptions']:,}
• Конверсия рег → подписка: {metrics['conversion_reg_to_sub_pct']:.1f}%
• DAU (транскрипции): {metrics['dau_active_transcribers']:,}
• Активных подписок: {metrics['active_subscribers_total']:,}

💰 *Финансы*
• Оплат: {metrics['purchases_today']}
• Выручка: {metrics['revenue_today_rub']:,.0f} ₽
• Расход Директ: {metrics['direct_spend_rub']:,.0f} ₽
• Расход транскрипция: {metrics['transcription_cost_rub']:,.0f} ₽
• Прибыль: {profit_str}

🎙 *Продукт*
• Транскрипций: {metrics['transcriptions_today']:,}
• Расшифровано: {metrics['transcription_hours_today']:.2f} ч
• AI-отчётов: {metrics['ai_reports_today']:,}
• Сообщений AI-чат: {metrics['chat_messages_today']:,}

⭐️ *Средняя оценка (7 дн):* {metrics['avg_rating_7d']:.2f}/5.0"""

    await bot.send_message(chat_id=TELEGRAM_CHAT_ID, text=summary, parse_mode="Markdown")

    # ── Аномалии ───────────────────────────────────────────────────────
    if anomalies:
        anomaly_text = "⚠️ *Аномалии за день:*\n"
        for a in anomalies:
            anomaly_text += f"• {a['metric']}: {a['value']} ({a['direction']} нормы ~{a['expected']})\n"
        await bot.send_message(chat_id=TELEGRAM_CHAT_ID, text=anomaly_text, parse_mode="Markdown")

    # ── Гипотезы и инсайты от Claude ───────────────────────────────────
    if hypotheses:
        priority_emoji = {"high": "🔴", "medium": "🟡", "low": "🟢"}
        hyp_text = f"🧠 *Гипотезы и инсайты на {today}*\n\n"
        for i, h in enumerate(hypotheses[:5], 1):
            emoji = priority_emoji.get(h.get("priority", "medium"), "🟡")
            hyp_text += f"{emoji} *{i}. {h['title']}*\n"
            hyp_text += f"📌 {h['observation']}\n"
            hyp_text += f"💡 {h['hypothesis']}\n"
            hyp_text += f"📏 {h['metric']}\n\n"

        if len(hyp_text) > 4000:
            hyp_text = hyp_text[:4000] + "..."

        await bot.send_message(chat_id=TELEGRAM_CHAT_ID, text=hyp_text, parse_mode="Markdown")


def run():
    asyncio.run(send_daily_report())


if __name__ == "__main__":
    run()
