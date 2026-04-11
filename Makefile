# ==============================================================================
# Makefile - Automação de tarefas do APM Project
# ==============================================================================
# Comandos disponíveis:
#   make help      - Mostra ajuda
#   make install   - Instala dependências localmente
#   make build     - Build da imagem Docker
#   make up        - Sobe os containers
#   make down      - Derruba os containers
#   make logs      - Mostra logs
#   make test      - Executa testes
#   make clean     - Limpa arquivos temporários
#   make shell     - Acessa shell do container
# ==============================================================================

.PHONY: help install build up down logs test clean shell

# Variáveis
DOCKER_COMPOSE = docker-compose
DOCKER_COMPOSE_PROFILES = $(DOCKER_COMPOSE) --profile full

# Cores para output
GREEN = \033[0;32m
YELLOW = \033[1;33m
RED = \033[0;31m
NC = \033[0m # No Color

help:
	@echo "$(GREEN)APM Project - Comandos Disponíveis$(NC)"
	@echo ""
	@echo "$(YELLOW)make install$(NC)   - Instala dependências localmente"
	@echo "$(YELLOW)make build$(NC)     - Build da imagem Docker"
	@echo "$(YELLOW)make up$(NC)        - Sobe os containers"
	@echo "$(YELLOW)make down$(NC)      - Derruba os containers"
	@echo "$(YELLOW)make logs$(NC)      - Mostra logs dos containers"
	@echo "$(YELLOW)make test$(NC)      - Executa testes"
	@echo "$(YELLOW)make clean$(NC)     - Limpa arquivos temporários"
	@echo "$(YELLOW)make shell$(NC)     - Acessa shell do container"
	@echo ""

install:
	@echo "$(GREEN)Instalando dependências...$(NC)"
	pip install -r requirements.txt
	@echo "$(GREEN)✅ Instalação concluída$(NC)"

build:
	@echo "$(GREEN)Build da imagem Docker...$(NC)"
	$(DOCKER_COMPOSE) build --no-cache
	@echo "$(GREEN)✅ Build concluído$(NC)"

up:
	@echo "$(GREEN)Subindo containers...$(NC)"
	mkdir -p models logs data
	$(DOCKER_COMPOSE) up -d
	@echo "$(GREEN)✅ Containers em execução$(NC)"
	@echo "$(GREEN)Acesse: http://localhost:8501$(NC)"

down:
	@echo "$(YELLOW)Derrubando containers...$(NC)"
	$(DOCKER_COMPOSE) down
	@echo "$(GREEN)✅ Containers removidos$(NC)"

logs:
	$(DOCKER_COMPOSE) logs -f

test:
	@echo "$(GREEN)Executando testes...$(NC)"
	docker exec apm_terminal_analytics python -m pytest tests/ -v

clean:
	@echo "$(YELLOW)Limpando arquivos temporários...$(NC)"
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete
	find . -type f -name "*.log" -delete
	rm -rf .pytest_cache/ .coverage htmlcov/
	@echo "$(GREEN)✅ Limpeza concluída$(NC)"

shell:
	@echo "$(GREEN)Acessando shell do container...$(NC)"
	docker exec -it apm_terminal_analytics bash

dev:
	@echo "$(GREEN)Iniciando ambiente de desenvolvimento...$(NC)"
	$(DOCKER_COMPOSE) --profile dev up -d
	@echo "$(GREEN)✅ Ambiente dev disponível$(NC)"
	@echo "$(GREEN)Jupyter Lab: http://localhost:8888 (token: apm_analytics_2024)$(NC)"

restart:
	@echo "$(YELLOW)Reiniciando containers...$(NC)"
	$(DOCKER_COMPOSE) restart
	@echo "$(GREEN)✅ Containers reiniciados$(NC)"

status:
	@echo "$(GREEN)Status dos containers:$(NC)"
	$(DOCKER_COMPOSE) ps