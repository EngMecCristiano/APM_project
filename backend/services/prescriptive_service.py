"""
Agente de Manutenção Prescritiva com IA.
Combina Expert System (regras ISO 14224) com Claude API (tool_use)
para gerar planos prescritivos baseados em evidências.

Com ANTHROPIC_API_KEY: agente Claude claude-opus-4-7 com 3 ferramentas.
Sem ANTHROPIC_API_KEY: fallback para Expert System puro (sem custo).
"""
from __future__ import annotations

import json
import logging
import math
import os
import re
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# Pesos de criticidade para scoring dos cenários
_CRIT_WEIGHT: Dict[str, int] = {"Alta": 3, "Média": 2, "Baixa": 1}

# ─── Ferramentas do agente ────────────────────────────────────────────────────

_TOOLS = [
    {
        "name": "get_catalog_scenarios",
        "description": (
            "Retorna os cenários de falha do catálogo ISO 14224 para o equipamento, "
            "ordenados por probabilidade × peso de criticidade (Alta=3, Média=2, Baixa=1). "
            "Use para identificar os modos de falha mais prováveis e críticos do ativo."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "equipment_type": {
                    "type": "string",
                    "description": "Nome exato do tipo de equipamento conforme informado no estado do ativo."
                },
                "top_n": {
                    "type": "integer",
                    "description": "Número máximo de cenários a retornar (default 8, máx 15)."
                },
            },
            "required": ["equipment_type"],
        },
    },
    {
        "name": "compute_maintenance_window",
        "description": (
            "Calcula a janela temporal recomendada para intervenção de manutenção "
            "com base no RUL, score de risco e intervalo ótimo PMO (se disponível)."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "rul_hours":      {"type": "number",  "description": "Vida útil residual estimada em horas."},
                "risk_score":     {"type": "integer", "description": "Score de risco ML de 0 a 100."},
                "pmo_tp_otimo":   {"type": "number",  "description": "Intervalo ótimo PMO em horas (opcional)."},
                "horimetro_atual": {"type": "number", "description": "Horímetro atual do ativo em horas."},
            },
            "required": ["rul_hours", "risk_score"],
        },
    },
    {
        "name": "classify_urgency",
        "description": (
            "Classifica o nível de urgência da manutenção e define a ação prioritária "
            "com base no score de risco, tipo de tendência e histórico de falhas."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "risk_score":    {"type": "integer", "description": "Score de risco ML (0–100)."},
                "trend_type":    {"type": "string",  "description": "Tipo de tendência detectada pelo ML."},
                "rul_hours":     {"type": "number",  "description": "Vida útil residual em horas."},
                "anomaly_count": {"type": "integer", "description": "Número de anomalias detectadas."},
                "failure_count": {"type": "integer", "description": "Número de falhas no histórico."},
            },
            "required": ["risk_score", "trend_type", "rul_hours"],
        },
    },
]


# ─── Implementação das ferramentas ────────────────────────────────────────────

def _tool_get_scenarios(inputs: Dict, catalog: List[Dict]) -> Dict:
    equipment_type = inputs.get("equipment_type", "")
    top_n = min(int(inputs.get("top_n", 8)), 15)

    eq_entry = next((e for e in catalog if e.get("name") == equipment_type), None)

    if not eq_entry:
        all_scenarios = [s for eq in catalog for s in eq.get("failure_scenarios", [])]
        scored = sorted(
            [{**s, "_score": s.get("prob", 0) * _CRIT_WEIGHT.get(s.get("criticidade", "Média"), 2)}
             for s in all_scenarios],
            key=lambda x: x["_score"], reverse=True,
        )
        return {
            "equipment": equipment_type,
            "note": "Equipamento não encontrado no catálogo — usando cenários agregados de referência",
            "scenarios": scored[:top_n],
        }

    scenarios = eq_entry.get("failure_scenarios", [])
    scored = sorted(
        [{**s, "_score": s.get("prob", 0) * _CRIT_WEIGHT.get(s.get("criticidade", "Média"), 2)}
         for s in scenarios],
        key=lambda x: x["_score"], reverse=True,
    )
    return {
        "equipment": equipment_type,
        "iso14224_class": eq_entry.get("iso14224_class", ""),
        "sector": eq_entry.get("sector", ""),
        "weibull": eq_entry.get("weibull", {}),
        "scenarios": scored[:top_n],
        "total_scenarios": len(scenarios),
    }


