#!/bin/bash
# ==============================================================================
# SISCONT — Script de Deploy Automatizado em Produção
# ==============================================================================
# Resolve a limitação do Docker Compose v5+ com Bake e "network: host",
# executando o build de forma isolada e aplicando as rotinas de segurança:
# 1. Validação de ambiente e sintaxe (.env.prod)
# 2. Backup preventivo do banco de dados
# 3. Preservação da imagem anterior (tag :previous)
# 4. Build direto com --network host
# 5. Atualização dos containers (up -d)
# 6. Monitoramento de integridade (Health Check com rollback automático)
# 7. Salvaguarda contra modelos sem migração (makemigrations --check --dry-run)
# 8. Aplicação de migrações (migrate)
# 9. Limpeza e recopilação de estáticos (collectstatic --clear)
# ==============================================================================

set -euo pipefail

# Garante execução a partir da raiz do repositório
PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$PROJECT_DIR"

COMPOSE_FILE="docker-compose.prod.yml"
IMAGE_NAME="app_contratos-web:latest"
IMAGE_PREVIOUS="app_contratos-web:previous"
START_TIME=$(date +%s)
TIMESTAMP=$(date +"%Y%m%d_%H%M%S")

mkdir -p logs
LOG_FILE="$PROJECT_DIR/logs/deploy_${TIMESTAMP}.log"

# Cores para terminal
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m'

# Opções padrão
DO_PULL=false
DO_BACKUP=true
USE_MAINTENANCE=false
DO_ROLLBACK=false
DO_PRUNE=false
DRY_RUN=false

log() {
    local msg="[$(date +'%Y-%m-%d %H:%M:%S')] $1"
    echo -e "$1"
    echo -e "$msg" | sed -r "s/\x1B\[([0-9]{1,2}(;[0-9]{1,2})?)?[mGK]//g" >> "$LOG_FILE"
}

info() { log "${BLUE}ℹ️  $1${NC}"; }
success() { log "${GREEN}✅ $1${NC}"; }
warn() { log "${YELLOW}⚠️  $1${NC}"; }
error() { log "${RED}❌ $1${NC}"; }

show_help() {
    cat << EOF
Uso: sudo ./scripts/deploy_prod.sh [OPÇÕES]

Opções disponíveis:
  --pull           Executa 'git pull origin master' antes do deploy.
  --sem-backup     Pula a criação do backup preventivo do banco de dados.
  --manutencao     Ativa página de manutenção no Nginx durante o deploy.
  --prune          Remove imagens Docker antigas/dangling ao final.
  --rollback       Restaura imediatamente a versão anterior (:previous).
  --dry-run        Exibe os passos que seriam executados sem aplicar alterações.
  -h, --help       Exibe esta ajuda.

Exemplos:
  sudo ./scripts/deploy_prod.sh
  sudo ./scripts/deploy_prod.sh --pull
  sudo ./scripts/deploy_prod.sh --pull --manutencao
  sudo ./scripts/deploy_prod.sh --rollback
EOF
}

# Tratamento de parâmetros de linha de comando
while [[ $# -gt 0 ]]; do
    case "$1" in
        --pull) DO_PULL=true; shift ;;
        --sem-backup) DO_BACKUP=false; shift ;;
        --manutencao) USE_MAINTENANCE=true; shift ;;
        --prune) DO_PRUNE=true; shift ;;
        --rollback) DO_ROLLBACK=true; shift ;;
        --dry-run) DRY_RUN=true; shift ;;
        -h|--help) show_help; exit 0 ;;
        *) error "Opção desconhecida: $1"; show_help; exit 1 ;;
    esac
done

# Tratamento de modo de manutenção via trap
cleanup() {
    if [ "$USE_MAINTENANCE" = true ] && [ "$DRY_RUN" = false ]; then
        info "Desativando modo de manutenção..."
        if [ -f "./scripts/maintenance_off.sh" ]; then
            bash ./scripts/maintenance_off.sh || true
        fi
    fi
}
trap cleanup EXIT

