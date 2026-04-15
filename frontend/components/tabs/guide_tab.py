"""
Aba 📖 Guia & Teoria — Referência técnica completa do APM Analytics.
Cobre teoria matemática, interpretação dos indicadores e guia prático botão a botão.
"""
from __future__ import annotations

import streamlit as st


def render() -> None:
    """Renderiza o guia completo com navegação por sub-abas."""

    st.markdown("## 📖 Guia & Teoria — APM Analytics")
    st.caption(
        "Referência técnica completa: fundamentos matemáticos, interpretação dos indicadores "
        "e guia prático passo a passo para cada funcionalidade do sistema."
    )

    sections = st.tabs([
        "🚀 Como Começar",
        "📊 LDA",
        "🔮 RUL",
        "📈 Crow-AMSAA",
        "🧠 Machine Learning",
        "🔧 PMO",
        "📋 ISO 14224",
        "🏭 Cases",
        "📚 Glossário",
    ])

    with sections[0]:
        _section_como_comecar()
    with sections[1]:
        _section_lda()
    with sections[2]:
        _section_rul()
    with sections[3]:
        _section_crow_amsaa()
    with sections[4]:
        _section_ml()
    with sections[5]:
        _section_pmo()
    with sections[6]:
        _section_iso14224()
    with sections[7]:
        _section_cases()
    with sections[8]:
        _section_glossario()


# ─── Seção 1: Como Começar ────────────────────────────────────────────────────

def _section_como_comecar() -> None:
    st.markdown("### 🚀 Como Começar — Guia Passo a Passo")
    st.markdown("""
O APM Analytics opera com um fluxo simples: **configurar → simular ou importar → analisar**.
Siga os passos abaixo para gerar sua primeira análise em menos de 2 minutos.
""")

    with st.expander("**Passo 1 — Abrir a Barra Lateral**", expanded=True):
        st.markdown("""
Clique no ícone **☰** no canto superior esquerdo para abrir o painel de configuração.
A barra lateral contém todos os controles de entrada de dados e parâmetros de análise.

> **Dica mobile:** a barra lateral fecha automaticamente após a execução. Swipe da esquerda para reabrir.
""")

    with st.expander("**Passo 2 — Selecionar o Equipamento**"):
        st.markdown("""
**Campo: Perfil de Equipamento**

Escolha um dos perfis pré-configurados representativos da mineração:

| Perfil | β | η (h) | Aplicação típica |
|---|---|---|---|
| Britador Cônico HP500 | 2.1 | 3.200 h | Cominuição primária |
| Bomba Centrífuga Warman | 1.8 | 2.800 h | Polpas abrasivas |
| Redutor de Velocidade | 2.8 | 5.500 h | Transportadores de correia |
| Motor Elétrico 6,6 kV | 1.5 | 8.000 h | Acionamentos críticos |
| Peneira Vibratória | 1.6 | 2.100 h | Classificação granulométrica |

**Ou use "Personalizado"** para inserir seus próprios parâmetros Weibull (β, η) ou Lognormal (μ, σ).

> **β = Parâmetro de Forma:** define o regime de falha. β < 1 = mortalidade infantil | β ≈ 1 = aleatório | β > 1 = desgaste.
> **η = Vida Característica:** 63,2% dos equipamentos terão falhado até este horímetro.
""")

    with st.expander("**Passo 3 — Definir TAG e Horímetro**"):
        st.markdown("""
**Campo: TAG do Ativo**
- Identificador único do equipamento (ex: `BRD-HP500-01`, `BBA-WAR-003`)
- Usado para nomear arquivos de export e relatório PDF
- Salvo no histórico persistente do sistema

**Campo: Horímetro Atual (h)**
- Horas acumuladas de operação desde o início ou última grande reforma
- **Não confundir com data de instalação** — use o horímetro do hodômetro/contador de horas do equipamento
- Este valor é usado para calcular R(t₀), RUL e a taxa de hazard atual h(t₀)

> **Exemplo:** se o britador acumula 4.200 h desde a última troca do manto, insira 4200.
""")

    with st.expander("**Passo 4 — Escolher a Fonte de Dados**"):
        st.markdown("""
O sistema aceita duas fontes de dados:

---

**🎲 Simulação Sintética** (para aprendizado e cenários hipotéticos)

| Campo | O que preencher |
|---|---|
| Nº de Amostras | Quantidade de eventos a simular (100–2000). Mais amostras = maior precisão estatística |
| Proporção de Censuras | % de registros sem falha (ex: 0.20 = 20% dos eventos são inspeções sem falha) |
| Semente Aleatória | Qualquer número inteiro. Garante reprodutibilidade do cenário |

> **Enriquecimento ISO 14224:** marque esta opção para gerar também campos de Modo de Falha, Causa Raiz, Subcomponente, TTR, Custo de Reparo e Lucro Cessante — habilita a aba "Dataset ISO 14224".

---

**📂 Importar CSV Real** (para análise de dados históricos reais)

O arquivo CSV deve conter obrigatoriamente as colunas:

| Coluna | Tipo | Descrição |
|---|---|---|
| `TBF` | float | Time Between Failures — horas entre falhas consecutivas |
| `Falha` | int | 1 = falha confirmada, 0 = censura (inspeção sem falha) |

Colunas opcionais ISO 14224: `Modo_Falha`, `Causa_Raiz`, `Subcomponente`, `TTR`, `Custo_Reparo_BRL`, `Impacto_Producao_t`.

**Preparando seu CSV:**
1. Extraia o histórico do CMMS (SAP PM, Máximo, etc.)
2. Calcule os TBFs como diferença entre datas de falha consecutivas em horas
3. Marque como censura (0) os registros de inspeção sem falha ou o período em operação atual
4. Exporte com ponto-e-vírgula (`;`) ou vírgula (`,`) como separador — o sistema detecta automaticamente
""")

    with st.expander("**Passo 5 — Configurar Limiares de Análise**"):
        st.markdown("""
**Limiar de Confiabilidade (RUL Threshold)**
- Padrão: **10%** → O RUL indica quando a confiabilidade cai para 10% (ou seja: 90% de chance de falha)
- Valores menores = mais conservador (intervenção mais cedo)
- Valores maiores = mais tolerante ao risco

**Nível de Bootstrap (n_bootstrap)**
- Número de reamostragens para calcular o IC do RUL
- Padrão: 300. Aumente para 500+ em análises críticas (mais lento)

**Score de Risco — Pesos dos componentes** (opcional)
- Tendência NHPP, Anomalias, Confiabilidade, Proximidade TBF
- Ajuste os pesos se quiser priorizar um indicador específico
""")

    with st.expander("**Passo 6 — Executar e Interpretar**"):
        st.markdown("""
Clique em **"▶ Executar Simulação"** ou **"▶ Processar Dados Reais"**.

O sistema executa em sequência:
1. Ajuste paramétrico (Weibull, Lognormal, Normal, Exponencial) — seleciona o melhor pelo AICc
2. Cálculo do RUL com Bootstrap paramétrico (IC 80%)
3. Análise Crow-AMSAA (tendência de degradação NHPP)
4. Auditoria estatística (KS test, outliers IQR, Spearman)
5. Machine Learning (Random Forest + Isolation Forest + Score de Risco)

**Feche a barra lateral** clicando no ✕ ou clicando fora dela para ver os resultados nas abas.

**Bateria de Saúde (esquerda):** mostra R(t₀) como nível de carga — verde > 70%, amarelo 40-70%, vermelho < 40%.

**KPIs de topo:**
- `R(t₀)` — Confiabilidade atual
- `RUL` — Vida útil remanescente em horas
- `Modelo` — Distribuição vencedora (Weibull, Lognormal, etc.)
- `β` — Parâmetro de forma (regime de falha)
""")

    with st.expander("**Passo 7 — Histórico e PDF**"):
        st.markdown("""
**Histórico Acumulado:**
O sistema salva automaticamente cada análise no histórico do ativo (por TAG).
Na próxima sessão, você pode carregar o histórico anterior para enriquecer a análise com mais dados.

**Relatório PDF:**
Clique em **"📄 Gerar Relatório PDF"** no rodapé da página. O relatório inclui:
- Identificação do ativo e data da análise
- Saúde atual, RUL com IC Bootstrap e horizonte de intervenção
- Curvas de confiabilidade (SF, HF) com IC 95%
- Resultados Crow-AMSAA e Score de Risco ML
- Auditoria estatística (KS, Spearman, outliers)
- Ranking de modelos AICc
""")