def _tool_maintenance_window(inputs: Dict) -> Dict:
    rul     = float(inputs.get("rul_hours", 0))
    risk    = int(inputs.get("risk_score", 0))
    pmo_tp  = inputs.get("pmo_tp_otimo")
    horim   = float(inputs.get("horimetro_atual", 0))

    if risk >= 70 or rul < 100:
        janela    = "Imediata (≤ 48h)"
        max_hours = min(rul * 0.15, 48)
    elif risk >= 50:
        janela    = "Curto Prazo (≤ 2 semanas)"
        max_hours = min(rul * 0.30, 336)
    elif risk >= 30:
        janela    = "Médio Prazo (≤ 1 mês)"
        max_hours = min(rul * 0.50, 720)
    else:
        janela    = "Planejado (próxima parada programada)"
        max_hours = rul * 0.70

    horas_ate_pmo = float(pmo_tp) - horim if pmo_tp else None
    recomendado   = min(max_hours, horas_ate_pmo) if horas_ate_pmo else max_hours
    recomendado   = max(0.0, recomendado)

    return {
        "janela_recomendada":   janela,
        "horas_ate_intervencao": round(recomendado, 1),
        "rul_disponivel_h":      round(rul, 1),
        "pmo_horas_restantes":   round(horas_ate_pmo, 1) if horas_ate_pmo else None,
        "interpretacao": (
            f"Intervir em até {recomendado:.0f}h — RUL: {rul:.0f}h, "
            f"Risco: {risk}/100"
        ),
    }


def _tool_classify_urgency(inputs: Dict) -> Dict:
    risk     = int(inputs.get("risk_score", 0))
    trend    = str(inputs.get("trend_type", ""))
    rul      = float(inputs.get("rul_hours", 9999))
    anomalies = int(inputs.get("anomaly_count", 0))

    if risk >= 70 or rul < 100:
        nivel = "Crítica"
        acao  = "Parar o equipamento para inspeção imediata"
        cor   = "#DC2626"
    elif risk >= 50 or (anomalies > 5 and "degradação" in trend.lower()):
        nivel = "Alta"
        acao  = "Programar parada nos próximos 2–7 dias"
        cor   = "#F59E0B"
    elif risk >= 30:
        nivel = "Média"
        acao  = "Incluir na próxima janela de manutenção preventiva"
        cor   = "#3B82F6"
    else:
        nivel = "Baixa"
        acao  = "Monitorar e manter plano de manutenção vigente"
        cor   = "#10B981"

    return {
        "nivel_urgencia": nivel,
        "cor":            cor,
        "acao_principal": acao,
        "fatores": {
            "risk_score":   risk,
            "tendencia":    trend,
            "rul_h":        rul,
            "anomalias":    anomalies,
        },
    }


def _execute_tool(name: str, inputs: Dict, req: Dict, catalog: List[Dict]) -> Dict:
    if name == "get_catalog_scenarios":
        return _tool_get_scenarios(inputs, catalog)
    if name == "compute_maintenance_window":
        return _tool_maintenance_window(inputs)
    if name == "classify_urgency":
        return _tool_classify_urgency(inputs)
    return {"error": f"Ferramenta '{name}' não encontrada"}


# ─── Parser da resposta do agente ─────────────────────────────────────────────

def _parse_response(text: str, steps: List[str]) -> Dict:
    """Extrai o JSON estruturado do texto final do agente."""
    structured: Optional[Dict] = None
    m = re.search(r"```json\s*([\s\S]*?)\s*```", text)
    if m:
        try:
            structured = json.loads(m.group(1))
        except json.JSONDecodeError:
            pass

    # Texto narrativo = tudo antes do bloco ```json (ou texto inteiro se não houver bloco)
    diagnostico = re.sub(r"```json[\s\S]*?```", "", text).strip()
    # Remove também qualquer bloco JSON solto (começa com { na raiz)
    diagnostico = re.sub(r"\n\s*\{[\s\S]*", "", diagnostico).strip()

    if not structured:
        structured = {
            "sumario_executivo": (diagnostico[:400] + "…") if len(diagnostico) > 400 else diagnostico,
            "nivel_urgencia":    "Média",
            "proxima_intervencao_h": None,
            "janela_intervencao": "—",
            "acoes": [],
        }

    structured["raciocinio_agente"] = steps
    structured["diagnostico"]       = diagnostico  # só texto narrativo, sem JSON
    structured["ia_disponivel"]     = True
    return structured


# ─── Fallback Expert System (sem API key) ─────────────────────────────────────

