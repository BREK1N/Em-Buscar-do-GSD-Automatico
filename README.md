# GSD Automático

**GSD Automático** é um sistema web desenvolvido em Django para auxiliar na gestão administrativa e disciplinar de Organizações Militares. O projeto visa automatizar processos burocráticos, gerenciar efetivo, controlar solicitações de ouvidoria e gerar documentação oficial (NPD, Relatórios, etc.) de forma padronizada.

## 📋 Funcionalidades Principais

O sistema é dividido em módulos para melhor organização:

### 1. Seção de Pessoal (`Secao_pessoal`)
* **Gestão de Efetivo:** Cadastro e controle de militares.
* **Controle de Dados:** Gerenciamento de Nome de Guerra, Posto/Graduação, Setor e SARAM.
* **Importação de Dados:** Funcionalidade para importar efetivo em massa via planilhas Excel.

### 2. Ouvidoria e Justiça (`Ouvidoria`)
* **Gestão de PATD:** Controle completo de Processos Administrativos de Transgressão Disciplinar.
* **Fluxo de Processo:** Acompanhamento desde a notificação, alegação de defesa, até a solução/punição ou justificativa.
* **Geração de Documentos:** Criação automática de arquivos `.docx` e `.pdf` baseados em modelos (NPD, Reconsideração, Relatórios).
* **Dashboard do Comandante:** Visão geral para tomada de decisão.

### 3. Informática (`informatica`)
* Gestão de usuários e permissões de acesso ao sistema.
* Configurações gerais do sistema.

### 4. Autenticação (`login`)
* Sistema de login seguro e personalizado.
* Gestão de perfis de usuário.

---

## 🚀 Tecnologias Utilizadas

* **Linguagem:** Python 3.x
* **Framework Web:** Django
* **Banco de Dados:** PostgreSQL (Configurado via Docker)
* **Infraestrutura:** Docker & Docker Compose
* **Servidor Web:** Nginx (Proxy Reverso) & Gunicorn
* **Frontend:** HTML5, CSS3, JavaScript (Bootstrap e jQuery na área administrativa)
* **Manipulação de Arquivos:** `python-docx` (Word) e `reportlab` (PDF)

---

## 🔧 Pré-requisitos

Para rodar este projeto, você precisará ter instalado em sua máquina:

* [Docker](https://www.docker.com/get-started)
* [Docker Compose](https://docs.docker.com/compose/install/)
* [Git](https://git-scm.com/)

---

## 🐳 Como rodar com Docker (Recomendado)

Esta é a maneira mais fácil de iniciar o projeto, pois configura o banco de dados, o servidor web e a aplicação automaticamente.

1.  **Clone o repositório:**
    ```bash
    git clone [https://github.com/brek1n/em-buscar-do-gsd-automatico.git](https://github.com/brek1n/em-buscar-do-gsd-automatico.git)
    cd em-buscar-do-gsd-automatico
    ```

2.  **Construa e inicie os containers:**
    ```bash
    docker-compose up --build
    ```
    *O processo pode levar alguns minutos na primeira vez enquanto baixa as imagens e instala as dependências.*

3.  **Acesse o sistema:**
    Abra o seu navegador e acesse: `http://localhost:8000` (ou a porta configurada no seu `docker-compose.yml`/`nginx`).

4.  **Criar um Superusuário (Admin):**
    Com o container rodando, abra um novo terminal e execute:
    ```bash
    docker-compose exec web python manage.py createsuperuser
    ```
    Siga as instruções para definir usuário e senha.

---

## 🛠️ Instalação Manual (Desenvolvimento Local sem Docker)

Caso prefira rodar sem Docker, siga os passos abaixo:

1.  **Crie e ative um ambiente virtual:**
    ```bash
    python -m venv venv
    # No Windows:
    venv\Scripts\activate
    # No Linux/Mac:
    source venv/bin/activate
    ```

2.  **Instale as dependências:**
    ```bash
    pip install -r requirements.txt
    ```

3.  **Configure o Banco de Dados:**
    Verifique o arquivo `settings.py`. Se estiver configurado para PostgreSQL, você precisará ter um banco rodando localmente e ajustar as credenciais. Para testes rápidos, você pode alterar para SQLite.

4.  **Execute as migrações:**
    ```bash
    python manage.py makemigrations
    python manage.py migrate
    ```

5.  **Colete os arquivos estáticos:**
    ```bash
    python manage.py collectstatic
    ```

6.  **Inicie o servidor de desenvolvimento:**
    ```bash
    python manage.py runserver
    ```

---

## 📂 Estrutura de Arquivos

```text
Em-Buscar-do-GSD-Automatico/
├── Dockerfile              # Configuração da imagem Docker da aplicação
├── docker-compose.yml      # Orquestração dos serviços (App, DB, Nginx)
├── entrypoint.sh           # Script de inicialização do container
├── requirements.txt        # Dependências do Python
├── nginx/                  # Configurações do servidor Nginx
└── GsdAutomatico/          # Pasta raiz do projeto Django
    ├── manage.py
    ├── GsdAutomatico/      # Configurações principais (settings, urls)
    ├── Ouvidoria/          # App de Justiça e Disciplina
    ├── Secao_pessoal/      # App de Gestão de Efetivo
    ├── informatica/        # App de Suporte/Configuração
    ├── login/              # App de Autenticação
    ├── pdf/                # Modelos de documentos (.docx, .pdf)
    ├── Static/             # Arquivos estáticos (CSS, JS, Imagens) do projeto
    └── staticfiles/        # Arquivos estáticos coletados (para produção)