# ─── Seção 2: LDA ────────────────────────────────────────────────────────────

def _section_lda() -> None:
    st.markdown("### 📊 LDA — Life Data Analysis")
    st.markdown("""
**Life Data Analysis** é a disciplina de ajustar distribuições estatísticas ao histórico de falhas
para quantificar a confiabilidade de um equipamento ao longo do tempo.
""")

    with st.expander("📐 Fundamentos Matemáticos"):
        st.markdown(r"""
#### As 4 Distribuições Analisadas

**Weibull (2 parâmetros)**

$$f(t) = \frac{\beta}{\eta}\left(\frac{t}{\eta}\right)^{\beta-1} e^{-(t/\eta)^\beta}$$

$$R(t) = e^{-(t/\eta)^\beta} \qquad h(t) = \frac{\beta}{\eta}\left(\frac{t}{\eta}\right)^{\beta-1}$$

- **β < 1:** taxa de falha decrescente → mortalidade infantil (defeitos de fabricação/montagem)
- **β = 1:** taxa constante → falhas aleatórias (HPP — Poisson homogêneo)
- **β > 1:** taxa crescente → desgaste por envelhecimento

---

**Lognormal**

$$f(t) = \frac{1}{t\sigma\sqrt{2\pi}} e^{-(\ln t - \mu)^2 / (2\sigma^2)}$$

Útil quando o processo de falha envolve **acumulação de danos** (corrosão, fadiga, trinca).
A mediana da vida é $e^\mu$ horas.

---

**Normal**

$$f(t) = \frac{1}{\sigma\sqrt{2\pi}} e^{-(t-\mu)^2/(2\sigma^2)}$$

Menos comum em confiabilidade (pode gerar t < 0), mas útil para componentes com desgaste uniforme.

---

**Exponencial**

$$f(t) = \lambda e^{-\lambda t} \qquad R(t) = e^{-\lambda t} \qquad h(t) = \lambda \text{ (constante)}$$

Processo de Poisson Homogêneo (HPP). MTBF = 1/λ. Não tem memória.
""")

    with st.expander("📏 Estimação MLE e Seleção de Modelos (AICc)"):
        st.markdown(r"""
#### Maximum Likelihood Estimation (MLE)

Os parâmetros são estimados maximizando a **função de verossimilhança** que considera
tanto falhas confirmadas quanto **dados censurados** (right-censored):

$$\mathcal{L}(\theta) = \prod_{i \in \text{falhas}} f(t_i;\theta) \cdot \prod_{j \in \text{censuras}} R(t_j;\theta)$$

#### Critério de Akaike Corrigido (AICc)

$$\text{AICc} = -2\ln\mathcal{L} + 2k + \frac{2k(k+1)}{n-k-1}$$

onde $k$ = número de parâmetros do modelo, $n$ = total de registros.

**Interpretação:**
- Menor AICc = melhor equilíbrio entre ajuste e parcimônia
- |ΔAICc| > 4 → modelo vencedor significativamente superior
- |ΔAICc| < 2 → modelos equivalentes (use conhecimento de domínio)
""")

    with st.expander("📈 Interpretando as Funções de Confiabilidade"):
        st.markdown("""
| Função | Símbolo | Leitura | Quando usar |
|---|---|---|---|
| **Sobrevivência** | R(t) ou SF | Probabilidade de ainda estar operando em t horas | **Principal — use sempre** |
| **Densidade de Prob.** | f(t) ou PDF | Concentração de falhas ao longo do tempo | Ver onde as falhas se concentram |
| **Acumulada** | F(t) ou CDF | Probabilidade de já ter falhado até t horas | Complementar ao SF |
| **Taxa de Falha** | h(t) ou HF | Risco instantâneo de falha a cada hora | Identificar regime de desgaste |
| **Hazard Acumulado** | H(t) ou CHF | Dano acumulado | Modelos de degradação e renovação |

#### Kaplan-Meier (linha tracejada)

Estimativa **não-paramétrica** da função de sobrevivência — calculada diretamente dos dados
sem assumir distribuição. Serve como referência empírica: quanto mais próxima do modelo ajustado,
melhor o ajuste paramétrico.

#### IC 95% (faixa cinza)

Intervalo de confiança baseado na aproximação de Wald para proporções. A faixa reflete a incerteza
estatística: com poucos dados (< 10 falhas) a faixa é muito larga; com muitas falhas ela estreita.
""")

    with st.expander("🖱️ Guia Prático — Aba LDA botão a botão"):
        st.markdown("""
**Selectbox "Função de Confiabilidade"**
- Mude para `HF` para ver se a taxa de falha é crescente (desgaste) ou constante (aleatório)
- Use `PDF` para identificar se há concentração de falhas em uma faixa de horas específica
- Use `CHF` em conjunto com o modelo Crow-AMSAA para validar a degradação acumulada

**Checkbox "IC 95%"**
- Desmarque quando o gráfico estiver poluído demais (muitos outliers nos dados reais)
- A faixa cinza mostra onde a curva real provavelmente está: mais estreita = mais confiável

**Tabela Ranking AICc**
- O Pos. 1 é o modelo selecionado automaticamente para todos os cálculos
- Se o ΔAICc do 2º modelo for < 2, considere a interpretação física: Weibull é mais intuitiva
  para engenharia do que Lognormal, mesmo com AICc similar

**Expander "Parâmetros"**
- Verifique se β e η fazem sentido físico para o equipamento
- β muito baixo (< 0.5) com poucos dados pode indicar overfitting — aumente a base histórica
""")