def _expert_system(req: Dict, catalog: List[Dict]) -> Dict:
    """Prescrição baseada em regras quando a API key não está disponível."""
    eq_type  = req.get("equipment_type", "")
    risk     = int(req.get("risk_score", 0))
    rul      = float(req.get("rul_hours", 9999))
    tag      = req.get("tag", "—")

    urgency = _tool_classify_urgency({
        "risk_score":    risk,
        "trend_type":    req.get("trend_type", ""),
        "rul_hours":     rul,
        "anomaly_count": req.get("anomaly_count", 0),
    })
    window = _tool_maintenance_window({
        "rul_hours":      rul,
        "risk_score":     risk,
        "pmo_tp_otimo":   req.get("pmo_tp_otimo"),
        "horimetro_atual": req.get("horimetro_atual", 0),
    })
    scen_result = _tool_get_scenarios({"equipment_type": eq_type, "top_n": 6}, catalog)

    acoes = []
    for i, s in enumerate(scen_result.get("scenarios", []), 1):
        ttr_exp = round(math.exp(s.get("ttr_mu", 3.0)), 1) if s.get("ttr_mu") else None
        acoes.append({
            "prioridade":         i,
            "subcomponente":      s.get("subcomponente", "—"),
            "modo_falha":         s.get("modo_falha", "—"),
            "causa_raiz":         s.get("causa_raiz", "—"),
            "mecanismo":          s.get("mecanismo", "—"),
            "criticidade":        s.get("criticidade", "Média"),
            "boundary":           s.get("boundary", "—"),
            "acao_recomendada":   urgency["acao_principal"],
            "janela_intervencao": window["janela_recomendada"],
            "ttr_esperado_h":     ttr_exp,
            "custo_relativo":     s.get("cost_factor", 1.0),
            "justificativa": (
                f"Probabilidade: {s.get('prob', 0) * 100:.0f}% — "
                f"Criticidade: {s.get('criticidade', 'Média')} — "
                f"Boundary: {s.get('boundary', '—')}"
            ),
        })

    return {
        "diagnostico": (
            f"Score de risco {risk}/100 — {urgency['nivel_urgencia']}. "
            f"{urgency['acao_principal']}."
        ),
        "sumario_executivo": (
            f"Equipamento **{eq_type}** (TAG: {tag}) com RUL de {rul:.0f}h e "
            f"score de risco {risk}/100. Nível de urgência: **{urgency['nivel_urgencia']}**. "
            f"Intervir em até {window['horas_ate_intervencao']:.0f}h."
        ),
        "nivel_urgencia":        urgency["nivel_urgencia"],
        "cor_urgencia":          urgency["cor"],
        "proxima_intervencao_h": window["horas_ate_intervencao"],
        "janela_intervencao":    window["janela_recomendada"],
        "acoes":                 acoes,
        "raciocinio_agente":     ["[Expert System — ANTHROPIC_API_KEY não configurada]"],
        "texto_completo":        "",
        "ia_disponivel":         False,
    }


# ─── Entrada principal ────────────────────────────────────────────────────────

_SYSTEM_PROMPT = """Você é um especialista sênior em Manutenção Prescritiva e Confiabilidade Industrial \
com expertise em ISO 14224:2016 e RCM (Reliability-Centered Maintenance).

Você recebe o estado atual de um ativo industrial (score de risco ML, RUL, parâmetros Weibull, \
histórico de falhas) e usa as ferramentas disponíveis para gerar um plano prescritivo completo.

**Processo obrigatório:**
1. Use `get_catalog_scenarios` para os modos de falha mais críticos e prováveis do equipamento
2. Use `compute_maintenance_window` para calcular a janela de intervenção recomendada
3. Use `classify_urgency` para determinar o nível de urgência e ação prioritária
4. Sintetize em diagnóstico técnico + plano prescritivo JSON

**Formato de resposta final obrigatório:**
Após usar as ferramentas, forneça:
1. Diagnóstico técnico (2–3 parágrafos em português técnico)
2. JSON estruturado no formato exato abaixo

```json
{
  "sumario_executivo": "1–2 frases resumindo situação e ação principal",
  "nivel_urgencia": "Crítica|Alta|Média|Baixa",
  "cor_urgencia": "#DC2626|#F59E0B|#3B82F6|#10B981",
  "proxima_intervencao_h": <número>,
  "janela_intervencao": "descrição da janela",
  "acoes": [
    {
      "prioridade": 1,
      "subcomponente": "...",
      "modo_falha": "...",
      "causa_raiz": "...",
      "mecanismo": "...",
      "criticidade": "Alta|Média|Baixa",
      "boundary": "Interno|Externo",
      "acao_recomendada": "descrição específica da ação",
      "janela_intervencao": "Ex: Imediata / Curto Prazo / Próxima parada",
      "ttr_esperado_h": <número ou null>,
      "custo_relativo": <fator numérico>,
      "justificativa": "por que esta ação é prioritária com base nos dados"
    }
  ]
}
```

Responda sempre em português do Brasil. Seja técnico, preciso e acionável."""


