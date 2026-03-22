import streamlit as st
import pandas as pd
from ai_agent.claude import load_hypotheses
from dashboard.theme import SUCCESS, WARNING, DANGER, PRIMARY, MUTED, CARD_BG


def render_hypotheses():
    st.subheader("Продуктовые гипотезы от Claude")

    hypotheses = load_hypotheses()

    if not hypotheses:
        st.info("Гипотезы пока не сгенерированы. Они появятся после первого ежедневного отчёта.")
        return

    priority_colors = {"high": DANGER, "medium": WARNING, "low": SUCCESS}
    priority_labels = {"high": "🔴 Высокий", "medium": "🟡 Средний", "low": "🟢 Низкий"}

    # Фильтр по приоритету
    priorities = ["Все"] + ["high", "medium", "low"]
    selected = st.selectbox("Фильтр по приоритету", priorities, format_func=lambda x: priority_labels.get(x, x))

    filtered = hypotheses if selected == "Все" else [h for h in hypotheses if h.get("priority") == selected]

    for i, h in enumerate(filtered[:20], 1):
        priority = h.get("priority", "medium")
        color = priority_colors.get(priority, WARNING)
        label = priority_labels.get(priority, priority)
        created_at = h.get("created_at", "")[:10]

        st.markdown(f"""
        <div style="background:{CARD_BG}; border:1px solid {color}; border-radius:12px; padding:16px; margin-bottom:12px;">
            <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:8px;">
                <strong style="color:{PRIMARY}; font-size:1rem;">{i}. {h.get('title', '')}</strong>
                <span style="color:{color}; font-size:0.8rem;">{label} · {created_at}</span>
            </div>
            <div style="color:#CBD5E1; font-size:0.9rem; margin-bottom:6px;">
                📌 <strong>Наблюдение:</strong> {h.get('observation', '')}
            </div>
            <div style="color:#CBD5E1; font-size:0.9rem; margin-bottom:6px;">
                💡 <strong>Гипотеза:</strong> {h.get('hypothesis', '')}
            </div>
            <div style="color:{MUTED}; font-size:0.85rem;">
                📏 <strong>Метрика успеха:</strong> {h.get('metric', '')}
            </div>
        </div>
        """, unsafe_allow_html=True)

    if len(filtered) == 0:
        st.info("Нет гипотез с выбранным приоритетом")
