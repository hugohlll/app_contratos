# **Guia de Isolamento Docker: Produção vs Desenvolvimento no Mesmo Servidor**

Este guia estabelece as regras e práticas rigorosas para garantir que as bases de dados de Produção e Desenvolvimento, hospedadas no mesmo servidor Linux (Ubuntu), nunca colidam. O objetivo é eliminar o risco de o ambiente de desenvolvimento ler ou modificar os dados reais de produção.

## **1\. Isolamento de Rede (Network Isolation)**

Por padrão, o Docker Compose pode conectar contentores de diferentes diretórios se compartilharem os mesmos nomes de rede padrão. Para evitar isso de forma automática e segura, o Docker Compose V2 utiliza o isolamento por namespaces de projeto, gerando redes exclusivas para cada ambiente.

### **Configuração:**

Cada ambiente possui seu próprio nome de projeto declarado na primeira linha de cada arquivo Docker Compose.
**No docker-compose.prod.yml:**
```yaml
name: siscont_prod
```

**No docker-compose.yml:**
```yaml
name: siscont_dev
```

*Porque funciona:* Ao definir o nome do projeto no topo do arquivo, o Docker Compose cria automaticamente redes padrão isoladas para cada um: `siscont_prod_default` e `siscont_dev_default`. O DNS interno de uma rede não consegue resolver ou acessar contêineres instalados na outra rede, impossibilitando que a aplicação de desenvolvimento se comunique com o banco de dados de produção.

## **2\. Separação Estrita de Nomes de Projetos**

O Docker Compose agrupa recursos pelo nome do projeto ("Project Name"). Se dois ambientes compartilhassem o mesmo nome (como o nome do diretório padrão `app_contratos`), comandos como `down` ou `up` executados em desenvolvimento poderiam interromper ou destruir contêineres de produção.

### **Configuração:**

Em vez de depender de arquivos `.env` com a variável `COMPOSE_PROJECT_NAME`, o Docker Compose V2 simplifica o gerenciamento definindo o nome diretamente no arquivo de configuração (conforme visto na Seção 1):
- Produção: `name: siscont_prod` (no `docker-compose.prod.yml`)
- Desenvolvimento: `name: siscont_dev` (no `docker-compose.yml`)

*Porque funciona:* Os contêineres passam a ser gerados com namespaces específicos (ex: `siscont_prod-db-1` e `siscont_dev-db-1`), eliminando qualquer risco de colisão de nomes de contêineres ou conflitos em seu ciclo de vida.

## **3\. Isolamento Físico de Volumes**

Os volumes Docker são onde os dados do PostgreSQL residem fisicamente no servidor hospedeiro. Se ambos os ambientes apontassem para o mesmo volume genérico (como `postgres_data`), a base de desenvolvimento compartilharia o mesmo espaço físico de produção, causando corrupção ou perda de dados reais.

### **Configuração:**

Nomeie explicitamente os volumes declarados no bloco final de cada arquivo para garantir caminhos físicos totalmente independentes.

**No docker-compose.prod.yml:**
```yaml
volumes:
  postgres_data:
    name: siscont_pg_data_prod
  static_volume:
    name: siscont_static_prod
  media_volume:
    name: siscont_media_prod
```

**No docker-compose.yml:**
```yaml
volumes:
  postgres_data:
    name: siscont_pg_data_dev
```

*Importante:* O serviço `db` mapeia o volume interno do contêiner para o volume nomeado isolado (ex: `postgres_data:/var/lib/postgresql/data`). O Docker cria diretórios de persistência separados em `/var/lib/docker/volumes/` (`siscont_pg_data_prod/_data` e `siscont_pg_data_dev/_data`).

## **4\. Remoção de Portas Expostas (Host Binding)**

Um erro comum em infraestrutura é expor a porta padrão do banco de dados (5432) do contêiner de produção para a máquina hospedeira. Isso permitiria que conexões externas acidentais (ou scripts de teste rodando no localhost) afetassem a produção.

### **Configuração:**

**Em Produção (docker-compose.prod.yml):**
Remova completamente o mapeamento de portas do serviço do banco de dados `db`. A comunicação entre a aplicação Django (`web`) e o banco de dados é feita de forma estritamente interna pela rede isolada `siscont_prod_default`.

```yaml
services:
  db:
    image: postgres:15
    # Sem mapeamento de portas (ports:)
```

**Em Desenvolvimento (docker-compose.yml):**
Se for necessário conectar ferramentas visuais de administração (como DBeaver) ao banco de desenvolvimento local, mapeie-o para uma porta externa alternativa, mantendo a porta padrão 5432 do host livre:

```yaml
services:
  db:
    image: postgres:15
    # Porta 5433 no host aponta para a 5432 interna do container de dev
    # Evitando conflito caso o host já tenha outro PostgreSQL rodando
```

## **5\. Diferenciação de Credenciais e Bases de Dados**

Como última linha de defesa, as credenciais e o nome dos bancos de dados são totalmente distintos em cada ambiente.

### **Configuração:**

**Em Desenvolvimento (docker-compose.yml):**
As credenciais de desenvolvimento são definidas de maneira explícita e direta no arquivo YAML:
- `POSTGRES_DB=gestao_contratos_db`
- `POSTGRES_USER=admin_contratos`
- `POSTGRES_PASSWORD=senha_segura_militar`

**Em Produção (docker-compose.prod.yml):**
As credenciais de produção são salvas e lidas a partir do arquivo confidencial `.env.prod`, que não é versionado no repositório:
- `POSTGRES_DB=siscont_db`
- `POSTGRES_USER=admin_siscont`
- `POSTGRES_PASSWORD=S1sc0nt_Pr0d_2026!` (Senha forte e única)

*Porque funciona:* Caso ocorra alguma falha de rede e a aplicação de desenvolvimento tente conectar no host de banco de produção, a conexão será rejeitada pelo PostgreSQL de produção devido a nomes de banco e credenciais de login completamente incompatíveis.

---

## **Resumo das Camadas de Defesa (Defesa em Profundidade):**

1. **Camada de Rede:** Desenvolvimento e Produção estão em redes separadas (`siscont_dev_default` e `siscont_prod_default`).
2. **Camada de Sistema Operacional:** O Docker gerencia contêineres sob namespaces distintos (`siscont_dev` e `siscont_prod`).
3. **Camada de Disco:** Dados residem em volumes físicos diferentes (`siscont_pg_data_dev` e `siscont_pg_data_prod`).
4. **Camada de Acesso Local:** A porta do banco de produção não é exposta para o host hospedeiro.
5. **Camada Lógica (Autenticação):** Cada ambiente utiliza usuários, senhas e nomes de base de dados diferentes.