import json
from datetime import datetime
from typing import List, Dict
import anthropic
from config.settings import ANTHROPIC_API_KEY, HYPOTHESES_FILE

client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)


def generate_hypotheses(metrics_summary: dict, anomalies: List[Dict]) -> List[Dict]:
    """Генерирует продуктовые гипотезы и инсайты через Claude как лучший CPO."""

    anomalies_text = ""
    if anomalies:
        anomalies_text = "\n\nОБНАРУЖЕННЫЕ АНОМАЛИИ:\n"
        for a in anomalies:
            anomalies_text += (
                f"- {a['metric']}: {a['value']} "
                f"(ожидалось ~{a['expected']}, {a['direction']} нормы, z-score={a['z_score']})\n"
            )

    prompt = f"""Ты — опытный CPO SaaS-сервиса транскрибации аудио и видео для бизнеса и частных пользователей.

Вот итоговые метрики за сегодня:
{json.dumps(metrics_summary, ensure_ascii=False, indent=2)}
{anomalies_text}

Контекст продукта:
- Пользователи загружают аудио/видео → получают текстовую транскрипцию
- Монетизация через подписку (месячная/годовая), есть бесплатный план
- Ключевые метрики роста: конверсия регистрации в подписку, удержание, средняя длительность транскрипции
- Реклама через Яндекс Директ

На основе данных за день сгенерируй 5 конкретных продуктовых гипотез или инсайтов.
Опирайся на реальные цифры из метрик — не выдумывай, делай выводы из того, что видишь.

Для каждой гипотезы:
1. Что конкретно видно в данных (observation)
2. Гипотеза — что нужно проверить или изменить (hypothesis)
3. Как измерить результат (metric)
4. Приоритет: high (влияет на выручку/retention), medium (UX/рост), low (эксперимент)

Формат ответа — строго JSON массив без лишнего текста:
[
  {{
    "title": "Краткое название до 60 символов",
    "observation": "Конкретное наблюдение с цифрами из данных",
    "hypothesis": "Конкретная проверяемая гипотеза с ожидаемым результатом",
    "metric": "Метрика успеха и целевое значение",
    "priority": "high|medium|low"
  }}
]"""

    response = client.messages.create(
        model="claude-opus-4-6",
        max_tokens=3000,
        messages=[{"role": "user", "content": prompt}]
    )

    text = response.content[0].text.strip()
    if text.startswith("```"):
        text = text.split("```")[1]
        if text.startswith("json"):
            text = text[4:]

    hypotheses = json.loads(text)

    for h in hypotheses:
        h["created_at"] = datetime.now().isoformat()

    save_hypotheses(hypotheses)
    return hypotheses


def save_hypotheses(new_hypotheses: List[Dict]):
    """Сохраняет гипотезы в JSON файл (последние 100)."""
    existing = load_hypotheses()
    all_hyp = new_hypotheses + existing
    all_hyp = all_hyp[:100]
    with open(HYPOTHESES_FILE, "w", encoding="utf-8") as f:
        json.dump(all_hyp, f, ensure_ascii=False, indent=2)


def load_hypotheses() -> List[Dict]:
    """Загружает сохранённые гипотезы."""
    if not HYPOTHESES_FILE.exists():
        return []
    try:
        with open(HYPOTHESES_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return []
