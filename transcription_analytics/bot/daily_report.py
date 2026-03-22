import asyncio
import json
import telegram
from datetime import datetime
from config.settings import TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID
from anomaly.detector import check_all_metrics
from ai_agent.claude import generate_hypotheses
from metrics.users import get_dau_today, get_registrations_today, get_mau, get_active_subscribers, get_churn_rate
from metrics.revenue import get_revenue_today, get_revenue_month, get_arppu, get_arpu, get_ltv
from metrics.product import get_transcriptions_today, get_total_transcriptions
from metrics.satisfaction import get_avg_review_rating

def build_metrics_summary() -> dict:
    return {
        "date": datetime.now().strftime("%Y-%m-%d"),
        "new_users_today": get_dau_today(),
        "registrations_today": get_registrations_today(),
        "mau": get_mau(),
        "active_subscribers": get_active_subscribers(),
        "churn_rate_30d": get_churn_rate(30),
        "revenue_today": float(get_revenue_today()),
        "revenue_month": float(get_revenue_month()),
        "arpu_30d": float(get_arpu(30)),
        "arppu_30d": float(get_arppu(30)),
        "ltv": float(get_ltv()),
        "transcriptions_today": get_transcriptions_today(),
        "total_transcriptions": get_total_transcriptions(),
        "avg_rating_7d": float(get_avg_review_rating(7)),
    }

async def send_daily_report():
    bot = telegram.Bot(token=TELEGRAM_BOT_TOKEN)

    # Собираем метрики и аномалии
    metrics = build_metrics_summary()
    anomalies = check_all_metrics()

    # Генерируем гипотезы через Claude
    try:
        hypotheses = generate_hypotheses(metrics, anomalies)
    except Exception as e:
        hypotheses = []
        print(f"Ошибка генерации гипотез: {e}")

    # Сообщение об аномалиях
    if anomalies:
        anomaly_text = "⚠️ *Обнаружены аномалии:*\n"
        for a in anomalies:
            anomaly_text += f"• {a['metric']}: {a['value']} ({a['direction']} нормы ~{a['expected']})\n"
        await bot.send_message(chat_id=TELEGRAM_CHAT_ID, text=anomaly_text, parse_mode="Markdown")

    # Гипотезы
    if hypotheses:
        priority_emoji = {"high": "🔴", "medium": "🟡", "low": "🟢"}
        hyp_text = f"🧠 *Продуктовые гипотезы на {datetime.now().strftime('%d.%m.%Y')}*\n\n"
        for i, h in enumerate(hypotheses[:5], 1):
            emoji = priority_emoji.get(h.get("priority", "medium"), "🟡")
            hyp_text += f"{emoji} *{i}. {h['title']}*\n"
            hyp_text += f"📌 {h['observation']}\n"
            hyp_text += f"💡 {h['hypothesis']}\n"
            hyp_text += f"📏 Метрика: {h['metric']}\n\n"

        # Telegram ограничение 4096 символов
        if len(hyp_text) > 4000:
            hyp_text = hyp_text[:4000] + "..."

        await bot.send_message(chat_id=TELEGRAM_CHAT_ID, text=hyp_text, parse_mode="Markdown")

def run():
    asyncio.run(send_daily_report())

if __name__ == "__main__":
    run()
