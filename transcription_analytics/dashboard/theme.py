PRIMARY = "#4F46E5"      # синий
SECONDARY = "#7C3AED"   # фиолетовый
BG = "#0F0F1A"
CARD_BG = "#1A1A2E"
TEXT = "#E2E8F0"
MUTED = "#94A3B8"
SUCCESS = "#10B981"
WARNING = "#F59E0B"
DANGER = "#EF4444"

PLOTLY_TEMPLATE = {
    "layout": {
        "paper_bgcolor": BG,
        "plot_bgcolor": CARD_BG,
        "font": {"color": TEXT, "family": "Inter, sans-serif"},
        "colorway": [PRIMARY, SECONDARY, SUCCESS, WARNING, DANGER,
                     "#06B6D4", "#8B5CF6", "#EC4899"],
        "xaxis": {"gridcolor": "#2D2D44", "linecolor": "#2D2D44"},
        "yaxis": {"gridcolor": "#2D2D44", "linecolor": "#2D2D44"},
        "margin": {"t": 40, "b": 40, "l": 40, "r": 20},
    }
}

STREAMLIT_CSS = f"""
<style>
    .stApp {{ background-color: {BG}; color: {TEXT}; }}
    .metric-card {{
        background: {CARD_BG};
        border: 1px solid #2D2D44;
        border-radius: 12px;
        padding: 20px;
        text-align: center;
    }}
    .metric-value {{ font-size: 2rem; font-weight: 700; color: {PRIMARY}; }}
    .metric-delta-up {{ color: {SUCCESS}; }}
    .metric-delta-down {{ color: {DANGER}; }}
    div[data-testid="stMetric"] {{
        background: {CARD_BG};
        border: 1px solid #2D2D44;
        border-radius: 12px;
        padding: 16px;
    }}
    .stTabs [data-baseweb="tab-list"] {{ background: {CARD_BG}; border-radius: 8px; }}
    .stTabs [data-baseweb="tab"] {{ color: {MUTED}; }}
    .stTabs [aria-selected="true"] {{ color: {PRIMARY}; }}
    div[data-testid="stSidebar"] {{ background: {CARD_BG}; }}
    h1, h2, h3 {{ color: {TEXT}; }}
</style>
"""
