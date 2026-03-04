---
description: como corrigir tags Django quebradas em templates HTML
---

## Identificar o Problema

Tags Django quebradas acontecem quando um `{{ ` fica no final de uma linha e a variável segue na próxima. O resultado é que o valor aparece como texto literal na página (ex: `{{ contrato.numero }}`).

**Padrão do bug:**
```html
<!-- QUEBRADO (não funciona) -->
<h5>{{ 
    contrato.numero }}</h5>

<!-- CORRETO -->
<h5>{{ contrato.numero }}</h5>
```

---

## Diagnóstico

**1. Confirmar quais arquivos têm o problema:**
```bash
python3 -c "
import glob
templates_dir = 'contratos/templates'
for fpath in glob.glob(templates_dir + '/**/*.html', recursive=True):
    with open(fpath) as f:
        lines = f.readlines()
    for i, line in enumerate(lines):
        if line.rstrip().endswith('{{'):
            print(f'{fpath}:{i+1}: {line.strip()[:80]}')
"
```

Se a saída for vazia: **nenhum arquivo tem o problema**. Se listar arquivos e linhas: anote-os.

---

## Correção

**2. Executar o script de correção automática:**

```bash
python3 -c "
import glob, re
templates_dir = 'contratos/templates'
for fpath in glob.glob(templates_dir + '/**/*.html', recursive=True):
    with open(fpath) as f:
        content = f.read()
    fixed = re.sub(r'\{\{\s+(\S+)\s*\n\s*\}\}', r'{{ \1 }}', content)
    if fixed != content:
        with open(fpath, 'w') as f:
            f.write(fixed)
        print(f'Corrigido: {fpath}')
"
```

> **Limitação:** Este regex corrige quebras simples (variável direto, sem filtros). Para casos mais complexos, edite o arquivo manualmente — veja abaixo.

**3. Correção manual (para casos não capturados pelo regex):**

Abra o arquivo apontado pelo diagnóstico e junte as linhas manualmente:
```html
<!-- Antes -->
<div>{{ comissao.get_tipo_display
    }}</div>

<!-- Depois -->
<div>{{ comissao.get_tipo_display }}</div>
```

---

## Correção via Script Externo (Método mais Confiável)

Quando o arquivo tem múltiplos casos mistos, escreva um script Python em `/tmp/` e execute-o:

```bash
# 1. Crie /tmp/fix_template.py com o conteúdo correto do template
# 2. Execute:
python3 /tmp/fix_template.py
```

Exemplo de script:
```python
filepath = 'contratos/templates/contratos/nome_do_template.html'

new_content = '''... conteúdo completo do template corrigido ...'''

with open(filepath, 'w', encoding='utf-8') as f:
    f.write(new_content)
print("OK")
```

> **Por que este método?** Ferramentas de edição integradas (IDE) às vezes falham ao salvar arquivos de template abertos simultaneamente. O script Python via terminal é o método que comprovadamente funciona.

---

## Validação

**4. Confirmar que não há mais tags quebradas:**
```bash
python3 -c "
import glob
templates_dir = 'contratos/templates'
found = False
for fpath in glob.glob(templates_dir + '/**/*.html', recursive=True):
    with open(fpath) as f:
        lines = f.readlines()
    for i, line in enumerate(lines):
        if line.rstrip().endswith('{{'):
            print(f'{fpath}:{i+1}: {line.strip()[:80]}')
            found = True
if not found:
    print('Tudo certo: zero tags quebradas.')
"
```

---

## Testar em Produção Local

**5. Rebuild e teste:**
```bash
docker compose -f docker-compose.prod.yml up -d --build
```

Abra o navegador em **http://localhost** e verifique se os dados estão sendo exibidos corretamente (valores reais, não `{{ variável }}`).

---

## Causa Raiz e Como Evitar

O problema ocorre quando o editor de código formata automaticamente o HTML quebrando linhas longas. 

**Para evitar:**
- Configure o formatador do VS Code para não quebrar linhas dentro de `{{ }}`. Adicione ao `.vscode/settings.json`:
```json
{
    "editor.wordWrap": "off",
    "html.format.wrapAttributesIndentSize": 0
}
```
- Ao escrever templates, **nunca** deixe `{{` como último caractere de uma linha.
