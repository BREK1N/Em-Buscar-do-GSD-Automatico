<!DOCTYPE html>
<html lang="pt-br">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Sistema de Gestão Disciplinar (Ouvidoria Inteligente)</title>
    <style>
        body {
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
            line-height: 1.6;
            color: #333;
            max-width: 800px;
            margin: 0 auto;
            padding: 20px;
            background-color: #f9f9f9;
        }
        h1, h2, h3 {
            border-bottom: 1px solid #ddd;
            padding-bottom: 10px;
            margin-top: 24px;
            color: #24292e;
        }
        h1 {
            font-size: 2em;
        }
        h2 {
            font-size: 1.5em;
        }
        ul {
            padding-left: 20px;
        }
        li {
            margin-bottom: 10px;
        }
        code {
            font-family: "SFMono-Regular", Consolas, "Liberation Mono", Menlo, Courier, monospace;
            background-color: #f0f0f0;
            padding: 2px 5px;
            border-radius: 4px;
            font-size: 0.9em;
        }
        pre {
            background-color: #2d2d2d;
            color: #f1f1f1;
            padding: 15px;
            border-radius: 5px;
            overflow-x: auto;
        }
        pre code {
            background-color: transparent;
            padding: 0;
        }
        strong {
            color: #1a1a1a;
        }
        .cite {
            font-size: 0.8em;
            color: #666;
        }
    </style>