# ─── Seção 3: RUL ────────────────────────────────────────────────────────────

def _section_rul() -> None:
    st.markdown("### 🔮 RUL — Remaining Useful Life")
    st.markdown("""
**RUL (Vida Útil Remanescente)** é a estimativa de quantas horas o equipamento ainda pode operar
antes de atingir um nível crítico de confiabilidade — base matemática para a manutenção preditiva.
""")

    with st.expander("📐 Confiabilidade Condicional"):
        st.markdown(r"""
A confiabilidade condicional R(t|T) responde: dado que o equipamento JÁ operou T horas sem falhar,
qual é a probabilidade de sobreviver mais t horas?

$$R(t \mid T) = \frac{R(T + t)}{R(T)}$$

**Por que usar R(t|T) e não R(t)?**

R(t) é a probabilidade de sobreviver desde zero. Mas um equipamento com 3.000 h já "passou" pelos
riscos anteriores — R(t|T) corrige isso, dando uma visão mais realista do estado atual.

---

#### RUL como Problema de Otimização

O RUL é o valor τ tal que a confiabilidade condicional atinge o limiar θ:

$$\text{RUL} = \tau : R(\tau \mid T_0) = \theta$$

Padrão: θ = 10% → o equipamento tem 90% de chance de falhar antes de completar RUL horas adicionais.

---

#### Horizonte de Intervenção

$$t_{\text{intervenção}} = T_0 + \text{RUL}$$

Horímetro atual somado ao RUL — quando planejar a próxima parada preventiva.
""")

    with st.expander("📊 Bootstrap Paramétrico — IC 80% do RUL"):
        st.markdown(r"""
O RUL é uma estimativa pontual baseada nos parâmetros ajustados (β, η). Mas esses parâmetros
têm incerteza — o Bootstrap quantifica essa incerteza:

**Algoritmo:**
1. Reamostrar os dados originais com reposição (300 iterações)
2. Reajustar os parâmetros em cada amostra → distribuição de β* e η*
3. Calcular o RUL para cada par (β*, η*)
4. Os percentis P10 e P90 da distribuição de RUL formam o IC 80%

**Interpretação:**
- **IC estreito:** dados consistentes, modelo bem identificado — confiar no RUL pontual
- **IC largo:** alta variabilidade nos dados → usar o P10 (pessimista) para decisão de manutenção

> **Regra de ouro:** planejar a intervenção no **P25 do RUL** para segurança operacional.
""")

    with st.expander("🖱️ Guia Prático — Aba RUL botão a botão"):
        st.markdown("""
**KPI R(t₀) — Confiabilidade Atual**
- > 80%: equipamento saudável, manutenção pode aguardar
- 50–80%: atenção — monitorar com frequência maior
- < 50%: zona de alerta — planejar intervenção a curto prazo
- < 20%: intervenção urgente — risco alto de falha não planejada

**KPI RUL**
- Interprete sempre junto com o IC: `+500 h [200 — 800 h]` significa grande incerteza
- Se o IC for muito largo (P90/P10 > 3×), colete mais dados históricos

**KPI Horizonte de Falha**
- Converta para data: `horímetro ÷ horas diárias de operação = dias até intervenção`
- Exemplo: Horizonte 5.200 h, equipamento roda 20 h/dia, horímetro atual 4.200 h → RUL ≈ 50 dias

**Gráfico RUL**
- Eixo X: horas FUTURAS a partir do horímetro atual (não é o horímetro absoluto)
- Linha pontilhada vermelha: limiar de confiabilidade configurado
- Faixa vermelha vertical: IC 80% Bootstrap — quanto maior, mais incerteza
- Cruzamento da curva com a linha = momento do RUL

**Limiar RUL (barra lateral)**
- 5%: muito conservador (intervenção muito cedo)
- 10%: recomendado para ativos críticos (Alta Criticidade)
- 20%: razoável para ativos com redundância
- 30%+: tolerância alta (manutenção corretiva dominante)
""")


# ─── Seção 4: Crow-AMSAA ─────────────────────────────────────────────────────

