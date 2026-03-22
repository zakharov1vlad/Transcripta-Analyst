import plotly.graph_objects as go
import plotly.express as px
import pandas as pd
from dashboard.theme import PLOTLY_TEMPLATE, PRIMARY, SECONDARY, SUCCESS, WARNING, DANGER, TEXT, CARD_BG


def _apply_template(fig):
    fig.update_layout(**PLOTLY_TEMPLATE["layout"])
    return fig


def dau_chart(df: pd.DataFrame) -> go.Figure:
    """Линейный график DAU по дням."""
    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=df["date"], y=df["val"],
        mode="lines+markers",
        name="DAU",
        line=dict(color=PRIMARY, width=2),
        marker=dict(size=4),
        fill="tozeroy",
        fillcolor=f"rgba(79,70,229,0.1)"
    ))
    fig.update_layout(title="DAU — активные пользователи по дням", xaxis_title="Дата", yaxis_title="Пользователей")
    return _apply_template(fig)


def revenue_chart(df: pd.DataFrame) -> go.Figure:
    """Столбчатый график выручки по дням."""
    fig = go.Figure()
    fig.add_trace(go.Bar(
        x=df["date"], y=df["val"],
        name="Выручка",
        marker_color=SUCCESS,
        opacity=0.85
    ))
    fig.update_layout(title="Выручка по дням (руб)", xaxis_title="Дата", yaxis_title="Руб")
    return _apply_template(fig)


def transcriptions_chart(df: pd.DataFrame) -> go.Figure:
    """График транскрипций по дням."""
    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=df["date"], y=df["val"],
        mode="lines+markers",
        name="Транскрипции",
        line=dict(color=SECONDARY, width=2),
        fill="tozeroy",
        fillcolor="rgba(124,58,237,0.1)"
    ))
    fig.update_layout(title="Транскрипции по дням", xaxis_title="Дата", yaxis_title="Кол-во")
    return _apply_template(fig)


def rating_series_chart(df: pd.DataFrame) -> go.Figure:
    """График среднего рейтинга по дням."""
    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=df["date"], y=df["val"],
        mode="lines+markers",
        name="Ср. оценка",
        line=dict(color=WARNING, width=2),
        marker=dict(size=5)
    ))
    fig.add_hline(y=4.0, line_dash="dash", line_color=DANGER, annotation_text="Порог 4.0")
    fig.update_layout(title="Средний рейтинг по дням", xaxis_title="Дата", yaxis_title="Оценка", yaxis_range=[1, 5])
    return _apply_template(fig)


def rating_distribution_chart(dist: dict) -> go.Figure:
    """Распределение оценок 1–5."""
    labels = [str(k) for k in sorted(dist.keys())]
    values = [dist[int(k)] for k in labels]
    colors = [DANGER, WARNING, WARNING, SUCCESS, SUCCESS]
    fig = go.Figure(go.Bar(
        x=labels, y=values,
        marker_color=colors,
        text=values, textposition="outside"
    ))
    fig.update_layout(title="Распределение оценок (reviews)", xaxis_title="Оценка", yaxis_title="Кол-во")
    return _apply_template(fig)


def plan_distribution_chart(df: pd.DataFrame) -> go.Figure:
    """Pie-chart по тарифным планам."""
    fig = px.pie(df, names="plan", values="cnt", title="Распределение по тарифам",
                 color_discrete_sequence=[PRIMARY, SECONDARY, SUCCESS, WARNING, DANGER, "#06B6D4"])
    fig.update_layout(**PLOTLY_TEMPLATE["layout"])
    return fig


def media_type_chart(df: pd.DataFrame) -> go.Figure:
    """Столбчатый график audio vs video."""
    fig = go.Figure(go.Bar(
        x=df["media_type"], y=df["cnt"],
        marker_color=[PRIMARY, SECONDARY],
        text=df["cnt"], textposition="outside"
    ))
    fig.update_layout(title="Тип медиафайлов (audio / video)", xaxis_title="Тип", yaxis_title="Кол-во")
    return _apply_template(fig)


def utm_chart(df: pd.DataFrame) -> go.Figure:
    """Горизонтальный bar по UTM-источникам."""
    df_sorted = df.sort_values("cnt", ascending=True).tail(10)
    fig = go.Figure(go.Bar(
        x=df_sorted["cnt"], y=df_sorted["utm_source"].astype(str),
        orientation="h",
        marker_color=PRIMARY
    ))
    fig.update_layout(title="Регистрации по UTM-источникам (топ 10)", xaxis_title="Регистраций", yaxis_title="UTM Source")
    return _apply_template(fig)


def cohort_heatmap(pivot: pd.DataFrame) -> go.Figure:
    """Когортный heatmap retention."""
    fig = go.Figure(go.Heatmap(
        z=pivot.values,
        x=pivot.columns.tolist(),
        y=[str(idx) for idx in pivot.index],
        colorscale=[[0, "#1A1A2E"], [0.5, SECONDARY], [1, PRIMARY]],
        text=[[f"{v:.0f}%" if pd.notna(v) else "" for v in row] for row in pivot.values],
        texttemplate="%{text}",
        showscale=True,
        zmin=0, zmax=100
    ))
    fig.update_layout(title="Когортный анализ — Retention (%)", xaxis_title="Неделя", yaxis_title="Когорта")
    return _apply_template(fig)


def arpu_arppu_chart(df_arpu: pd.DataFrame, df_arppu: pd.DataFrame) -> go.Figure:
    """ARPU и ARPPU на одном графике."""
    fig = go.Figure()
    if not df_arpu.empty:
        fig.add_trace(go.Scatter(
            x=df_arpu["date"], y=df_arpu["val"],
            name="ARPU", line=dict(color=SUCCESS, width=2)
        ))
    if not df_arppu.empty:
        fig.add_trace(go.Scatter(
            x=df_arppu["date"], y=df_arppu["val"],
            name="ARPPU", line=dict(color=WARNING, width=2)
        ))
    fig.update_layout(title="ARPU / ARPPU по дням", xaxis_title="Дата", yaxis_title="Руб")
    return _apply_template(fig)
