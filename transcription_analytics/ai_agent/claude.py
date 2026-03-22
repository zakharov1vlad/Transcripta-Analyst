import json
from datetime import datetime
from typing import List, Dict
import anthropic
from config.settings import ANTHROPIC_API_KEY, HYPOTHESES_FILE

client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)

def generate_hypotheses(metrics_summary: dict, anomalies: List[Dict]) -> List[Dict]:
    """Генерирует продуктовые гипотезы через Claude как лучший CPO."""

    anomalies_text = ""
    if anomalies:
        anomalies_text = "\n\nОБНАРУЖЕННЫЕ АНОМАЛИИ:\n"
        for a in anomalies:
            anomalies_text += f"- {a['metric']}: {a['value']} (ожидалось ~{a['expected']}, {a['direction']} нормы, z-score={a['z_score']})\n"

    prompt = f"""Ты — лучший CPO (Chief Product Officer) SaaS-сервиса транскрибации аудио и видео.

Вот текущие продуктовые метрики за сегодня:
{json.dumps(metrics_summary, ensure_ascii=False, indent=2)}
{anomalies_text}

На основе этих данных сгенерируй 3-5 конкретных продуктовых гипотез. Для каждой гипотезы укажи:
1. Проблему/наблюдение из данных
2. Конкретную гипотезу для проверки
3. Метрику успеха
4. Приоритет (high/medium/low)

Отвечай в формате JSON массива:
[
  {{
    "title": "Краткое название",
    "observation": "Что видно в данных",
    "hypothesis": "Конкретная гипотеза",
    "metric": "Как измерить успех",
    "priority": "high|medium|low"
  }}
]

Только JSON, без лишнего текста."""

    response = client.messages.create(
        model="claude-opus-4-6",
        max_tokens=2000,
        messages=[{"role": "user", "content": prompt}]
    )

    text = response.content[0].text.strip()
    # Убираем markdown если есть
    if text.startswith("```"):
        text = text.split("```")[1]
        if text.startswith("json"):
            text = text[4:]

    hypotheses = json.loads(text)

    # Добавляем timestamp
    for h in hypotheses:
        h["created_at"] = datetime.now().isoformat()

    # Сохраняем
    save_hypotheses(hypotheses)
    return hypotheses

def save_hypotheses(new_hypotheses: List[Dict]):
    """Сохраняет гипотезы в JSON файл (последние 50)."""
    existing = load_hypotheses()
    all_hyp = new_hypotheses + existing
    all_hyp = all_hyp[:50]  # Храним последние 50
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