def _section_crow_amsaa() -> None:
    st.markdown("### 📈 Crow-AMSAA — Análise de Degradação NHPP")
    st.markdown("""
**Crow-AMSAA** (Non-Homogeneous Poisson Process) analisa se a taxa de falha do equipamento
está **crescendo, estável ou decrescendo** ao longo do tempo — independente da distribuição
individual de cada falha.
""")

    with st.expander("📐 Modelo NHPP e Estimadores MLE"):
        st.markdown(r"""
O modelo NHPP de Crow-AMSAA assume que a **intensidade de falha** (taxa de ocorrência) segue
uma lei de potência:

$$\lambda(t) = \frac{\beta}{\lambda} \left(\frac{t}{\lambda}\right)^{\beta-1} = \lambda\beta t^{\beta-1}$$

onde:
- **β (beta):** parâmetro de forma — descreve a tendência temporal
- **λ (lambda):** intensidade base (escala do processo)

#### Estimadores MLE (tempo terminado em falha)

$$\hat{\beta} = \frac{n}{n\ln(T_{max}) - \sum_{i=1}^{n}\ln(T_i)}$$

$$\hat{\lambda} = \frac{n}{T_{max}^{\hat{\beta}}}$$

onde $T_i$ são os tempos acumulados de cada falha e $n$ é o número total de falhas.

#### Número Esperado de Falhas

$$E[N(t)] = \lambda \cdot t^{\beta}$$

No gráfico log-log, isso se torna uma linha reta: $\ln[E[N]] = \ln\lambda + \beta\ln(t)$.
""")

    with st.expander("📊 Interpretando β — Regime de Degradação"):
        st.markdown("""
| β | Regime | Taxa de Falha | Diagnóstico | Ação Recomendada |
|---|---|---|---|---|
| **β > 1,05** | **Degradação** | Crescente ↑ | Desgaste acelerado, fadiga, acúmulo de dano | Substituição preventiva por idade (TPM) |
| **β ≈ 1** (0,95–1,05) | **Estacionário** | Constante | Processo HPP — falhas aleatórias independentes | Manutenção corretiva ou inspeção por condição |
| **β < 0,95** | **Melhoria** | Decrescente ↓ | Mortalidade infantil ou processo de melhoria | Investigar causa-raiz das primeiras falhas |

**Exemplos reais em mineração:**
- Britador HP500: β ≈ 2.1 → desgaste do manto, substituição preventiva a 3.000 h
- Bomba Warman: β ≈ 1.8 → desgaste do impelidor, monitorar vibração e pressão diferencial
- Motor elétrico: β ≈ 1.0 → falhas aleatórias (sobretensão, contaminação), monitorar por condição
""")

    with st.expander("📈 Como Ler o Gráfico Log-Log"):
        st.markdown("""
**Eixos:**
- X (escala log): tempo acumulado de operação em horas
- Y (escala log): número acumulado de falhas

**Elementos:**
- **Pontos azuis:** falhas reais observadas
- **Linha vermelha:** ajuste do modelo NHPP (Crow-AMSAA MLE)

**Padrões visuais:**
- **Linha reta:** processo HPP (β = 1) — taxa de falha constante
- **Curvatura para cima (côncava):** taxa crescente (β > 1) — degradação
- **Curvatura para baixo (convexa):** taxa decrescente (β < 1) — melhoria ou mortalidade infantil

**Limitação:** O Crow-AMSAA requer mínimo 5 falhas para ajuste confiável.
Com menos de 3 falhas, o resultado não é estatisticamente significativo.
""")

    with st.expander("🖱️ Guia Prático — Aba Crow-AMSAA"):
        st.markdown("""
**KPI β — Parâmetro de Forma**
- O valor é mostrado com código de cor: vermelho (degradação), amarelo (estacionário), verde (melhoria)
- Valores extremos (β > 3 ou β < 0.3) com poucos dados podem indicar overfitting

**KPI λ — Intensidade Base**
- Valores muito pequenos (< 0.001) são normais para equipamentos confiáveis
- Use λ para comparar a "frequência base" entre ativos similares

**KPI Processo**
- Mostra o regime interpretado com texto por extenso
- Útil para relatórios técnicos e comunicação com gestão

**Gráfico**
- Clique duas vezes no gráfico para resetar o zoom
- Passe o cursor sobre os pontos para ver o número da falha e o tempo acumulado

**Integração com LDA:**
- Se LDA identifica β > 1 (Weibull desgaste) E Crow-AMSAA β > 1 (degradação NHPP),
  há **convergência de evidências** — planejar substituição preventiva com alta confiança
- Se LDA β > 1 mas Crow-AMSAA β ≈ 1, avaliar se houve manutenções intermediárias que resetaram o processo
""")


# ─── Seção 5: Machine Learning ───────────────────────────────────────────────

def _section_ml() -> None:
    st.markdown("### 🧠 Machine Learning Prescritivo")
    st.markdown("""
A aba ML combina 3 modelos para gerar recomendações prescritivas de manutenção:
**Random Forest (predição de TBF)**, **Isolation Forest (detecção de anomalias)** e
**Score de Risco ponderado**.
""")

    with st.expander("🌲 Random Forest — Predição de TBF"):
        st.markdown(r"""
#### Como Funciona

Random Forest treina $N$ árvores de decisão em subconjuntos aleatórios dos dados.
Cada árvore prediz o próximo TBF; o resultado final é a média das predições.

**Features usadas:**
- TBF anterior (lag-1, lag-2)
- Número de falhas acumuladas
- Posição temporal (índice cronológico)
- Horímetro relativo

**Divisão temporal 80/20:**
O modelo usa os 80% mais antigos para treino e os 20% mais recentes para teste,
simulando predição real (não usa dados futuros para treinar).

#### Métricas de Performance

| Métrica | Fórmula | Interpretação |
|---|---|---|
| **MAE** | $\frac{1}{n}\sum|y_i - \hat{y}_i|$ | Erro médio em horas — mais interpretável |
| **R²** | $1 - \frac{SS_{res}}{SS_{tot}}$ | Variância explicada: 1.0 = perfeito, < 0 = pior que média |
| **RMSE** | $\sqrt{\frac{1}{n}\sum(y_i-\hat{y}_i)^2}$ | Penaliza erros grandes — mais sensível a outliers |

> **R² > 0.7:** modelo confiável para predição. **R² < 0.3:** dados insuficientes ou alta variabilidade aleatória.

#### Importância das Features

O gráfico de importância mostra quais variáveis mais influenciam o próximo TBF.
Se o lag-1 (TBF anterior) domina, o processo tem **memória** — bom indicativo de degradação cumulativa.
""")

    with st.expander("🔍 Isolation Forest — Detecção de Anomalias"):
        st.markdown(r"""
#### Como Funciona

Isolation Forest detecta anomalias **isolando** pontos incomuns em árvores aleatórias.
Pontos anômalos são mais fáceis de isolar (precisam de menos divisões).

**Score de Anomalia:**

$$\text{Score} = 2^{-E[h(x)]/c(n)}$$

onde $E[h(x)]$ é a profundidade média de isolamento e $c(n)$ é a normalização.

- Score próximo de **1.0:** ponto muito incomum → anomalia
- Score próximo de **0.5:** ponto típico da distribuição

**Interpretação na manutenção:**
- **TBF anormalmente curto (< Q1 - 1.5·IQR):** mortalidade infantil ou falha de instalação
- **TBF anormalmente longo (> Q3 + 1.5·IQR):** possível censura não registrada ou equipamento em boas condições
- **Cluster de anomalias consecutivas:** processo de degradação acelerada em andamento
""")

    with st.expander("⚠️ Score de Risco — Composição e Interpretação"):
        st.markdown("""
O Score de Risco integra 4 componentes em um índice 0–100:

| Componente | Peso Padrão | Fonte | Como Aumenta o Risco |
|---|---|---|---|
| **Tendência NHPP** | 30 pts | Crow-AMSAA β | β > 1 (degradação ativa) |
| **Anomalias IF** | 25 pts | Isolation Forest | % de pontos anômalos detectados |
| **Confiabilidade** | 30 pts | R(t₀) LDA/Weibull | R(t₀) baixo (equipamento perto do fim da vida) |
| **Proximidade TBF** | 15 pts | Predição RF vs. histórico | TBF atual próximo ao limite superior histórico |

**Faixas de Risco:**

| Score | Nível | Cor | Ação Recomendada |
|---|---|---|---|
| 0–29 | **BAIXO** | 🟢 Verde | Monitoramento padrão |
| 30–49 | **MÉDIO** | 🟡 Amarelo | Aumentar frequência de inspeção |
| 50–69 | **ALTO** | 🟠 Laranja | Planejar intervenção preventiva |
| 70–100 | **CRÍTICO** | 🔴 Vermelho | Intervenção urgente — parada programada |
""")

    with st.expander("🔧 PMO — Manutenção Preventiva Ótima"):
        st.markdown(r"""
O modelo PMO calcula o **intervalo ótimo de manutenção preventiva** que minimiza o custo total esperado.

$$C(t_p) = \frac{C_p \cdot R(t_p) + C_u \cdot F(t_p)}{\int_0^{t_p} R(x)\,dx}$$

onde:
- $C_p$ = custo de manutenção preventiva (planejada)
- $C_u$ = custo de manutenção corretiva (não planejada) — **inclui todos os custos**
- $R(t_p)$ = probabilidade de sobreviver até $t_p$
- $F(t_p)$ = probabilidade de falhar antes de $t_p$
- $\int_0^{t_p} R(x)\,dx$ = vida média esperada no ciclo de renovação

**O ótimo $t_p^*$ minimiza $C(t_p)$** — equilíbrio entre fazer MP cedo demais (custo desnecessário)
e tarde demais (risco de falha com custo alto).

> **Custo Corretivo Real ($C_u$):** deve incluir **tudo** que a falha não planejada gera:
> custo de reparo + peças de reposição emergenciais + mão de obra extra (horas extras, terceiros) +
> impacto na produção (lucro cessante) + penalidades contratuais + custo de logística emergencial.
> Um $C_u$ subestimado leva a um $t_p^*$ muito longo (pouco preventivo).
""")

    with st.expander("🖱️ Guia Prático — Aba Machine Learning"):
        st.markdown("""
**Sub-aba Predição RF**
- Gráfico superior: TBFs reais (azul) vs. preditos (vermelho) no conjunto de teste
- Gráfico inferior: importância das features — feature dominante = processo com memória
- Se MAE > 30% do MTBF médio: modelo com baixa precisão — coletar mais dados

**Sub-aba Anomalias**
- Pontos em vermelho = anomalias detectadas pelo Isolation Forest
- Verifique se as anomalias coincidem com eventos conhecidos (troca de operador, parada não programada, etc.)
- Alta densidade de anomalias em período recente = degradação acelerada

**Sub-aba Score de Risco**
- Gauge circular: leitura rápida do risco global
- Barras de componentes: identificar qual fator está elevando o risco
- Recomendação prescritiva gerada automaticamente pelo sistema

**Sub-aba PMO**
- Campo `Cp (R$)`: custo de uma MP padrão (revisão preventiva com peças planejadas)
- Campo `Cu (R$)`: custo total de uma falha não planejada (ver cálculo acima)
- Slider `t_p (h)`: mova para ver como o custo varia com o intervalo preventivo
- Linha vertical vermelha = ponto ótimo calculado pelo modelo
- Se `Cu/Cp < 2`: a MP preventiva pouco se justifica economicamente — avaliar CBM (inspeção por condição)
- Se `Cu/Cp > 5`: MP preventiva com alta justificativa — ajustar intervalo para próximo de `t_p*`
""")