# ------------------------------------------------------------------------------
# ROTA DE ROLLBACK EXPLICITA (--rollback)
# ------------------------------------------------------------------------------
if [ "$DO_ROLLBACK" = true ]; then
    info "Iniciando reversão (rollback) para a imagem anterior..."
    if ! docker image inspect "$IMAGE_PREVIOUS" >/dev/null 2>&1; then
        error "Imagem anterior '$IMAGE_PREVIOUS' não foi encontrada! Não é possível reverter."
        exit 1
    fi

    if [ "$DRY_RUN" = true ]; then
        info "[DRY-RUN] docker tag $IMAGE_PREVIOUS $IMAGE_NAME"
        info "[DRY-RUN] docker compose -f $COMPOSE_FILE up -d"
        info "[DRY-RUN] docker compose -f $COMPOSE_FILE exec -T web python manage.py collectstatic --noinput --clear"
        success "Simulação de rollback finalizada."
        exit 0
    fi

    docker tag "$IMAGE_PREVIOUS" "$IMAGE_NAME"
    docker compose -f "$COMPOSE_FILE" up -d
    docker compose -f "$COMPOSE_FILE" exec -T web python manage.py collectstatic --noinput --clear
    success "Rollback concluído com sucesso para $IMAGE_PREVIOUS."
    exit 0
fi

# ------------------------------------------------------------------------------
# 1. PRÉ-VERIFICAÇÕES
# ------------------------------------------------------------------------------
info "Executando pré-verificações do ambiente..."

if ! docker info >/dev/null 2>&1; then
    error "O daemon do Docker não está acessível. Você executou o comando com sudo?"
    exit 1
fi

REQUIRED_FILES=("$COMPOSE_FILE" "Dockerfile.prod" ".env.prod")
for file in "${REQUIRED_FILES[@]}"; do
    if [ ! -f "$file" ]; then
        error "Arquivo obrigatório não encontrado: $file"
        exit 1
    fi
done

SECRETS_FILES=("secrets/credentials.json" "secrets/token.json")
for file in "${SECRETS_FILES[@]}"; do
    if [ ! -e "$file" ]; then
        error "Arquivo/caminho de credenciais não encontrado: $file"
        exit 1
    fi
done

# Verifica se há interpolação acidental de variáveis ($) no .env.prod
COMPOSE_CHECK=$(docker compose -f "$COMPOSE_FILE" config 2>&1 >/dev/null || true)
if echo "$COMPOSE_CHECK" | grep -qi "variable is not set"; then
    error "Detectado aviso crítico de variável não definida no Compose:"
    echo "$COMPOSE_CHECK" | grep -i "variable is not set"
    echo ""
    warn "Possível causa: Senha ou SECRET_KEY com caractere '\$' no .env.prod."
    warn "O Docker Compose interpreta '\$' como variável e apaga esse caractere."
    warn "Corrija o arquivo .env.prod antes de prosseguir com o deploy."
    exit 1
fi

success "Pré-verificações concluídas com sucesso."

# ------------------------------------------------------------------------------
# 2. ATUALIZAÇÃO DO CÓDIGO (GIT PULL)
# ------------------------------------------------------------------------------
if [ "$DO_PULL" = true ]; then
    info "Atualizando código-fonte via git pull..."
    if [ -n "$(git status --porcelain)" ]; then
        error "Existem alterações locais não commitadas no repositório. Abortando deploy."
        git status -s
        exit 1
    fi

    if [ "$DRY_RUN" = true ]; then
        info "[DRY-RUN] git pull origin master"
    else
        if [ -n "${SUDO_USER:-}" ] && [ "$SUDO_USER" != "root" ]; then
            sudo -u "$SUDO_USER" git pull origin master
        else
            git pull origin master
        fi
        success "Código atualizado para o commit: $(git log -1 --oneline)"
    fi
fi

# Ativação opcional da página de manutenção
if [ "$USE_MAINTENANCE" = true ]; then
    info "Ativando página de manutenção no Nginx..."
    if [ "$DRY_RUN" = false ] && [ -f "./scripts/maintenance_on.sh" ]; then
        bash ./scripts/maintenance_on.sh || warn "Não foi possível ativar modo de manutenção (container Nginx rodando?)."
    fi
fi

