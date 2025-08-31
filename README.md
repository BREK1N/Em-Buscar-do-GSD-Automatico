# Sistema de Gestão Disciplinar (Ouvidoria Inteligente)

## 1\. Introdução

O **Sistema de Gestão Disciplinar** é uma aplicação web robusta, desenvolvida com Django, projetada para otimizar e automatizar processos administrativos disciplinares em contexto militar. A funcionalidade central do sistema é a capacidade de analisar documentos PDF de transgressões, utilizando Inteligência Artificial (com LangChain e a API da OpenAI), para extrair informações cruciais e criar automaticamente um **Processo Administrativo Disciplinar (PATD)**.

Além da análise inteligente, a plataforma oferece um sistema completo para a gestão do efetivo de militares, o controlo detalhado do ciclo de vida dos PATDs, a geração automática de documentos oficiais e um sistema de notificações para prazos expirados, tudo através de uma interface moderna, responsiva e com temas claro e escuro.

## 2\. Funcionalidades Principais

  - **Analisador de PDF com IA**: Carregue um documento de transgressão em PDF e a IA extrairá automaticamente o nome do militar, a descrição da transgressão, o local e a data do ocorrido.
  - **Criação Automática de PATD**: Com base na análise do PDF, o sistema cria uma nova PATD, associando-a ao militar correspondente e verificando a existência de processos similares para evitar duplicidade.
  - **Cadastro Inteligente**: Se o militar mencionado no PDF não estiver na base de dados, a interface facilita o seu registo, pré-preenchendo os dados obtidos pela IA.
  - **Gestão de Efetivo (CRUD)**: Interface completa para Adicionar, Visualizar, Editar e Excluir militares, com pesquisa dinâmica e paginação.
  - **Importação via Excel**: Importe em massa o cadastro de militares a partir de uma planilha Excel, agilizando a configuração inicial do sistema.
  - **Gestão de PATDs e Fluxo de Trabalho Avançado**:
      - Visualização e edição detalhada de cada processo.
      - Registo de até duas testemunhas por PATD.
      - Recolha digital da assinatura de ciência do militar acusado.
      - Controlo de prazo para a apresentação da alegação de defesa, com notificações visuais.
      - Opções para estender o prazo ou registar a preclusão (prosseguir sem defesa).
  - **Geração de Documentos**: Criação automática dos documentos do processo (PATD, Alegação de Defesa, Termo de Preclusão) em formato HTML, preenchidos dinamicamente com os dados do sistema a partir de templates `.docx`.
  - **Gestão de Assinaturas**: Interface dedicada para adicionar e gerir as assinaturas digitalizadas dos oficiais, que são usadas automaticamente nos documentos gerados.
  - **Sistema de Notificações**: Alertas em tempo real na interface sobre PATDs com prazo de defesa expirado, permitindo ações rápidas como estender o prazo ou prosseguir com o processo.
  - **Configurações Gerais**: Painel para definir parâmetros do sistema, como o Comandante do GSD padrão e os prazos para a defesa.

## 3\. Tecnologias Utilizadas

  - **Backend**: Python, Django
  - **Inteligência Artificial**: LangChain, OpenAI API
  - **Base de Dados**: SQLite (padrão do Django)
  - **Frontend**: HTML, CSS, JavaScript
  - **Bibliotecas Python Principais**:
      - `django`
      - `langchain-openai`
      - `langchain-community`
      - `pypdf`
      - `python-dotenv`
      - `pydantic`
      - `pandas` & `openpyxl` (para importação de Excel)
      - `python-docx` (para leitura de templates de documentos)

## 4\. Pré-requisitos

Antes de começar, garanta que tem os seguintes softwares instalados na sua máquina:

  - Python (versão 3.9 ou superior)
  - pip (geralmente vem com o Python)
  - Git

## 5\. Guia de Instalação

Siga os passos abaixo para configurar o ambiente de desenvolvimento local.

### 1\. Clonar o Repositório

```bash
git clone <URL_DO_SEU_REPOSITORIO>
cd <NOME_DA_PASTA_DO_PROJETO>
```

### 2\. Criar e Ativar um Ambiente Virtual

É uma boa prática usar um ambiente virtual para isolar as dependências do projeto.
**Para Windows:**

```bash
python -m venv venv
venv\Scripts\activate
```

**Para macOS/Linux:**

```bash
python3 -m venv venv
source venv/bin/activate
```

### 3\. Instalar as Dependências

Instale todas as bibliotecas necessárias listadas no ficheiro `requirements.txt`.

```bash
pip install -r requirements.txt
```

### 4\. Configurar Variáveis de Ambiente

A integração com a OpenAI requer uma chave de API.

  - Crie um ficheiro chamado `.env` na raiz do projeto (na mesma pasta que `manage.py`).
  - Dentro do ficheiro `.env`, adicione a sua chave da API:

<!-- end list -->

```
OPENAI_API_KEY='sua_chave_secreta_da_openai_aqui'
```

### 5\. Aplicar as Migrações da Base de Dados

Estes comandos irão criar as tabelas (Militar, PATD, etc.) na sua base de dados SQLite.

```bash
python manage.py makemigrations Ouvidoria
python manage.py migrate
```

### 6\. Criar um Superutilizador

Para aceder à área de administração do Django (`/admin`), precisa de um utilizador com privilégios.

```bash
python manage.py createsuperuser
```

Siga as instruções para criar o seu nome de utilizador e palavra-passe.

## 6\. Como Executar o Projeto

Com tudo configurado, inicie o servidor de desenvolvimento do Django:

```bash
python manage.py runserver
```

A aplicação estará disponível no seu navegador nos seguintes endereços:

  - **Página Principal (Analisador)**: `http://127.0.0.1:8000/Ouvidoria/`
  - **Área de Administração**: `http://127.0.0.1:8000/admin/` (use as credenciais do superutilizador)

## 7\. Estrutura do Projeto

```
.
├── GsdAutomatico/         # Pasta principal do projeto Django
│   ├── settings.py        # Configurações do projeto
│   └── urls.py            # URLs principais
├── Ouvidoria/             # Aplicação principal "Ouvidoria"
│   ├── models.py          # Definição das tabelas da base de dados
│   ├── views.py           # Lógica de negócio (controllers)
│   ├── urls.py            # URLs específicas da aplicação
│   ├── forms.py           # Formulários Django
│   ├── admin.py           # Configuração da interface de admin
│   └── templates/         # Ficheiros HTML
├── static/                # Ficheiros estáticos (CSS, JS, Imagens)
├── pdf/                   # Templates de documentos (.docx)
├── manage.py              # Utilitário de linha de comando do Django
├── requirements.txt       # Lista de dependências Python
└── .env                   # Ficheiro para variáveis de ambiente (API keys, etc.)
```

## 8\. Licença

Este projeto está licenciado sob a Licença MIT. Consulte o ficheiro `LICENSE` para mais detalhes.
