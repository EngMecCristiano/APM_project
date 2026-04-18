"""
Tema escuro APM — CSS consolidado.
"""
from __future__ import annotations
import base64
from pathlib import Path


def _load_bg(path: Path) -> str | None:
    if path.exists():
        return base64.b64encode(path.read_bytes()).decode()
    return None


def build_css(bg_image_path: Path | None = None) -> str:
    bg_b64 = _load_bg(bg_image_path) if bg_image_path else None
    bg_rule = (
        f'background-image: url("data:image/png;base64,{bg_b64}");'
        if bg_b64 else ""
    )

    return f"""
<style>

/* ── App (fundo global) ─────────────────────────────────────────────────── */
.stApp {{
    {bg_rule}
    background-size: cover;
    background-position: center;
    background-repeat: no-repeat;
    background-attachment: fixed;
    background-color: #020B18;
}}

/* ── Sidebar ─────────────────────────────────────────────────────────────── */
[data-testid="stSidebar"] {{
    background: #071A2B !important;
    border-right: 1px solid rgba(0, 212, 255, 0.18) !important;
}}
[data-testid="stSidebar"] * {{
    color: #DEF7FF !important;
}}

/* ── Texto global ────────────────────────────────────────────────────────── */
body, .stMarkdown, .stMarkdown *,
.stMetric, .stAlert, .stException,
[data-testid="stMetric"],
[data-testid="stMetricLabel"],
[data-testid="stMetricValue"],
[data-testid="stMetricDelta"] {{
    color: #DEF7FF !important;
}}

/* ── Espaçamento vertical entre elementos ───────────────────────────────── */
.stMarkdown h3 {{ margin-top: 1.2rem !important; margin-bottom: 0.4rem !important; }}
.stMarkdown h4 {{ margin-top: 1rem !important;   margin-bottom: 0.3rem !important; }}
[data-testid="stPlotlyChart"]  {{ margin-top: 20px !important; margin-bottom: 8px !important; }}
[data-testid="stMetric"]       {{ margin-bottom: 4px !important; }}
[data-testid="stAlert"]        {{ margin-top: 6px  !important; margin-bottom: 6px !important; }}
hr {{ margin: 10px 0 !important; border-color: rgba(0,212,255,0.15) !important; }}

/* ── Bateria centralizada verticalmente na coluna ───────────────────────── */
[data-testid="stHorizontalBlock"]:has(.battery-container)
  > [data-testid="column"] {{
    display: flex !important;
    align-items: center !important;
    justify-content: center !important;
}}
[data-testid="stHorizontalBlock"]:has(.battery-container) {{
    align-items: stretch !important;
}}

/* ── Abas ───────────────────────────────────────────────────────────────── */
.stTabs [data-baseweb="tab-list"] {{
    background: rgba(0, 0, 0, 0.4);
    border-radius: 12px;
    padding: 6px;
    gap: 4px;
}}
.stTabs [data-baseweb="tab"] {{
    background: transparent;
    border-radius: 8px;
    padding: 7px 18px;
    color: #DEF7FF !important;
    font-size: 13px;
}}
.stTabs [aria-selected="true"] {{
    background: linear-gradient(135deg, #00d4ff, #7b2cbf);
    color: white !important;
}}

/* ── Botões ─────────────────────────────────────────────────────────────── */
.stButton > button {{
    background: linear-gradient(135deg, #00d4ff, #7b2cbf);
    color: white;
    border: none;
    border-radius: 10px;
    font-weight: 600;
    transition: opacity 0.2s;
}}
.stButton > button:hover {{ opacity: 0.85; }}

/* ══ Form Controls — apenas ajustes finos (base via config.toml) ════════ */
/* O config.toml já define: primaryColor, backgroundColor,                  */
/* secondaryBackgroundColor (#071A2B) e textColor. O CSS abaixo só          */
/* ajusta bordas, raio e estados de foco que o config.toml não cobre.       */

/* ── Fundo + borda uniformes em todos os inputs/selects ─────────────────── */
[data-baseweb="input"],
[data-baseweb="select"] > div:first-child {{
    background-color: rgba(7,26,43,0.20) !important;
    border: 1px solid rgba(0,212,255,0.30) !important;
    border-radius: 8px !important;
    overflow: hidden !important;
}}
/* Fundo interno do input também transparente */
[data-baseweb="input"] > div {{
    background-color: transparent !important;
}}
/* Foco nos inputs de texto e select */
[data-baseweb="input"]:focus-within,
[data-baseweb="select"] > div:first-child:focus-within {{
    border-color: rgba(0,212,255,0.75) !important;
    box-shadow: 0 0 0 2px rgba(0,212,255,0.10) !important;
    outline: none !important;
}}

/* Remove bordas redundantes do <input> interno */
[data-baseweb="input"] input {{
    border: none !important;
    outline: none !important;
    box-shadow: none !important;
    font-size: 13px !important;
}}

/* ── Espaçamento uniforme dos campos na sidebar ─────────────────────────── */
/* Zera padding/gap default do Streamlit e aplica gap fixo entre todos       */
/* os filhos diretos do bloco vertical da sidebar                            */
[data-testid="stSidebar"] [data-testid="stVerticalBlock"] {{
    gap: 10px !important;
}}
[data-testid="stSidebar"] .element-container,
[data-testid="stSidebar"] [data-testid="stVerticalBlock"] > div {{
    margin-top: 0 !important;
    margin-bottom: 0 !important;
    padding-top: 0 !important;
    padding-bottom: 0 !important;
}}
/* Labels uniformes */
[data-testid="stSidebar"] label p,
[data-testid="stSidebar"] .stWidgetLabel p {{
    font-size: 12px !important;
    margin-bottom: 2px !important;
    margin-top: 0 !important;
}}

/* ── NumberInput: container real (input + botões juntos) ─────────────────── */
[data-testid="stNumberInputContainer"] {{
    background-color: rgba(7,26,43,0.20) !important;
    border: 1px solid rgba(0,212,255,0.30) !important;
    border-radius: 8px !important;
    overflow: hidden !important;
    display: flex !important;
    align-items: center !important;
}}
[data-testid="stNumberInputContainer"]:focus-within {{
    border-color: rgba(0,212,255,0.75) !important;
    box-shadow: 0 0 0 2px rgba(0,212,255,0.10) !important;
}}
/* Campo do número — sem borda própria */
[data-testid="stNumberInputField"] {{
    background: transparent !important;
    border: none !important;
    outline: none !important;
    box-shadow: none !important;
    color: #DEF7FF !important;
    font-size: 13px !important;
    padding: 7px 10px !important;
    flex: 1;
}}
/* Botões − e + */
[data-testid="stNumberInputStepDown"],
[data-testid="stNumberInputStepUp"] {{
    background: rgba(0,212,255,0.08) !important;
    color: #63DCF7 !important;
    border: none !important;
    border-left: 1px solid rgba(0,212,255,0.18) !important;
    border-radius: 0 !important;
    min-width: 32px !important;
    height: 100% !important;
    transition: background 0.15s;
}}
[data-testid="stNumberInputStepDown"]:hover,
[data-testid="stNumberInputStepUp"]:hover {{
    background: rgba(0,212,255,0.22) !important;
}}
[data-testid="stNumberInputStepDown"] svg,
[data-testid="stNumberInputStepUp"] svg {{
    fill: #63DCF7 !important;
}}
/* Garante que o [data-baseweb="input"] dentro do NumberInput não conflite */
[data-testid="stNumberInputContainer"] [data-baseweb="input"] {{
    background: transparent !important;
    border: none !important;
    border-radius: 0 !important;
    flex: 1;
}}

/* ── Lista de opções do dropdown ─────────────────────────────────────────── */
[data-baseweb="menu"] {{
    background-color: #071A2B !important;
    border: 1px solid rgba(0,212,255,0.25) !important;
    border-radius: 8px !important;
    padding: 4px !important;
}}
[data-baseweb="option"] {{
    border-radius: 6px !important;
    color: #DEF7FF !important;
    font-size: 13px !important;
}}
[data-baseweb="option"]:hover                {{ background: rgba(0,212,255,0.12) !important; }}
[data-baseweb="option"][aria-selected="true"] {{
    background: rgba(0,212,255,0.20) !important;
    color: #63DCF7 !important;
    font-weight: 600 !important;
}}
/* Ícone de seta do select */
[data-baseweb="select"] svg {{ fill: #63DCF7 !important; }}

/* ── Sliders ─────────────────────────────────────────────────────────────── */
div[data-baseweb="slider"] div[role="slider"] {{
    background: #1A5FA8 !important;
    border: 2px solid #63DCF7 !important;
    width: 14px !important;
    height: 14px !important;
}}
div[data-testid="stThumbValue"] {{ color: #63DCF7 !important; font-size: 11px !important; }}

/* ── Radio buttons — só círculo + texto, sem borda nem fundo ────────────── */
.stRadio {{ border: none !important; outline: none !important; }}
.stRadio > div {{ gap: 2px !important; }}
.stRadio label {{
    background: transparent !important;
    border: none !important;
    border-radius: 0 !important;
    padding: 4px 6px !important;
    cursor: pointer;
    outline: none !important;
    box-shadow: none !important;
    font-size: 13px !important;
    color: #DEF7FF !important;
}}
.stRadio label:has(input:checked) {{
    background: transparent !important;
    border: none !important;
    box-shadow: none !important;
    color: #00d4ff !important;
    font-weight: 600 !important;
}}
.stRadio label:focus-within,
.stRadio label:focus,
.stRadio input:focus {{
    outline: none !important;
    box-shadow: none !important;
}}
.stRadio input[type="radio"] {{ accent-color: #00d4ff !important; }}

/* ── Alertas ────────────────────────────────────────────────────────────── */
.stAlert, .stInfo, .stWarning, .stSuccess, .stError {{
    color: #F0FFFF !important;
    background-color: rgba(0, 0, 0, 0.55) !important;
    backdrop-filter: blur(4px);
    margin-top: 6px !important;
}}

/* ── Expander ───────────────────────────────────────────────────────────── */
.stExpander summary, .stExpander p {{ color: #F0FFFF !important; }}
[data-testid="stExpander"] {{
    border: 1px solid rgba(0,212,255,0.15) !important;
    border-radius: 8px !important;
    margin-top: 8px !important;
}}

/* ── Previne reload por pull-to-refresh em qualquer dispositivo ─────────── */
html, body {{
    overscroll-behavior-y: contain !important;
}}

/* ── Mobile (≤ 768px) — sidebar 100%, sem zoom por toque ───────────────── */
@media (max-width: 768px) {{
    section[data-testid="stSidebar"] {{
        width: 100vw !important;
        min-width: 100vw !important;
    }}
    /* Botão de fechar sidebar — área de toque maior, menos chance de erro */
    button[data-testid="baseButton-header"] {{
        background: rgba(0,212,255,0.15) !important;
        border: 1px solid rgba(0,212,255,0.4) !important;
        border-radius: 8px !important;
        color: #63DCF7 !important;
        font-size: 18px !important;
        padding: 12px 20px !important;
        min-width: 48px !important;
        min-height: 48px !important;
    }}
    /* Desativa zoom por pinça nos gráficos Plotly */
    .js-plotly-plot .plotly .main-svg {{
        touch-action: pan-y !important;
    }}
    /* Aumenta área de toque nos sliders */
    div[data-baseweb="slider"] div[role="slider"] {{
        width: 24px !important;
        height: 24px !important;
    }}
    /* Previne cliques acidentais no overlay que fecha a sidebar */
    [data-testid="stSidebarNavItems"] {{
        pointer-events: auto !important;
    }}
}}

/* ── Tablet (769px–1100px) — sidebar mais larga ─────────────────────────── */
@media (min-width: 769px) and (max-width: 1100px) {{
    section[data-testid="stSidebar"] {{
        width: 360px !important;
        min-width: 360px !important;
    }}
}}


/* ── Download Button ────────────────────────────────────────────────────── */
.stDownloadButton button {{
    background: linear-gradient(135deg, #00d4ff22, #7b2cbf22) !important;
    color: #F0FFFF !important;
    border: 1px solid rgba(0,212,255,0.35) !important;
}}

/* ── File Uploader ───────────────────────────────────────────────────────── */
[data-testid="stFileUploader"] {{
    background: rgba(14,55,90,0.25) !important;
    border: 1.5px dashed rgba(0,212,255,0.45) !important;
    border-radius: 12px !important;
    padding: 12px 16px !important;
}}
/* Área interna de drop (era o quadrado preto) */
[data-testid="stFileUploaderDropzone"] {{
    background: rgba(14,55,90,0.35) !important;
    border: 1px dashed rgba(0,212,255,0.30) !important;
    border-radius: 8px !important;
}}
[data-testid="stFileUploader"] * {{ color: #DEF7FF !important; }}
[data-testid="stFileUploader"] button {{
    background: linear-gradient(135deg, #00d4ff, #7b2cbf) !important;
    color: white !important;
    border: none !important;
    border-radius: 8px !important;
    font-weight: 600 !important;
    margin: 8px auto !important;
    display: block !important;
}}

/* ═══ CLASSES CUSTOMIZADAS DO DASHBOARD ═════════════════════════════════════ */

.apm-title {{
    font-size: 26px;
    font-weight: 800;
    color: #00d4ff;
    text-align: center;
    letter-spacing: 4px;
    text-shadow: 0 0 24px rgba(0, 212, 255, 0.55);
    margin: 0 0 2px 0;
}}
.apm-subtitle {{
    font-size: 11px;
    color: #63DCF7;
    text-align: center;
    letter-spacing: 2.5px;
    margin-bottom: 8px;
    opacity: 0.85;
}}

/* ── Bateria ─────────────────────────────────────────────────────────────── */
.battery-container {{
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    width: 100%;
    height: 100%;
    min-height: 150px;
    padding: 8px 0;
}}
.battery {{
    width: 92%;
    max-width: 320px;
    height: 65px;
    border: 2px solid rgba(0, 212, 255, 0.45);
    border-radius: 10px;
    position: relative;
    background: rgba(0, 0, 0, 0.35);
    margin-bottom: 8px;
}}
.battery::after {{
    content: '';
    position: absolute;
    right: -10px;
    top: 18px;
    width: 10px;
    height: 28px;
    background: rgba(0, 212, 255, 0.6);
    border-radius: 0 3px 3px 0;
}}
.battery-level {{
    height: 100%;
    width: 0%;
    border-radius: 8px;
    transition: width 0.5s ease;
}}
.health-label {{
    font-size: 13px;
    font-weight: 700;
    color: #EDF3F5;
    letter-spacing: 1px;
    text-align: center;
}}

/* ── Cards de métricas (header dashboard) ───────────────────────────────── */
.metric-card {{
    background: rgba(7, 26, 43, 0.55);
    backdrop-filter: blur(10px);
    -webkit-backdrop-filter: blur(10px);
    border-radius: 14px;
    padding: 9px 8px;
    text-align: center;
    margin: 4px 2px;
    border: 1px solid rgba(0, 212, 255, 0.20);
}}
.metric-value {{
    font-size: 20px;
    font-weight: 700;
    color: #63DCF7;
}}
.metric-label {{
    font-size: 10px;
    color: #A8CEDD;
    letter-spacing: 0.8px;
    text-transform: uppercase;
}}

/* ── Beta box (Crow-AMSAA) ──────────────────────────────────────────────── */
.beta-box {{
    background: rgba(0, 0, 0, 0.45);
    border-left: 4px solid;
    border-radius: 4px;
    padding: 10px 16px;
    margin-top: 12px;
    font-size: 15px;
    font-weight: 600;
    backdrop-filter: blur(4px);
}}

</style>
"""


