#!/bin/bash
# =============================================================
# Teste de Isolamento: populate_db NÃO deve existir em produção
# =============================================================

echo "============================================="
echo " TESTE DE ISOLAMENTO - populate_db"
echo "============================================="
echo ""

# --- TESTE 1: Verificar se populate_db.py existe na imagem de PRODUÇÃO ---
echo "[TESTE 1] Verificando se populate_db.py existe na imagem de PRODUÇÃO..."

docker build -f Dockerfile.prod --network=host -t siscont_prod_test --quiet . > /dev/null 2>&1

if docker run --rm siscont_prod_test ls /app/contratos/management/commands/populate_db.py > /dev/null 2>&1; then
    echo "  ❌ FALHOU: populate_db.py EXISTE na imagem de produção!"
    TESTE1="FALHOU"
else
    echo "  ✅ PASSOU: populate_db.py NÃO existe na imagem de produção."
    TESTE1="PASSOU"
fi

echo ""

# --- TESTE 2: Verificar se o comando populate_db é rejeitado em produção ---
echo "[TESTE 2] Tentando executar 'manage.py populate_db' na imagem de PRODUÇÃO..."

OUTPUT=$(docker run --rm siscont_prod_test python manage.py populate_db 2>&1)
EXIT_CODE=$?

if [ $EXIT_CODE -ne 0 ]; then
    echo "  ✅ PASSOU: Comando rejeitado com código de saída $EXIT_CODE."
    echo "  Mensagem: $(echo $OUTPUT | head -c 120)"
    TESTE2="PASSOU"
else
    echo "  ❌ FALHOU: Comando foi aceito na imagem de produção!"
    TESTE2="FALHOU"
fi

echo ""

# --- TESTE 3: Verificar se populate_db.py existe na imagem de DESENVOLVIMENTO ---
echo "[TESTE 3] Verificando se populate_db.py existe na imagem de DESENVOLVIMENTO..."

docker build -f Dockerfile --network=host -t siscont_dev_test --quiet . > /dev/null 2>&1

if docker run --rm siscont_dev_test ls /app/contratos/management/commands/populate_db.py > /dev/null 2>&1; then
    echo "  ✅ PASSOU: populate_db.py existe na imagem de desenvolvimento."
    TESTE3="PASSOU"
else
    echo "  ❌ FALHOU: populate_db.py NÃO existe na imagem de desenvolvimento!"
    TESTE3="FALHOU"
fi

echo ""

# --- RESUMO ---
echo "============================================="
echo " RESUMO DOS TESTES"
echo "============================================="
echo "  Teste 1 (Arquivo ausente em prod):    $TESTE1"
echo "  Teste 2 (Comando rejeitado em prod):  $TESTE2"
echo "  Teste 3 (Arquivo presente em dev):    $TESTE3"
echo "============================================="

# Limpeza das imagens de teste
docker rmi siscont_prod_test siscont_dev_test > /dev/null 2>&1

if [ "$TESTE1" = "PASSOU" ] && [ "$TESTE2" = "PASSOU" ] && [ "$TESTE3" = "PASSOU" ]; then
    echo "🟢 TODOS OS TESTES PASSARAM. O isolamento está funcionando."
    exit 0
else
    echo "🔴 ALGUM TESTE FALHOU. Revise as configurações."
    exit 1
fi