# ─── Seção 6: PMO ────────────────────────────────────────────────────────────

def _section_pmo() -> None:
    st.markdown("### 🔧 PMO — Preventive Maintenance Optimization")
    st.markdown("""
**PMO** usa a teoria de **renovação de Barlow-Hunter** para encontrar o intervalo de manutenção
preventiva que minimiza o custo total esperado por unidade de tempo.
""")

    with st.expander("📐 Teoria de Renovação e Modelo de Custo"):
        st.markdown(r"""
#### Premissas do Modelo

1. **Renovação perfeita:** após cada MP preventiva ou corretiva, o equipamento volta a AGEM = 0 (como novo)
2. **MP interrompe envelhecimento:** se a MP ocorre em $t_p$ sem falha prévia, o ciclo reinicia
3. **Falha antes de $t_p$:** ocorre com probabilidade $F(t_p)$ → manutenção corretiva ao custo $C_u$

#### Função de Custo por Unidade de Tempo

$$C(t_p) = \frac{C_p \cdot R(t_p) + C_u \cdot F(t_p)}{\int_0^{t_p} R(x)\,dx}$$

O denominador é a **vida esperada no ciclo** — tempo médio até MP ou falha.

#### Derivada e Condição de Otimalidade

O $t_p^*$ ótimo satisfaz:

$$h(t_p^*) = \frac{C(t_p^*) - C_p/M(t_p^*)}{C_u - C_p}$$

onde $M(t_p) = \int_0^{t_p} R(x)\,dx$ e $h(t_p)$ é a taxa de falha instantânea.

Na prática, o sistema resolve numericamente: avalia $C(t_p)$ em 500 pontos e retorna o mínimo.
""")

    with st.expander("💰 Como Calcular Cu Corretamente"):
        st.markdown("""
**Cu é o custo TOTAL de uma falha não planejada**, não apenas o custo de reparo.
A subestimação de Cu é o erro mais comum na implementação de PMO.

#### Composição Completa do Cu

| Componente | Descrição | Estimativa Típica |
|---|---|---|
| **Custo de Reparo** | Mão de obra corretiva (horas extras, chamadas noturnas) | +40% vs. custo preventivo |
| **Peças de Emergência** | Frete expresso, compra de urgência, markup emergencial | +60% vs. peças planejadas |
| **Lucro Cessante** | Produção perdida × margem de contribuição × horas de parada | Maior componente em ativos críticos |
| **Dano Colateral** | Dano a equipamentos adjacentes por falha catastrófica | Variável — estimar por histórico |
| **Penalidades** | Multas contratuais, penalidades de SLA | Se aplicável |
| **Custo de Oportunidade** | Custo de logística emergencial, gestão de crise | 5–15% do custo total |

#### Exemplo Prático — Britador HP500

| Item | Valor |
|---|---|
| Mão de obra corretiva (16h × R$ 80/h × 2 técnicos) | R$ 2.560 |
| Peças emergenciais (manto + pinhão com frete aéreo) | R$ 85.000 |
| Lucro cessante (8h × 500 t/h × R$ 12/t margem) | R$ 48.000 |
| Dano à coroa e carcaça (estimativa histórica) | R$ 30.000 |
| **Cu Total** | **R$ 165.560** |
| **Cp (MP padrão)** | R$ 28.000 |
| **Razão Cu/Cp** | 5,9× → alta justificativa para MP |

Com esses valores e β = 2.1, η = 3.200 h → **t_p* ≈ 2.750 h** (MP antes da vida característica).
""")

    with st.expander("🖱️ Guia Prático — Sub-aba PMO"):
        st.markdown("""
**Campo Cp (R$)**
- Custo de uma revisão preventiva planejada completa
- Inclui: mão de obra (horas normais), peças de reposição planejadas, consumíveis
- Para britador HP500: R$ 25.000–35.000

**Campo Cu (R$)**
- Custo total de falha não planejada — veja composição acima
- **Mínimo**: deve ser > 2× Cp para que a MP faça sentido econômico

**Curva de Custo**
- Eixo X: intervalo preventivo t_p em horas
- Eixo Y: custo por hora de operação (R$/h)
- Mínimo da curva = intervalo ótimo t_p*
- Linha vertical vermelha marca o ótimo

**Interpretação da curva:**
- Curva com mínimo bem definido (forma de U): solução única confiável
- Curva monotonicamente decrescente: Cu/Cp muito baixo — MP pode não ser a melhor estratégia
- Curva com mínimo muito à esquerda (< 500 h): verificar se β > 1.5 e Cu está completo

**ROI da MP:**
O sistema calcula a economia anual comparando o custo total com MP vs. apenas corretiva.
Essa métrica justifica o investimento em manutenção preventiva para a gestão.
""")