def run(req: Dict[str, Any], catalog: List[Dict]) -> Dict[str, Any]:
    """
    Executa o agente de Manutenção Prescritiva.
    Com ANTHROPIC_API_KEY: Claude claude-sonnet-4-6 + tool_use.
    Sem ANTHROPIC_API_KEY: Expert System baseado em regras ISO 14224.
    Qualquer exceção cai no Expert System — nunca retorna 500.
    """
    api_key = os.getenv("ANTHROPIC_API_KEY")

    if not api_key:
        logger.warning("ANTHROPIC_API_KEY ausente — usando Expert System")
        return _expert_system(req, catalog)

    try:
        import anthropic as _anthropic
    except ImportError:
        logger.error("Pacote 'anthropic' não instalado — usando Expert System")
        return _expert_system(req, catalog)

    try:
        return _run_agent(req, catalog, _anthropic)
    except Exception as exc:
        logger.error("Erro no agente prescritivo: %s", exc, exc_info=True)
        fallback = _expert_system(req, catalog)
        fallback["raciocinio_agente"] = [f"[Erro no agente: {exc}]", "[Fallback: Expert System]"]
        fallback["ia_disponivel"] = False
        return fallback


def _run_agent(req: Dict[str, Any], catalog: List[Dict], _anthropic: Any) -> Dict[str, Any]:
    """Loop do agente Claude com tool_use."""
    client = _anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))

    user_msg = (
        f"Analise o estado atual do ativo e gere o plano prescritivo:\n\n"
        f"**Equipamento:** {req['equipment_type']}\n"
        f"**TAG:** {req['tag']}\n"
        f"**Score de Risco ML:** {req['risk_score']}/100 ({req['risk_classification']})\n"
        f"**RUL Estimado:** {req['rul_hours']:.0f} h\n"
        f"**Horímetro Atual:** {req['horimetro_atual']:.0f} h\n"
        f"**Weibull:** β={req.get('weibull_beta', 'N/A')}, η={req.get('weibull_eta', 'N/A')} h\n"
        f"**Tendência TBF:** {req['trend_type']} ({req['degradation_rate']:.2f}%/ciclo)\n"
        f"**Falhas no histórico:** {req['failure_count']}\n"
        f"**Anomalias detectadas:** {req['anomaly_count']}\n"
        f"**PMO Intervalo Ótimo:** {req.get('pmo_tp_otimo') or 'Não calculado'} h\n\n"
        "Execute a análise completa usando as três ferramentas disponíveis."
    )

    messages: List[Dict] = [{"role": "user", "content": user_msg}]
    steps:    List[str]  = []

    urgency_map = {
        "Crítica": "#DC2626", "Alta": "#F59E0B",
        "Média": "#3B82F6",  "Baixa": "#10B981",
    }

    last_text = ""

    for _ in range(12):
        response = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=8096,
            system=_SYSTEM_PROMPT,
            tools=_TOOLS,
            messages=messages,
        )

        logger.info("Agente stop_reason: %s", response.stop_reason)

        # Extrai texto de qualquer resposta (end_turn ou max_tokens)
        if response.stop_reason in ("end_turn", "max_tokens"):
            final_text = "".join(
                b.text for b in response.content if hasattr(b, "text")
            )
            last_text = final_text or last_text
            result = _parse_response(last_text, steps)
            if "cor_urgencia" not in result:
                result["cor_urgencia"] = urgency_map.get(
                    result.get("nivel_urgencia", "Média"), "#3B82F6"
                )
            return result

        if response.stop_reason == "tool_use":
            tool_results = []
            for block in response.content:
                if hasattr(block, "text") and block.text:
                    last_text = block.text
                if block.type == "tool_use":
                    logger.info("Agente → ferramenta: %s", block.name)
                    steps.append(
                        f"🔧 {block.name}({json.dumps(block.input, ensure_ascii=False)[:60]}…)"
                    )
                    tool_out = _execute_tool(block.name, block.input, req, catalog)
                    tool_results.append({
                        "type":        "tool_result",
                        "tool_use_id": block.id,
                        "content":     json.dumps(tool_out, ensure_ascii=False),
                    })
            messages.append({"role": "assistant", "content": response.content})
            messages.append({"role": "user",      "content": tool_results})
        else:
            # stop_reason desconhecido — tenta extrair texto e retorna
            final_text = "".join(b.text for b in response.content if hasattr(b, "text"))
            last_text = final_text or last_text
            logger.warning("Stop reason inesperado '%s' — tentando parsear texto", response.stop_reason)
            if last_text.strip():
                result = _parse_response(last_text, steps)
                if "cor_urgencia" not in result:
                    result["cor_urgencia"] = urgency_map.get(
                        result.get("nivel_urgencia", "Média"), "#3B82F6"
                    )
                return result
            break

    logger.warning("Loop do agente encerrado sem resposta final — usando Expert System")
    fallback = _expert_system(req, catalog)
    fallback["raciocinio_agente"] = steps + ["[Fallback: Expert System]"]
    return fallback
