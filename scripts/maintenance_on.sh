#!/bin/bash
# =============================================================
# SISCONT — Ativar Modo de Manutenção
# =============================================================
# Cria o ficheiro-flag dentro do container Nginx.
# O Nginx detecta automaticamente o ficheiro a cada requisição
# e retorna 503 com a página de manutenção.
# Não requer restart do Nginx.
# =============================================================

CONTAINER="siscont_prod-nginx-1"
FLAG_FILE="/usr/share/nginx/html/maintenance.on"

# Verifica se o container está em execução
if ! docker inspect -f '{{.State.Running}}' "$CONTAINER" 2>/dev/null | grep -q "true"; then
    echo "❌ Erro: container '$CONTAINER' não está em execução."
    exit 1
fi

docker exec "$CONTAINER" touch "$FLAG_FILE"

echo "✅ Modo de manutenção ATIVADO."
echo "   Todos os acessos receberão a página de manutenção (HTTP 503)."