# ─── Seção 7: ISO 14224 ───────────────────────────────────────────────────────

def _section_iso14224() -> None:
    st.markdown("### 📋 ISO 14224 — Taxonomia de Falhas")
    st.markdown("""
**ISO 14224** é o padrão internacional para coleta e intercâmbio de dados de confiabilidade
e manutenção em equipamentos industriais. O APM implementa esta taxonomia na geração
de datasets enriquecidos e na análise de causa raiz.
""")

    with st.expander("📊 Estrutura Taxonômica"):
        st.markdown("""
A ISO 14224 organiza as informações em hierarquia:

```
Instalação
└── Unidade de Equipamento
    └── Sistema
        └── Subcomponente
            └── Evento de Falha
                ├── Modo de Falha (como falhou)
                ├── Causa Raiz (por que falhou)
                └── Consequência (impacto operacional)
```

#### Modos de Falha — Britadores Cônicos (exemplo)

| Modo de Falha | Subcomponente | Causa Raiz Típica |
|---|---|---|
| Desgaste excessivo | Manto / Côncavo | Abrasividade da rocha, granulometria inadequada |
| Vibração anormal | Mancal do eixo principal | Desequilíbrio, contaminação do lubrificante |
| Superaquecimento | Sistema de lubrificação | Falha na bomba de óleo, entupimento do filtro |
| Trinca estrutural | Carcaça | Sobrecarga, material incompetente na alimentação |
| Falha elétrica | Motor de acionamento | Sobretensão, falha de isolamento |

#### Campos ISO 14224 no Dataset Enriquecido

| Campo | Descrição | Exemplo |
|---|---|---|
| `Modo_Falha` | Como a falha se manifestou | "Desgaste excessivo do manto" |
| `Causa_Raiz` | Por que ocorreu a falha | "Abrasividade elevada (SiO2 > 35%)" |
| `Subcomponente` | Parte que falhou | "Manto côncavo superior" |
| `TTR` | Time To Repair em horas | 14.5 h |
| `Criticidade` | Alta / Média / Baixa | "Alta" |
| `Tipo_Manutencao` | Corretiva / Preventiva / Preditiva | "Corretiva de emergência" |
| `Custo_Reparo_BRL` | Custo do evento (R$) | R$ 87.400 |
| `Impacto_Producao_t` | Produção perdida (toneladas) | 3.200 t |
| `Lucro_Cessante_BRL` | Impacto financeiro da produção perdida | R$ 38.400 |
""")

    with st.expander("🔬 Como Usar o Dataset ISO 14224 no APM"):
        st.markdown("""
**Habilitando o Dataset:**
Marque "Enriquecimento ISO 14224" na barra lateral antes de executar a simulação.
Isso gera a aba "🗃️ Dataset ISO 14224" com o dataset completo.

**Filtros disponíveis:**
- Por Modo de Falha: analisar apenas falhas de um tipo específico
- Por Criticidade: focar nos eventos de alta criticidade
- Por Tipo de Manutenção: separar corretivas de preventivas

**Tabelas de análise:**
- Modos de Falha × Quantidade: identificar os mais frequentes (ABC de falhas)
- Causa Raiz × Quantidade: priorizar ações de causa raiz
- Custo por Subcomponente: identificar os componentes com maior impacto financeiro

**Download CSV:**
O dataset completo pode ser baixado para análise no Excel ou CMMS.
Útil para alimentar KPIs de confiabilidade e relatórios gerenciais.

**Aplicação prática:**
Use o Diagrama de Pareto (modo de falha × custo) para priorizar:
1. Os 20% dos modos de falha que causam 80% dos custos = foco do plano de manutenção
2. Calcular MTTR por subcomponente para dimensionamento de equipe e estoque
3. Identificar padrões de causa raiz para ações de engenharia (redesign, materiais alternativos)
""")


# ─── Seção 8: Cases ──────────────────────────────────────────────────────────