</head>
<body>

    <h1>Sistema de Gestão Disciplinar (Ouvidoria Inteligente)</h1>

    <h2>1. Introdução</h2>
    <p>O <strong>Sistema de Gestão Disciplinar</strong> é uma aplicação web robusta, desenvolvida com Django, projetada para otimizar e automatizar processos administrativos disciplinares em contexto militar. A funcionalidade central do sistema é a capacidade de analisar documentos PDF de transgressões, utilizando Inteligência Artificial (com LangChain e a API da OpenAI), para extrair informações cruciais e criar automaticamente um <strong>Processo Administrativo Disciplinar (PATD)</strong>.</p>
    <p>Além da análise inteligente, a plataforma oferece um sistema completo para a gestão do efetivo de militares, o controlo detalhado do ciclo de vida dos PATDs, a geração automática de documentos oficiais e um sistema de notificações para prazos expirados, tudo através de uma interface moderna, responsiva e com temas claro e escuro.</p>

    <h2>2. Funcionalidades Principais</h2>
    <ul>
        <li><strong>Analisador de PDF com IA</strong>: Carregue um documento de transgressão em PDF e a IA extrairá automaticamente o nome do militar, a descrição da transgressão, o local e a data do ocorrido <span class="cite">[cite: brek1n/em-buscar-do-gsd-automatico/Em-Buscar-do-GSD-Automatico-6b722cb465ccf0703f2479a4a3e347ec070ca2a8/GsdAutomatico/Ouvidoria/views.py]</span>.</li>
        <li><strong>Criação Automática de PATD</strong>: Com base na análise do PDF, o sistema cria uma nova PATD, associando-a ao militar correspondente e verificando a existência de processos similares para evitar duplicidade <span class="cite">[cite: brek1n/em-buscar-do-gsd-automatico/Em-Buscar-do-GSD-Automatico-6b722cb465ccf0703f2479a4a3e347ec070ca2a8/GsdAutomatico/Ouvidoria/views.py]</span>.</li>
        <li><strong>Cadastro Inteligente</strong>: Se o militar mencionado no PDF não estiver na base de dados, a interface facilita o seu registo, pré-preenchendo os dados obtidos pela IA <span class="cite">[cite: brek1n/em-buscar-do-gsd-automatico/Em-Buscar-do-GSD-Automatico-6b722cb465ccf0703f2479a4a3e347ec070ca2a8/GsdAutomatico/Ouvidoria/templates/indexOuvidoria.html]</span>.</li>
        <li><strong>Gestão de Efetivo (CRUD)</strong>: Interface completa para Adicionar, Visualizar, Editar e Excluir militares, com pesquisa dinâmica e paginação <span class="cite">[cite: brek1n/em-buscar-do-gsd-automatico/Em-Buscar-do-GSD-Automatico-6b722cb465ccf0703f2479a4a3e347ec070ca2a8/GsdAutomatico/Ouvidoria/templates/militar_list.html]</span>.</li>
        <li><strong>Importação via Excel</strong>: Importe em massa o cadastro de militares a partir de uma planilha Excel, agilizando a configuração inicial do sistema <span class="cite">[cite: brek1n/em-buscar-do-gsd-automatico/Em-Buscar-do-GSD-Automatico-6b722cb465ccf0703f2479a4a3e347ec070ca2a8/GsdAutomatico/Ouvidoria/views.py, brek1n/em-buscar-do-gsd-automatico/Em-Buscar-do-GSD-Automatico-6b722cb465ccf0703f2479a4a3e347ec070ca2a8/GsdAutomatico/Ouvidoria/urls.py]</span>.</li>
        <li><strong>Gestão de PATDs e Fluxo de Trabalho Avançado</strong>:
            <ul>
                <li>Visualização e edição detalhada de cada processo <span class="cite">[cite: brek1n/em-buscar-do-gsd-automatico/Em-Buscar-do-GSD-Automatico-6b722cb465ccf0703f2479a4a3e347ec070ca2a8/GsdAutomatico/Ouvidoria/templates/patd_detail.html]</span>.</li>
                <li>Registo de até duas testemunhas por PATD <span class="cite">[cite: brek1n/em-buscar-do-gsd-automatico/Em-Buscar-do-GSD-Automatico-6b722cb465ccf0703f2479a4a3e347ec070ca2a8/GsdAutomatico/Ouvidoria/migrations/0008_patd_testemunha1_patd_testemunha2.py, brek1n/em-buscar-do-gsd-automatico/Em-Buscar-do-GSD-Automatico-6b722cb465ccf0703f2479a4a3e347ec070ca2a8/GsdAutomatico/Ouvidoria/forms.py]</span>.</li>
                <li>Recolha digital da assinatura de ciência do militar acusado <span class="cite">[cite: brek1n/em-buscar-do-gsd-automatico/Em-Buscar-do-GSD-Automatico-6b722cb465ccf0703f2479a4a3e347ec070ca2a8/GsdAutomatico/Ouvidoria/migrations/0011_patd_assinatura_militar_ciencia.py]</span>.</li>
                <li>Controlo de prazo para a apresentação da alegação de defesa, com notificações visuais <span class="cite">[cite: brek1n/em-buscar-do-gsd-automatico/Em-Buscar-do-GSD-Automatico-6b722cb465ccf0703f2479a4a3e347ec070ca2a8/GsdAutomatico/Ouvidoria/models.py, brek1n/em-buscar-do-gsd-automatico/Em-Buscar-do-GSD-Automatico-6b722cb465ccf0703f2479a4a3e347ec070ca2a8/GsdAutomatico/Ouvidoria/templates/patd_detail.html]</span>.</li>
                <li>Opções para estender o prazo ou registar a preclusão (prosseguir sem defesa) <span class="cite">[cite: brek1n/em-buscar-do-gsd-automatico/Em-Buscar-do-GSD-Automatico-6b722cb465ccf0703f2479a4a3e347ec070ca2a8/GsdAutomatico/Ouvidoria/urls.py, brek1n/em-buscar-do-gsd-automatico/Em-Buscar-do-GSD-Automatico-6b722cb465ccf0703f2479a4a3e347ec070ca2a8/GsdAutomatico/Ouvidoria/views.py]</span>.</li>
            </ul>
        </li>
        <li><strong>Geração de Documentos</strong>: Criação automática dos documentos do processo (PATD, Alegação de Defesa, Termo de Preclusão) em formato HTML, preenchidos dinamicamente com os dados do sistema a partir de templates <code>.docx</code> <span class="cite">[cite: brek1n/em-buscar-do-gsd-automatico/Em-Buscar-do-GSD-Automatico-6b722cb465ccf0703f2479a4a3e347ec070ca2a8/GsdAutomatico/Ouvidoria/views.py]</span>.</li>
        <li><strong>Gestão de Assinaturas</strong>: Interface dedicada para adicionar e gerir as assinaturas digitalizadas dos oficiais, que são usadas automaticamente nos documentos gerados <span class="cite">[cite: brek1n/em-buscar-do-gsd-automatico/Em-Buscar-do-GSD-Automatico-6b722cb465ccf0703f2479a4a3e347ec070ca2a8/GsdAutomatico/Ouvidoria/templates/Base.html, brek1n/em-buscar-do-gsd-automatico/Em-Buscar-do-GSD-Automatico-6b722cb465ccf0703f2479a4a3e347ec070ca2a8/GsdAutomatico/Ouvidoria/urls.py]</span>.</li>
        <li><strong>Sistema de Notificações</strong>: Alertas em tempo real na interface sobre PATDs com prazo de defesa expirado, permitindo ações rápidas como estender o prazo ou prosseguir com o processo <span class="cite">[cite: brek1n/em-buscar-do-gsd-automatico/Em-Buscar-do-GSD-Automatico-6b722cb465ccf0703f2479a4a3e347ec070ca2a8/GsdAutomatico/Ouvidoria/templates/Base.html]</span>.</li>
        <li><strong>Configurações Gerais</strong>: Painel para definir parâmetros do sistema, como o Comandante do GSD padrão e os prazos para a defesa <span class="cite">[cite: brek1n/em-buscar-do-gsd-automatico/Em-Buscar-do-GSD-Automatico-6b722cb465ccf0703f2479a4a3e347ec070ca2a8/GsdAutomatico/Ouvidoria/models.py, brek1n/em-buscar-do-gsd-automatico/Em-Buscar-do-GSD-Automatico-6b722cb465ccf0703f2479a4a3e347ec070ca2a8/GsdAutomatico/Ouvidoria/templates/Base.html]</span>.</li>
    </ul>

    <h2>3. Tecnologias Utilizadas</h2>
    <ul>
        <li><strong>Backend</strong>: Python, Django</li>
        <li><strong>Inteligência Artificial</strong>: LangChain, OpenAI API</li>
        <li><strong>Base de Dados</strong>: SQLite (padrão do Django)</li>
        <li><strong>Frontend</strong>: HTML, CSS, JavaScript</li>
        <li><strong>Bibliotecas Python Principais</strong>:
            <ul>
                <li><code>django</code></li>
                <li><code>langchain-openai</code></li>
                <li><code>langchain-community</code></li>
                <li><code>pypdf</code></li>
                <li><code>python-dotenv</code></li>
                <li><code>pandas</code> & <code>openpyxl</code> (para importação de Excel)</li>
                <li><code>python-docx</code> (para leitura de templates de documentos)</li>
            </ul>
        </li>
    </ul>

    <h2>4. Pré-requisitos</h2>
    <p>Antes de começar, garanta que tem os seguintes softwares instalados na sua máquina:</p>
    <ul>
        <li>Python (versão 3.9 ou superior)</li>
        <li>pip (geralmente vem com o Python)</li>
        <li>Git</li>
    </ul>

    <h2>5. Guia de Instalação</h2>
    <p>Siga os passos abaixo para configurar o ambiente de desenvolvimento local.</p>
    <h3>1. Clonar o Repositório</h3>
    <pre><code>git clone &lt;URL_DO_SEU_REPOSITORIO&gt;
