"""
Helpers de UI reutilizáveis — cards KPI e tabelas dark.
Importar em qualquer aba: from frontend.components.ui_helpers import kpi_row, html_table, nbr
"""
from __future__ import annotations

import pandas as pd
import streamlit as st
from typing import Sequence, Tuple, Union


def nbr(value, decimals: int = 2, suffix: str = "") -> str:
    """Formata número com vírgula como separador decimal (padrão brasileiro).

    nbr(3.14)       → '3,14'
    nbr(1500.5, 1)  → '1500,5'
    nbr(0.875, 0)   → '1'        (sem casa decimal → sem vírgula)
    nbr(95.3, 1, '%') → '95,3%'
    """
    try:
        formatted = f"{float(value):.{decimals}f}"
        if decimals > 0:
            formatted = formatted.replace(".", ",")
        return f"{formatted}{suffix}"
    except (TypeError, ValueError):
        return str(value) if value is not None else "—"

# (label, valor, subtítulo)  ou  (label, valor, subtítulo, tooltip)
KPIItem = Union[Tuple[str, str, str], Tuple[str, str, str, str]]

_CARD = """
<div style="background:rgba(0,212,255,0.06);border:1px solid rgba(0,212,255,0.15);
            border-radius:10px;padding:8px 10px;text-align:center;margin-bottom:6px;
            cursor:default;" title="{tooltip}">
  <div style="font-size:10px;color:#90C8E0;letter-spacing:.8px;text-transform:uppercase;
              white-space:nowrap;overflow:hidden;text-overflow:ellipsis;margin-bottom:3px;">{label}</div>
  <div style="font-size:{fsize}px;font-weight:700;color:{color};
              white-space:nowrap;overflow:hidden;text-overflow:ellipsis;">{val}</div>
  <div style="font-size:10px;color:#A8CEDD;margin-top:2px;
              white-space:nowrap;overflow:hidden;text-overflow:ellipsis;">{sub}</div>
  {tip_icon}
</div>"""

_TIP_ICON = '<div style="font-size:9px;color:#4A8FA8;margin-top:1px;">ⓘ passe o mouse</div>'


def kpi_row(items: Sequence[KPIItem], color: str = "#63DCF7", font_size: int = 20) -> None:
    """Renderiza uma linha de cards KPI compactos dark.

    Cada item pode ser (label, val, sub) ou (label, val, sub, tooltip).
    Tooltip aparece como title HTML ao passar o mouse.
    """
    cols = st.columns(len(items))
    for col, item in zip(cols, items):
        label, val, sub = item[0], item[1], item[2]
        tooltip = item[3] if len(item) >= 4 else ""  # type: ignore[misc]
        tip_icon = _TIP_ICON if tooltip else ""
        col.markdown(
            _CARD.format(
                label=label, val=val, sub=sub,
                color=color, fsize=font_size,
                tooltip=tooltip.replace('"', "'"),
                tip_icon=tip_icon,
            ),
            unsafe_allow_html=True,
        )


def html_table(df: pd.DataFrame, max_rows: int = 200) -> None:
    """Renderiza DataFrame como tabela dark estilizada (sem iframe, sem CSS white)."""
    slice_ = df.head(max_rows)

    headers = "".join(
        f'<th style="padding:7px 12px;background:#0B2E42;color:#63DCF7;font-weight:700;'
        f'border-bottom:1px solid rgba(0,212,255,0.3);text-align:left;'
        f'white-space:nowrap;">{c}</th>'
        for c in slice_.columns
    )

    rows_html = ""
    for i, (_, row) in enumerate(slice_.iterrows()):
        bg = "#071A2B" if i % 2 == 0 else "#0A2336"
        cells = "".join(
            f'<td style="padding:6px 12px;background:{bg};color:#C6E8FF;'
            f'border-bottom:1px solid rgba(0,212,255,0.06);">{v}</td>'
            for v in row
        )
        rows_html += f"<tr>{cells}</tr>"

    st.markdown(f"""
<div style="overflow-x:auto;border-radius:8px;border:1px solid rgba(0,212,255,0.2);margin:6px 0 12px 0;">
<table style="width:100%;border-collapse:collapse;background:#071A2B;font-size:13px;">
<thead><tr>{headers}</tr></thead>
<tbody>{rows_html}</tbody>
</table>
</div>""", unsafe_allow_html=True)