def _section_cases() -> None:
    st.markdown("### 🏭 Cases de Aplicação — Mineração")
    st.markdown("""
Casos reais de aplicação do modelo APM em equipamentos de mineração,
com parâmetros, diagnósticos e ROI calculados.
""")

    with st.expander("🪨 Case 1 — Britador Cônico HP500", expanded=True):
        st.markdown("""
**Contexto:** Britador primário em planta de cobre. Histórico de 3 anos, 42 eventos registrados.

**Parâmetros LDA (Weibull MLE):**
- β = 2,1 → desgaste ativo (taxa de falha crescente)
- η = 3.200 h → vida característica
- MTTF = 2.842 h → tempo médio entre falhas
- Modelo vencedor: Weibull (ΔAICc = 8,3 → significativamente melhor)

**Análise Crow-AMSAA:**
- β_NHPP = 2,3 → degradação confirmada
- Tendência de aumento na frequência de falhas nos últimos 18 meses

**Score de Risco:** 72/100 (CRÍTICO) — horímetro atual 3.850 h, acima da vida característica

**PMO:**
- Cp = R$ 28.000 | Cu = R$ 165.000 (inclui lucro cessante de R$ 48.000)
- t_p* = 2.750 h → MP a cada 2.750 h de operação
- Economia anual estimada: R$ 312.000 vs. estratégia corretiva

**RUL (no horímetro de 3.850 h):**
- R(t₀) = 18% → zona crítica
- RUL = +180 h [50 — 380 h] → intervenção urgente
- Horizonte: 4.030 h → planejar parada na próxima semana

**Diagnóstico e Recomendação:**
Substituição imediata do manto côncavo. Avaliar condição da coroa e pinhão.
Implementar monitoramento de vibração para antecipar próximo ciclo.
""")

    with st.expander("💧 Case 2 — Bombas Centrífugas Warman 8×6 (frota de 6 unidades)"):
        st.markdown("""
**Contexto:** Frota de 6 bombas de polpa em circuito de flotação. Análise de frota com dados consolidados.

**Parâmetros LDA por bomba (média da frota):**
- β = 1,8 → desgaste moderado
- η = 2.800 h → vida característica
- Alta dispersão entre unidades (σ_bootstrap largo) → variabilidade operacional entre posições

**Análise Crow-AMSAA (frota consolidada):**
- β_NHPP = 1,4 → tendência de degradação moderada
- Duas bombas com β_NHPP > 2,0 → degradação acelerada (posições P3 e P5)

**Descoberta ML:**
- Isolation Forest detectou cluster de anomalias nas bombas P3 e P5 nos últimos 200 h
- TBF médio caindo de 420 h para 180 h nas últimas 5 falhas de P3

**PMO (por bomba):**
- Cp = R$ 8.500 | Cu = R$ 42.000
- t_p* = 2.200 h para frota em geral
- Para P3 e P5: intervenção imediata recomendada (não esperar t_p*)

**ROI da implantação APM (frota de 6 bombas):**
- Antes da APM: 18 falhas não planejadas/ano × R$ 42.000 = R$ 756.000
- Com APM (redução de 60%): 7 falhas/ano × R$ 42.000 + 20 MPs × R$ 8.500 = R$ 464.000
- **Economia anual: R$ 292.000 | ROI do APM: < 6 meses**
""")

    with st.expander("🏗️ Case 3 — Transportador de Correia (Redutores de Velocidade)"):
        st.markdown("""
**Contexto:** Sistema de 4 transportadores de correia com redutores Flender. Histórico de 5 anos.

**Parâmetros LDA:**
- β = 2,8 → desgaste pronunciado (componente com vida limitada bem definida)
- η = 5.500 h → vida característica alta (equipamento bem dimensionado)
- MTTF = 4.891 h → ~204 dias de operação contínua (24 h/dia)

**Análise Crow-AMSAA:**
- β_NHPP = 1,6 → degradação gradual
- Ponto de inflexão identificado em ~4.000 h (aceleração da degradação)

**RUL para o redutor com maior horímetro (5.200 h):**
- R(t₀) = 22% → zona de alerta
- RUL = +320 h [150 — 580 h] → ~13 dias para planejamento
- IC largo: variabilidade na manutenção entre paradas de mina

**PMO:**
- Cp = R$ 45.000 (revisão do redutor + troca de rolamentos e vedações)
- Cu = R$ 280.000 (inclui 8h × 2.400 t/h × R$ 15/t = R$ 288.000 lucro cessante)
- t_p* = 4.800 h → MP preventiva a cada 4.800 h
- Redutores com horímetro 4.500–5.000 h: prioridade máxima

**Implementação:**
Com APM, a mina implementou janelas de manutenção programadas nas paradas operacionais mensais.
Resultado: zero falhas não planejadas de redutor em 18 meses → economia de R$ 840.000.
""")


# ─── Seção 9: Glossário ──────────────────────────────────────────────────────