cd &lt;NOME_DA_PASTA_DO_PROJETO&gt;</code></pre>

    <h3>2. Criar e Ativar um Ambiente Virtual</h3>
    <p>É uma boa prática usar um ambiente virtual para isolar as dependências do projeto.</p>
    <p><strong>Para Windows:</strong></p>
    <pre><code>python -m venv venv
venv\Scripts\activate</code></pre>
    <p><strong>Para macOS/Linux:</strong></p>
    <pre><code>python3 -m venv venv
source venv/bin/activate</code></pre>

    <h3>3. Instalar as Dependências</h3>
    <p>Instale todas as bibliotecas necessárias listadas no ficheiro <code>requirements.txt</code>.</p>
    <pre><code>pip install -r requirements.txt</code></pre>

    <h3>4. Configurar Variáveis de Ambiente</h3>
    <p>A integração com a OpenAI requer uma chave de API.</p>
    <ul>
        <li>Crie um ficheiro chamado <code>.env</code> na raiz do projeto (na mesma pasta que <code>manage.py</code>).</li>
        <li>Dentro do ficheiro <code>.env</code>, adicione a sua chave da API:</li>
    </ul>
    <pre><code>OPENAI_API_KEY='sua_chave_secreta_da_openai_aqui'</code></pre>

    <h3>5. Aplicar as Migrações da Base de Dados</h3>
    <p>Estes comandos irão criar as tabelas (Militar, PATD, etc.) na sua base de dados SQLite.</p>
    <pre><code>python manage.py makemigrations Ouvidoria
python manage.py migrate</code></pre>

    <h3>6. Criar um Superutilizador</h3>
    <p>Para aceder à área de administração do Django (<code>/admin</code>), precisa de um utilizador com privilégios.</p>
    <pre><code>python manage.py createsuperuser</code></pre>
    <p>Siga as instruções para criar o seu nome de utilizador e palavra-passe.</p>

    <h2>6. Como Executar o Projeto</h2>
    <p>Com tudo configurado, inicie o servidor de desenvolvimento do Django:</p>
    <pre><code>python manage.py runserver</code></pre>
    <p>A aplicação estará disponível no seu navegador nos seguintes endereços:</p>
    <ul>
        <li><strong>Página Principal (Analisador)</strong>: <code>http://127.0.0.1:8000/Ouvidoria/</code></li>
        <li><strong>Área de Administração</strong>: <code>http://127.0.0.1:8000/admin/</code> (use as credenciais do superutilizador)</li>
    </ul>

    <h2>7. Estrutura do Projeto</h2>
    <pre><code>.
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
</code></pre>

    <h2>8. Licença</h2>
    <p>Este projeto está licenciado sob a Licença MIT. Consulte o ficheiro <code>LICENSE</code> para mais detalhes <span class="cite">[cite: brek1n/em-buscar-do-gsd-automatico/Em-Buscar-do-GSD-Automatico-6b722cb465ccf0703f2479a4a3e347ec070ca2a8/LICENSE]</span>.</p>

</body>
</html>