# ------------------------------------------------------------------------------
# 3. BACKUP PREVENTIVO DO BANCO DE DADOS
# ------------------------------------------------------------------------------
if [ "$DO_BACKUP" = true ]; then
    info "Gerando backup preventivo do banco de dados..."
    if [ "$DRY_RUN" = true ]; then
        info "[DRY-RUN] docker compose -f $COMPOSE_FILE exec -T web python manage.py executar_backup"
    else
        if docker compose -f "$COMPOSE_FILE" ps --status running -q web 2>/dev/null | grep -q .; then
            docker compose -f "$COMPOSE_FILE" exec -T web python manage.py executar_backup || warn "Falha no backup via container web. Prosseguindo com deploy..."
        elif docker compose -f "$COMPOSE_FILE" ps --status running -q cron 2>/dev/null | grep -q .; then
            docker compose -f "$COMPOSE_FILE" exec -T cron python manage.py executar_backup || warn "Falha no backup via container cron. Prosseguindo com deploy..."
        else
            warn "Nenhum container em execução no momento para executar backup pré-deploy. Prosseguindo..."
        fi
    fi
fi

# ------------------------------------------------------------------------------
# 4. SALVAGUARDA DA IMAGEM ATUAL (:previous)
# ------------------------------------------------------------------------------
if docker image inspect "$IMAGE_NAME" >/dev/null 2>&1; then
    info "Marcando imagem atual como '$IMAGE_PREVIOUS' para possibilidade de rollback..."
    if [ "$DRY_RUN" = false ]; then
        docker tag "$IMAGE_NAME" "$IMAGE_PREVIOUS"
    fi
fi

# ------------------------------------------------------------------------------
# 5. CONSTRUÇÃO DA NOVA IMAGEM (DOCKER BUILD COM --NETWORK HOST)
# ------------------------------------------------------------------------------
info "Construindo nova imagem Docker ($IMAGE_NAME) usando rede do host..."
if [ "$DRY_RUN" = true ]; then
    info "[DRY-RUN] docker build --network host -f Dockerfile.prod -t $IMAGE_NAME ."
else
    docker build --network host -f Dockerfile.prod -t "$IMAGE_NAME" .
    success "Imagem $IMAGE_NAME construída com sucesso."
fi

# ------------------------------------------------------------------------------
# 6. ATUALIZAÇÃO DOS CONTAINERS (UP -D)
# ------------------------------------------------------------------------------
info "Iniciando/atualizando containers de produção..."
if [ "$DRY_RUN" = true ]; then
    info "[DRY-RUN] docker compose -f $COMPOSE_FILE up -d --remove-orphans"
else
    docker compose -f "$COMPOSE_FILE" up -d --remove-orphans
fi

# ------------------------------------------------------------------------------
# 7. MONITORAMENTO DE INTEGRIDADE (HEALTH CHECK)
# ------------------------------------------------------------------------------
if [ "$DRY_RUN" = false ]; then
    info "Aguardando inicialização do container web..."
    WEB_CONTAINER_ID=$(docker compose -f "$COMPOSE_FILE" ps -q web)

    HEALTHY=false
    MAX_ATTEMPTS=36  # 36 x 5s = 180s
    ATTEMPT=0

    while [ $ATTEMPT -lt $MAX_ATTEMPTS ]; do
        STATUS=$(docker inspect --format '{{if .State.Health}}{{.State.Health.Status}}{{else}}{{.State.Status}}{{end}}' "$WEB_CONTAINER_ID" 2>/dev/null || echo "unknown")
        
        if [ "$STATUS" = "healthy" ]; then
            HEALTHY=true
            break
        elif [ "$STATUS" = "unhealthy" ]; then
            break
        fi

        sleep 5
        ATTEMPT=$((ATTEMPT + 1))
        echo -n "."
    done
    echo ""

    if [ "$HEALTHY" != true ]; then
        error "Container web não alcançou status saudável (Status: $STATUS)!"
        warn "Exibindo os últimos 50 logs do container web:"
        docker compose -f "$COMPOSE_FILE" logs --tail=50 web

        if docker image inspect "$IMAGE_PREVIOUS" >/dev/null 2>&1; then
            error "Iniciando ROLLBACK AUTOMÁTICO para $IMAGE_PREVIOUS..."
            docker tag "$IMAGE_PREVIOUS" "$IMAGE_NAME"
            docker compose -f "$COMPOSE_FILE" up -d
            warn "Rollback aplicado. O sistema retornou à versão estável anterior."
        fi
        exit 1
    fi
    success "Container web está saudável e respondendo às requisições."