def _section_glossario() -> None:
    st.markdown("### 📚 Glossário Técnico")
    st.markdown("Definições dos termos técnicos usados no APM Analytics.")

    with st.expander("A–C"):
        st.markdown("""
**AICc (Critério de Akaike Corrigido)**
Medida de qualidade do ajuste estatístico que penaliza modelos com muitos parâmetros.
Permite comparar distribuições diferentes em bases iguais. Menor = melhor.

**Anomalia (Isolation Forest)**
Evento com comportamento muito diferente da distribuição normal dos TBFs.
Pode indicar mortalidade infantil, erro de registro ou degradação acelerada.

**Beta (β) — Weibull**
Parâmetro de forma da distribuição Weibull que determina o regime de falha:
β < 1 = infantil | β = 1 = aleatório | β > 1 = desgaste.

**Beta (β) — Crow-AMSAA**
Parâmetro do modelo NHPP que indica se a taxa de falha está crescendo (β > 1),
estável (β ≈ 1) ou decrescendo (β < 1) ao longo do tempo.

**B10, B50, B90 Life**
Tempo em que 10%, 50% ou 90% dos equipamentos terão falhado. B50 = mediana da vida.
Calculado como o percentil correspondente da distribuição ajustada.

**Censura (Right-censored)**
Registro em que o equipamento estava em operação quando o dado foi coletado — a falha
ainda não ocorreu. Essencial para análise de confiabilidade realista (não descartar dados sem falha).

**CHF (Cumulative Hazard Function)**
Hazard acumulado H(t) = -ln[R(t)]. Indica o dano acumulado ao longo da vida.
Útil em modelos de degradação onde o dano se acumula progressivamente.

**Confiabilidade R(t)**
Probabilidade de um componente operar sem falha por t horas em condições especificadas.
R(t) = 1 - F(t) = P(T > t).

**Cp (custo preventivo)**
Custo total de uma manutenção preventiva planejada: mão de obra + peças + logística planejada.

**Cu (custo corretivo)**
Custo total de uma falha não planejada: reparo + peças emergenciais + lucro cessante + danos colaterais.

**Crow-AMSAA**
Modelo NHPP (Non-Homogeneous Poisson Process) proposto por Crow (1974) baseado no
modelo de Duane para análise de crescimento de confiabilidade. Adotado pela NASA e DOD.
""")

    with st.expander("D–H"):
        st.markdown("""
**Disponibilidade (A)**
Fração do tempo que um equipamento está operacional.
Estimativa no APM: A ≈ R(MTTF) × 100%.

**Distribuição Exponencial**
Caso especial da Weibull com β = 1. Taxa de falha constante — processo sem memória (HPP).
MTBF = 1/λ. Usada para componentes eletrônicos e falhas aleatórias.

**Distribuição Lognormal**
Modela falhas onde o logaritmo do TBF segue distribuição normal. Parâmetros: μ (log-média)
e σ (log-desvio). Comum em processos de corrosão e fadiga de alto ciclo.

**Distribuição Normal (Gaussiana)**
Distribuição simétrica em torno da média μ com desvio σ. Raramente a mais adequada em
confiabilidade (pode gerar valores negativos), mas útil para desgaste muito regular.

**Distribuição Weibull**
A mais versátil e utilizada em análise de confiabilidade. Parâmetros β (forma) e η (escala).
Desenvolvida por Waloddi Weibull em 1951, adotada como padrão na engenharia de confiabilidade.

**EDA (Exploratory Data Analysis)**
Análise exploratória dos dados: histogramas, boxplots, estatísticas descritivas e testes
de outlier para entender o comportamento dos TBFs antes do ajuste paramétrico.

**Eta (η) — Vida Característica**
Parâmetro de escala da Weibull. No horímetro η, exatamente 63,2% dos equipamentos
terão falhado, independente de β.

**Feature Importance (Random Forest)**
Medida de quanto cada variável contribui para a predição do modelo RF.
Calculada como a redução média de impureza nas árvores de decisão.

**HF (Hazard Function) / Taxa de Falha h(t)**
Risco instantâneo de falha a cada hora, dado que o equipamento ainda está operando.
Weibull: h(t) = (β/η)(t/η)^(β-1). Crescente se β > 1, constante se β = 1, decrescente se β < 1.

**HPP (Homogeneous Poisson Process)**
Processo de Poisson com taxa constante — equivalente a Weibull com β = 1 ou Exponencial.
Sem memória: o número de falhas futuras não depende do histórico passado.
""")

    with st.expander("I–R"):
        st.markdown("""
**IC 80% / IC 95% (Intervalo de Confiança)**
Faixa de valores dentro da qual o parâmetro verdadeiro está com probabilidade dada.
IC 80% Bootstrap: estimado por reamostragem paramétrica (300 iterações).
IC 95%: calculado pela aproximação de Wald binomial.

**Isolation Forest**
Algoritmo de detecção de anomalias baseado em florestas de isolamento.
Anomalias são detectadas por serem isoladas mais facilmente (menores caminhos na árvore).

**ISO 14224**
Norma internacional para coleta, intercâmbio e apresentação de dados de confiabilidade
e manutenção para equipamentos na indústria de petróleo, gás e petroquímica.
Amplamente adotada na mineração e indústria pesada.

**IQR (Interquartile Range)**
Amplitude interquartílica = Q3 - Q1. Usado para detecção de outliers:
pontos fora de [Q1 - 1,5·IQR, Q3 + 1,5·IQR] são considerados outliers.

**KS Test (Kolmogorov-Smirnov)**
Teste estatístico de aderência que compara a distribuição empírica com o modelo ajustado.
p > 0.05: modelo não rejeitado | p < 0.05: ajuste suspeito.

**Lucro Cessante**
Resultado financeiro não gerado pela parada não planejada do equipamento.
Calculado como: horas de parada × capacidade de produção × margem de contribuição unitária.

**MAE (Mean Absolute Error)**
Erro médio absoluto das predições do Random Forest. Mais interpretável que RMSE.
MAE em horas: erro médio na predição do próximo TBF.

**MLE (Maximum Likelihood Estimation)**
Método de estimação de parâmetros que maximiza a probabilidade de observar os dados registrados.
Padrão na análise de confiabilidade — lida corretamente com dados censurados.

**MTTF (Mean Time To Failure)**
Tempo médio até a falha: MTTF = ∫₀^∞ R(t)dt. Para Weibull: MTTF = η·Γ(1 + 1/β).
Sinônimo de MTBF quando o equipamento é reparado e colocado de volta em operação.

**NHPP (Non-Homogeneous Poisson Process)**
Processo de Poisson com taxa variável no tempo. Modela sistemas reparáveis onde a taxa
de falha muda com o histórico acumulado. Base do modelo Crow-AMSAA.

**PMO (Preventive Maintenance Optimization)**
Modelo matemático de Barlow-Hunter (1960) que minimiza o custo total esperado por
unidade de tempo determinando o intervalo ótimo de manutenção preventiva.

**R² (Coeficiente de Determinação)**
Fração da variância explicada pelo modelo. R² = 1 - SS_res/SS_tot.
R² = 1.0: predição perfeita | R² = 0: não melhor que a média | R² < 0: pior que a média.

**Random Forest**
Ensemble de árvores de decisão com bootstrap de amostras e features aleatórias.
Robusto contra overfitting — usado para predição do próximo TBF.

**RUL (Remaining Useful Life)**
Vida útil remanescente — horas adicionais que o equipamento pode operar antes de atingir
o limiar de confiabilidade configurado (padrão: 10%).

**R(t) / SF (Survival Function)**
Função de confiabilidade (sobrevivência): probabilidade de não falhar até t horas.
R(t) = 1 - F(t) = P(T > t). Principal função para análise de confiabilidade.
""")

    with st.expander("S–Z"):
        st.markdown("""
**Score de Risco**
Índice composto 0–100 que integra 4 componentes: tendência NHPP (30pts),
anomalias Isolation Forest (25pts), confiabilidade atual (30pts) e proximidade TBF (15pts).

**Spearman (ρ)**
Correlação de rank entre posição temporal e TBF. ρ negativo + significativo (p < 0.05)
indica degradação sistemática ao longo do tempo (TBFs diminuindo).

**TBF (Time Between Failures)**
Tempo entre falhas consecutivas em horas. Principal variável de análise de confiabilidade.
Calculado como diferença entre horímetros (ou datas) de falhas consecutivas.

**TTR (Time To Repair)**
Tempo de reparo em horas — da detecção da falha até a liberação do equipamento.
Usado para calcular disponibilidade e dimensionar equipes de manutenção.

**t_p* (Intervalo Ótimo PMO)**
Intervalo de manutenção preventiva que minimiza o custo total esperado C(t_p).
Resultado do modelo de otimização Barlow-Hunter.

**Weibull Plot (Probability Plot)**
Gráfico que lineariza os dados de falha na escala Weibull para avaliar aderência visual.
Pontos próximos à linha diagonal = bom ajuste da distribuição Weibull.

**λ (Lambda) — Exponencial**
Taxa de falha constante da distribuição exponencial. MTBF = 1/λ.

**λ (Lambda) — Crow-AMSAA**
Intensidade base do processo NHPP. Determina a frequência absoluta de falhas,
enquanto β determina a tendência temporal.

**η (Eta) — Vida Característica**
Parâmetro de escala da Weibull: horímetro em que 63,2% dos equipamentos terão falhado.
""")
