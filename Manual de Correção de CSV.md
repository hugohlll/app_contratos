# **Manual de Normalização: Correção de Codificação de CSV para Excel (Windows)**

## **1\. Visão Geral**

Este documento detalha o procedimento para resolver o problema de codificação de caracteres (acentos, cedilhas, etc.) ao abrir os ficheiros .csv exportados pela aplicação no Microsoft Excel (ambiente Windows).

A solução consiste em aplicar rigorosamente o **BOM (Byte Order Mark)** do padrão UTF-8 no exato início do ficheiro. Isto força o Excel a abandonar a leitura regional padrão do Windows (ANSI/Windows-1252) e a adotar a leitura correta em UTF-8 automaticamente.

## **2\. Diagnóstico do Código Atual**

Após análise do código fonte, verificou-se que existem duas abordagens misturadas para a geração de CSV:

1. **Uso de buffer com utf-8-sig**: Encontrado na *view* exportar\_csv (auditoria.py). Esta abordagem **está correta** e é imune a falhas no Excel.  
2. **Escrita direta de string Unicode (response.write('\\ufeff'))**: Encontrada na maioria das *views* (ex: portal.py, militar.py). A utilização da string Unicode em vez do byte puro faz com que a assinatura não seja gravada corretamente no ficheiro físico final em determinadas configurações, causando a quebra da acentuação no Excel.

## **3\. A Solução (Padrão Recomendado)**

Para normalizar o sistema sem alterar a lógica de construção dos dados, iremos substituir o caractere Unicode pelos **bytes literais** correspondentes ao BOM UTF-8 (b'\\xef\\xbb\\xbf').

**O que deve ser feito em todas as Views de exportação afetadas:**

Substituir a linha:

response.write('\\ufeff')  \# Incorreto / Instável

Pela linha:

response.write(b'\\xef\\xbb\\xbf')  \# Correto / Garantido

## **4\. Mapeamento de Ficheiros e Views para Alteração**

Deve realizar a alteração (substituir '\\ufeff' por b'\\xef\\xbb\\xbf') nas seguintes funções dentro do projeto:

### **📄 Ficheiro: contratos/views/auditoria.py**

* \[ \] exportar\_vencimentos\_csv  
* \[ \] exportar\_radar\_permanencia\_csv  
* \[ \] exportar\_sobrecarga\_fiscais\_csv  
* \[ \] exportar\_contratos\_vencimento\_csv

*(Nota: As views exportar\_csv, exportar\_qualificacao\_csv e exportar\_relatorio\_periodo\_csv usam io.StringIO() com .encode('utf-8-sig') e **não precisam de ser alteradas**, pois já se encontram corretas).*

### **📄 Ficheiro: contratos/views/portal.py**

* \[ \] exportar\_empresas\_csv  
* \[ \] exportar\_contratos\_csv  
* \[ \] exportar\_agentes\_csv  
* \[ \] exportar\_comissoes\_csv

### **📄 Ficheiro: contratos/views/militar.py**

* \[ \] exportar\_historico\_militar\_csv

### **📄 Ficheiro: contratos/views/public.py**

* \[ \] exportar\_transparencia\_csv

## **5\. Exemplo Prático de Refatorização**

Veja como deve ficar a estrutura final de uma *view* após a correção. Usaremos a função exportar\_empresas\_csv do ficheiro portal.py como exemplo:

**ANTES (Com falhas no Excel):**

@auditor\_required  
def exportar\_empresas\_csv(request):  
    response \= HttpResponse(content\_type='text/csv; charset=utf-8')  
    filename \= "empresas.csv"  
    encoded\_filename \= urllib.parse.quote(filename)  
    response\['Content-Disposition'\] \= f'attachment; filename="{filename}"; filename\*=UTF-8\\'\\'{encoded\_filename}'  
    response\['Cache-Control'\] \= 'no-cache, no-store, must-revalidate, max-age=0'  
      
    \# ❌ AQUI ESTÁ A ORIGEM DO PROBLEMA  
    response.write('\\ufeff')  \# BOM (formato de string pode falhar)  
      
    writer \= csv.writer(response, delimiter=';')  
    writer.writerow(\['Razão Social', 'CNPJ'\])  
      
    for empresa in Empresa.objects.all():  
        writer.writerow(\[empresa.razao\_social, empresa.cnpj\])  
          
    return response

**DEPOIS (Corrigido para o Excel no Windows):**

@auditor\_required  
def exportar\_empresas\_csv(request):  
    response \= HttpResponse(content\_type='text/csv; charset=utf-8')  
    filename \= "empresas.csv"  
    encoded\_filename \= urllib.parse.quote(filename)  
    response\['Content-Disposition'\] \= f'attachment; filename="{filename}"; filename\*=UTF-8\\'\\'{encoded\_filename}'  
    response\['Cache-Control'\] \= 'no-cache, no-store, must-revalidate, max-age=0'  
      
    \# ✅ CORREÇÃO APLICADA: Gravação explícita dos bytes do BOM UTF-8  
    response.write(b'\\xef\\xbb\\xbf')  
      
    writer \= csv.writer(response, delimiter=';')  
    writer.writerow(\['Razão Social', 'CNPJ'\])  
      
    for empresa in Empresa.objects.all():  
        writer.writerow(\[empresa.razao\_social, empresa.cnpj\])  
          
    return response

## **6\. Procedimento de Teste**

Após realizar as alterações em todos os ficheiros mapeados na Secção 4:

1. Reinicie o servidor web (Gunicorn/Uvicorn ou o runserver local).  
2. Aceda à aplicação e efetue a transferência de um relatório afetado (ex: Lista de Empresas ou Histórico do Militar).  
3. Abra o ficheiro diretamente com um **duplo clique** no Windows (sem utilizar o assistente de importação de dados).  
4. Verifique se nomes como "João", "Ação" ou "Comissão" aparecem corretamente formatados no Excel.