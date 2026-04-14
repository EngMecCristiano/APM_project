# APM Analytics — Asset Performance Management

[![Deploy on Railway](https://railway.com/button.svg)](https://railway.com)
![Status](https://img.shields.io/badge/status-production-brightgreen)
![Python](https://img.shields.io/badge/python-3.12-blue)
![FastAPI](https://img.shields.io/badge/FastAPI-0.110-009688)
![Streamlit](https://img.shields.io/badge/Streamlit-1.32-FF4B4B)
![Docker](https://img.shields.io/badge/Docker-Compose-2496ED)
![License](https://img.shields.io/badge/license-MIT-green)

Sistema de análise de confiabilidade e manutenção preditiva para equipamentos industriais.

Combina **Engenharia de Confiabilidade clássica** (Weibull, Crow-AMSAA, RUL, PMO) com **Machine Learning** (Random Forest, Isolation Forest) em uma arquitetura de microserviços containerizada.

---

## Demo ao Vivo

**[https://apm-app-production.up.railway.app](https://apm-app-production.up.railway.app)**

> Acesse, selecione um equipamento, clique em **Executar Simulação** e explore os resultados.

---

## Arquitetura

```
┌─────────────────────────────────────────────────────────┐
│                   Docker Compose / Railway              │
│                                                         │
│  ┌──────────────────┐   REST    ┌──────────────────────┐│
│  │  Frontend        │──────────▶│  Backend             ││
│  │  Streamlit       │           │  FastAPI             ││
│  │  porta 8502      │           │  porta 8002          ││
│  └──────────────────┘           └──────────────────────┘│
└─────────────────────────────────────────────────────────┘
```

- **Backend (FastAPI)** — toda a computação: ajuste de distribuições, MLE, ML, RUL, relatório PDF
- **Frontend (Streamlit)** — interface dark, cliente fino, apenas chamadas à API e renderização

---

## Funcionalidades

### Análise de Dados de Vida (LDA)
- Ajuste de 4 distribuições: Weibull, Lognormal, Normal, Exponencial
- Seleção automática por critério AICc
- Kaplan-Meier sobreposto à curva paramétrica
- QQ Plot para validação do ajuste
- Unidades corretas por função: SF, CDF, PDF, HF, CHF

### Vida Útil Remanescente (RUL)
- Confiabilidade Condicional `R(t|T₀) = R(T₀+t) / R(T₀)`
- Intervalo de confiança P10–P90 via Bootstrap Paramétrico (N configurável)
- Limiar de intervenção configurável pelo usuário

### Degradação — Crow-AMSAA / NHPP
- Estimação MLE do modelo de Power Law
- Identificação de regime: degradação, burn-in ou aleatório
- Gráfico log-log com curva ajustada

### Machine Learning Preditivo
- Forecast do próximo TBF com Random Forest
- Detecção de anomalias com Isolation Forest
- Análise de tendência com regressão e CUSUM
- Risk Score composto (0–100) com 4 componentes
- Feature Importance e interpretabilidade

### Otimização de Manutenção (PMO)
- Política de substituição por idade via Teoria da Renovação
- Curva de custo `C(tp)` e intervalo ótimo `tp*`
- Relação custo preventivo / custo corretivo configurável

### Simulação de Dados
- Simulador paramétrico Weibull e Lognormal com ruído gaussiano, mortalidade infantil e fadiga sistêmica
- Equipamento personalizado com parâmetros β/η (Weibull) ou μ/σ (Lognormal)
- Simulação enriquecida ISO 14224: modo de falha, causa raiz, TTR, custo, impacto de produção
- Importação de CSV real com mapeamento de colunas

### Histórico Persistido
- TBFs acumulados por ativo em Parquet (volume Docker / Railway)
- Merge automático entre sessões — modelo melhora com o tempo
- Gestão por TAG: visualizar, incluir ou excluir histórico

### Relatório PDF
- Gerado pelo backend com cabeçalho em todas as páginas
- Inclui identificação do ativo, RUL com IC, modelos, Crow-AMSAA, ML e auditoria

---

## Stack

| Camada | Tecnologias |
|---|---|
| **Backend** | Python 3.12, FastAPI, SciPy, NumPy, Pandas, Scikit-learn, ReportLab |
| **Frontend** | Streamlit, Plotly |
| **DevOps** | Docker, Docker Compose, Railway |
| **Dados** | Parquet (histórico), Pydantic (validação) |

---

## Início Rápido (local)

### Pré-requisitos
- Docker e Docker Compose instalados

### Subir o ambiente

```bash
# Clonar o repositório
git clone https://github.com/EngMecCristiano/APM_project.git
cd APM_project

# Copiar e ajustar variáveis de ambiente
cp .env.example .env

# Subir os containers
docker compose up -d --build

# Acompanhar os logs
docker compose logs -f
```

### Acessar

| Serviço | URL |
|---|---|
| Frontend | http://localhost:8502 |
| Backend API | http://localhost:8002 |
| Docs da API | http://localhost:8002/docs |

---

## Estrutura do Projeto

```
APM_project/
├── backend/
│   ├── config/          # Configurações e settings
│   ├── routers/         # Endpoints FastAPI (analysis, ml, maintenance, report, history)
│   ├── schemas/         # Modelos Pydantic
│   ├── services/        # Lógica de negócio (reliability, ml, simulator, history)
│   ├── Dockerfile
│   ├── main.py
│   └── requirements.txt
├── frontend/
│   ├── components/      # Dashboard, sidebar, charts, tabs, ui_helpers
│   │   └── tabs/        # LDA, RUL, NHPP, ML, Audit
│   ├── styles/          # Tema dark CSS + Plotly
│   ├── Dockerfile
│   ├── app.py
│   ├── api_client.py
│   └── requirements.txt
├── images/              # Assets visuais
├── docker-compose.yml
├── railway.toml         # Configuração de deploy Railway
├── Makefile
├── .env.example
└── README.md
```

---

## Variáveis de Ambiente

Copie `.env.example` para `.env` e ajuste conforme necessário:

```env
APP_ENV=development
BACKEND_URL=http://apm_backend:8002
TZ=America/Sao_Paulo
```

### Deploy Railway
Configure as variáveis em cada serviço no painel Railway:

| Variável | Backend | Frontend |
|---|---|---|
| `BACKEND_URL` | — | URL pública do backend |
| `PYTHONPATH` | `/app` | `/app` |
| `TZ` | `America/Sao_Paulo` | `America/Sao_Paulo` |
| `ALLOWED_ORIGINS` | URL pública do frontend | — |

---

## Comandos Úteis

```bash
# Parar os containers
docker compose down

# Rebuild completo
docker compose up -d --build

# Logs do backend
docker compose logs -f apm_backend

# Logs do frontend
docker compose logs -f apm_frontend

# Acessar o container do backend
docker exec -it apm_backend bash
```

---

## Segurança

- CORS restrito à origem do frontend em produção (via `ALLOWED_ORIGINS`)
- Sem credenciais ou segredos no repositório
- Validação de entrada via Pydantic em todos os endpoints
- Histórico isolado por TAG de ativo

---

## Licença

MIT License — consulte o arquivo [LICENSE](LICENSE) para detalhes.
