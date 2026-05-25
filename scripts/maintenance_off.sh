#!/bin/bash
# =============================================================
# SISCONT — Desativar Modo de Manutenção
# =============================================================
# Remove o ficheiro-flag do container Nginx.
# O Nginx detecta automaticamente a ausência do ficheiro
# e volta a encaminhar requisições para o Django normalmente.
# Não requer restart do Nginx.
# =============================================================

CONTAINER="siscont_prod-nginx-1"
FLAG_FILE="/usr/share/nginx/html/maintenance.on"

# Verifica se o container está em execução
if ! docker inspect -f '{{.State.Running}}' "$CONTAINER" 2>/dev/null | grep -q "true"; then
    echo "❌ Erro: container '$CONTAINER' não está em execução."
    exit 1
fi

docker exec "$CONTAINER" rm -f "$FLAG_FILE"

echo "✅ Modo de manutenção DESATIVADO."
echo "   O sistema voltou ao funcionamento normal."
