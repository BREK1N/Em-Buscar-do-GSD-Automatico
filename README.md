Sistema de Gestão Disciplinar (Ouvidoria Inteligente)
1. Introdução
O Sistema de Gestão Disciplinar é uma aplicação web desenvolvida com Django, projetada para otimizar e automatizar processos administrativos em um contexto militar. A principal funcionalidade do sistema é a capacidade de analisar documentos PDF de transgressões disciplinares usando Inteligência Artificial (com LangChain e a API da OpenAI) para extrair informações e criar automaticamente um Processo Administrativo Disciplinar (PATD).

Além da análise inteligente de documentos, a plataforma oferece um sistema robusto para a gestão completa do efetivo de militares e dos PATDs gerados, tudo através de uma interface moderna, responsiva e com temas claro e escuro.

2. Funcionalidades Principais
Analisador de PDF com IA: Faça o upload de um documento PDF e a IA irá extrair automaticamente o nome do militar, a descrição da transgressão e o local do ocorrido.

Criação Automática de PATD: Com base na análise do PDF, o sistema verifica se o militar está cadastrado e cria uma nova PATD, associando-a ao militar correspondente.

Cadastro Inteligente: Caso o militar extraído do PDF não esteja na base de dados, a interface oferece um fluxo para cadastrá-lo, já preenchendo os dados obtidos pela IA.

Gestão de Efetivo (CRUD): Interface completa para Adicionar, Visualizar, Editar e Excluir militares do banco de dados, com funcionalidades de busca e paginação.

Gestão de PATDs (CRUD): Sistema para Visualizar, Editar e Excluir PATDs, com detalhes completos sobre cada processo.

Histórico por Militar: Visualize facilmente todas as PATDs associadas a um militar específico.

Interface Moderna: Layout responsivo que se adapta a diferentes tamanhos de ecrã e funcionalidade de tema claro/escuro para preferência do utilizador.

3. Tecnologias Utilizadas
Backend: Python, Django

Inteligência Artificial: LangChain, OpenAI API

Banco de Dados: SQLite (padrão do Django)

Frontend: HTML, CSS, JavaScript

Bibliotecas Python: django, langchain-openai, pypdf, python-dotenv, pydantic

4. Pré-requisitos
Antes de começar, garanta que tem os seguintes softwares instalados na sua máquina:

Python (versão 3.9 ou superior)

pip (geralmente vem com o Python)

5. Guia de Instalação
Siga os passos abaixo para configurar o ambiente de desenvolvimento local.

1. Clonar o Repositório

git clone <URL_DO_SEU_REPOSITORIO>
cd <NOME_DA_PASTA_DO_PROJETO>

2. Criar e Ativar um Ambiente Virtual
É uma boa prática usar um ambiente virtual para isolar as dependências do projeto.

# Para Windows
python -m venv venv
venv\Scripts\activate

# Para macOS/Linux
python3 -m venv venv
source venv/bin/activate

3. Instalar as Dependências
Instale todas as bibliotecas necessárias listadas no ficheiro requirements.txt.

pip install -r requirements.txt

4. Configurar Variáveis de Ambiente
A integração com a OpenAI requer uma chave de API.

Crie um ficheiro chamado .env na raiz do projeto (na mesma pasta que manage.py).

Dentro do ficheiro .env, adicione a sua chave da API:

OPENAI_API_KEY='sua_chave_secreta_da_openai_aqui'

5. Aplicar as Migrações do Banco de Dados
Estes comandos irão criar as tabelas (Militar, PATD, etc.) na sua base de dados.

python manage.py makemigrations Ouvidoria
python manage.py migrate

6. Criar um Superutilizador
Para aceder à área de administração do Django (/admin), precisa de um utilizador com privilégios.

python manage.py createsuperuser

Siga as instruções para criar o seu nome de utilizador e palavra-passe.

6. Como Rodar o Projeto
Com tudo configurado, inicie o servidor de desenvolvimento do Django:

python manage.py runserver

A aplicação estará disponível no seu navegador no seguinte endereço: http://127.0.0.1:8000/Ouvidoria/

Página Principal (Analisador): http://127.0.0.1:8000/Ouvidoria/

Área de Administração: http://127.0.0.1:8000/admin/ (use as credenciais do superutilizador)

7. Estrutura do Projeto
.
├── GsdAutomatico/         # Pasta principal do projeto Django
│   ├── settings.py        # Configurações do projeto
│   └── urls.py            # URLs principais
├── Ouvidoria/             # Aplicação principal "Ouvidoria"
│   ├── models.py          # Definição das tabelas do banco de dados
│   ├── views.py           # Lógica de negócio (controllers)
│   ├── urls.py            # URLs específicas da aplicação
│   ├── forms.py           # Formulários Django
│   ├── admin.py           # Configuração da interface de admin
│   └── templates/         # Ficheiros HTML
├── static/                # Ficheiros estáticos (CSS, JS, Imagens)
│   └── css/
│       └── style.css
├── manage.py              # Utilitário de linha de comando do Django
└── requirements.txt       # Lista de dependências Python

8. Licença
Este projeto está licenciado sob a Licença MIT. Consulte o ficheiro LICENSE para mais detalhes.