fi

# ------------------------------------------------------------------------------
# 8. SALVAGUARDA DE MIGRAÇÕES (MAKEMIGRATIONS --CHECK --DRY-RUN)
# ------------------------------------------------------------------------------
info "Validando integridade das migrações do Django..."
if [ "$DRY_RUN" = true ]; then
    info "[DRY-RUN] docker compose -f $COMPOSE_FILE exec -T web python manage.py makemigrations --check --dry-run"
else
    if ! docker compose -f "$COMPOSE_FILE" exec -T web python manage.py makemigrations --check --dry-run >/dev/null 2>&1; then
        error "=========================================================================="
        error "ERRO DE MIGRAÇÃO: Existem alterações nos models sem migração gerada no Git!"
        error "=========================================================================="
        warn "Você alterou models.py sem executar 'makemigrations' no ambiente de dev."
        warn "Em produção, migrações NÃO são criadas automaticamente para evitar corrupção."
        warn "Ação necessária:"
        warn "  1. No ambiente local/dev, execute: python manage.py makemigrations"
        warn "  2. Faça commit do novo arquivo de migração gerado e envie ao repositório."
        warn "  3. Execute este deploy novamente."
        
        if docker image inspect "$IMAGE_PREVIOUS" >/dev/null 2>&1; then
            error "Revertendo deploy para a imagem estável anterior..."
            docker tag "$IMAGE_PREVIOUS" "$IMAGE_NAME"
            docker compose -f "$COMPOSE_FILE" up -d
        fi
        exit 1
    fi
    success "Nenhuma discrepância encontrada entre modelos e migrações."
fi

# ------------------------------------------------------------------------------
# 9. APLICAÇÃO DE MIGRAÇÕES PENDENTES
# ------------------------------------------------------------------------------
info "Aplicando migrações pendentes no banco de dados..."
if [ "$DRY_RUN" = true ]; then
    info "[DRY-RUN] docker compose -f $COMPOSE_FILE exec -T web python manage.py migrate --noinput"
else
    docker compose -f "$COMPOSE_FILE" exec -T web python manage.py migrate --noinput
    success "Migrações aplicadas com sucesso."
fi

# ------------------------------------------------------------------------------
# 10. ATUALIZAÇÃO DOS ARQUIVOS ESTÁTICOS
# ------------------------------------------------------------------------------
info "Atualizando arquivos estáticos no volume persistente..."
if [ "$DRY_RUN" = true ]; then
    info "[DRY-RUN] docker compose -f $COMPOSE_FILE exec -T web python manage.py collectstatic --noinput --clear"
else
    docker compose -f "$COMPOSE_FILE" exec -T web python manage.py collectstatic --noinput --clear
    success "Arquivos estáticos atualizados."
fi

# ------------------------------------------------------------------------------
# 11. LIMPEZA OPCIONAL (PRUNE)
# ------------------------------------------------------------------------------
if [ "$DO_PRUNE" = true ]; then
    info "Limpando imagens antigas e sem uso..."
    if [ "$DRY_RUN" = true ]; then
        info "[DRY-RUN] docker image prune -f"
    else
        docker image prune -f
    fi
fi

# ------------------------------------------------------------------------------
# RESUMO FINAL
# ------------------------------------------------------------------------------
ELAPSED_TIME=$(( $(date +%s) - START_TIME ))

echo ""
success "=========================================================================="
success "DEPLOY FINALIZADO COM SUCESSO EM ${ELAPSED_TIME}s!"
success "=========================================================================="
info "Status atual dos containers:"
docker compose -f "$COMPOSE_FILE" ps
echo ""
info "Versão ativa (último commit): $(git log -1 --oneline 2>/dev/null || echo 'N/A')"
info "Log completo salvo em: $LOG_FILE"
