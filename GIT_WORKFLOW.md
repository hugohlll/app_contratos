# Workflow Git - Painel de Auditoria Visual

## 📋 Status Atual

✅ **Branch criada:** `feature/painel-auditoria-visual`  
✅ **Commit realizado:** Todas as mudanças do painel visual estão nesta branch  
✅ **Branch master:** Permanece intacta com a versão original

---

## 🔄 Comandos Úteis

### Verificar em qual branch você está:
```bash
git branch
# O asterisco (*) indica a branch atual
```

### Voltar para a branch master (versão original):
```bash
git checkout master
```

### Voltar para a branch de teste (versão visual):
```bash
git checkout feature/painel-auditoria-visual
```

### Ver diferenças entre as branches:
```bash
# Ver o que mudou na branch de teste em relação ao master
git diff master..feature/painel-auditoria-visual
```

### Ver histórico de commits da branch:
```bash
git log feature/painel-auditoria-visual --oneline
```

---

## 🧪 Processo de Teste

### 1. Testar a versão visual:
```bash
# Certifique-se de estar na branch de teste
git checkout feature/painel-auditoria-visual

# Execute o servidor Django
python manage.py runserver
```

### 2. Testar a versão original (para comparação):
```bash
# Volte para o master
git checkout master

# Execute o servidor Django
python manage.py runserver
```

---

## ✅ Após Aprovação - Merge para Master

### Opção 1: Merge direto (recomendado para manter histórico)
```bash
# Volte para o master
git checkout master

# Faça o merge da branch de teste
git merge feature/painel-auditoria-visual

# Resolva conflitos se houver (improvável neste caso)
# Depois faça push
git push origin master
```

### Opção 2: Merge com squash (combina commits em um único)
```bash
git checkout master
git merge --squash feature/painel-auditoria-visual
git commit -m "feat: aprimora painel de auditoria com gráficos interativos"
git push origin master
```

---

## ❌ Se Decidir Descartar as Mudanças

### Descartar a branch completamente:
```bash
# Volte para o master
git checkout master

# Delete a branch local
git branch -D feature/painel-auditoria-visual

# Se tiver enviado para o remoto, delete também:
git push origin --delete feature/painel-auditoria-visual
```

---

## 📤 Enviar Branch para Repositório Remoto (Opcional)

Se quiser que outros desenvolvedores testem ou fazer backup:

```bash
# Envie a branch para o remoto
git push -u origin feature/painel-auditoria-visual
```

Depois, outros podem testar com:
```bash
git fetch origin
git checkout feature/painel-auditoria-visual
```

---

## 🔍 Ver Arquivos Modificados

```bash
# Ver quais arquivos foram modificados na branch
git diff --name-only master..feature/painel-auditoria-visual
```

**Arquivos modificados:**
- `contratos/templates/contratos/painel_controle.html` (reescrito - 89% mudanças)
- `contratos/views/auditoria.py` (adicionados dados para gráficos)

---

## 💡 Dicas

1. **Sempre teste em ambas as branches** antes de fazer merge
2. **Faça backup** antes de merge: `git tag backup-pre-merge`
3. **Use branches descritivas**: `feature/`, `fix/`, `refactor/`
4. **Commits claros**: Mensagens explicam o "porquê", não apenas o "o quê"

---

## 📊 Resumo do Estado Atual

```
master (original)
  └── ad16bae estrutura inicial

feature/painel-auditoria-visual (nova versão)
  └── 0648d20 feat: aprimora painel de auditoria com gráficos interativos
```