# ─── Tema Plotly ──────────────────────────────────────────────────────────────

# Config padrão para st.plotly_chart — desativa zoom/drag por scroll e toque no mobile
PLOTLY_CONFIG = {
    "scrollZoom":   False,
    "displayModeBar": False,
    "doubleClick":  False,
    "staticPlot":   False,   # False mantém hover; True congela tudo
}

PLOTLY_THEME_KWARGS = dict(
    plot_bgcolor="rgba(0,0,0,0)",
    paper_bgcolor="rgba(0,0,0,0)",
    font=dict(color="#F0FFFF", size=13),
    title=dict(font=dict(color="#63DCF7", size=16)),   # alinhado à esquerda (default x=0)
    xaxis=dict(
        gridcolor="rgba(255,255,255,0.10)",
        linecolor="rgba(0,212,255,0.35)",
        tickfont=dict(color="#C6E8FF", size=11),
        title=dict(font=dict(color="#90C8E0", size=12)),
    ),
    yaxis=dict(
        gridcolor="rgba(255,255,255,0.10)",
        linecolor="rgba(0,212,255,0.35)",
        tickfont=dict(color="#C6E8FF", size=11),
        title=dict(font=dict(color="#90C8E0", size=12)),
    ),
    legend=dict(
        font=dict(color="#C6E0F5", size=11),
        bgcolor="rgba(0,0,0,0.40)",
        orientation="h",
        yanchor="bottom",
        y=-0.25,
        xanchor="center",
        x=0.5,
    ),
    margin=dict(t=40, b=80, l=50, r=20),
    dragmode=False,   # bloqueia zoom/pan por toque no mobile
)


# Cores do gauge
GAUGE_STEPS = [
    {"range": [0,  30], "color": "rgba(5,  150, 105, 0.25)"},
    {"range": [30, 50], "color": "rgba(202, 138,  4, 0.25)"},
    {"range": [50, 70], "color": "rgba(234, 88,  12, 0.25)"},
    {"range": [70,100], "color": "rgba(220, 38,  38, 0.25)"},
]
