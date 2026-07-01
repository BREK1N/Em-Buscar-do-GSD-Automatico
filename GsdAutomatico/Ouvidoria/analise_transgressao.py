# GsdAutomatico/Ouvidoria/analise_transgressao.py
import httpx
import logging
import os
from typing import List, Dict, Optional
from dotenv import load_dotenv
from langchain_openai import ChatOpenAI
from langchain.prompts import ChatPromptTemplate
from pydantic import BaseModel, Field
from langchain_core.output_parsers import PydanticOutputParser, StrOutputParser
from langchain.output_parsers import BooleanOutputParser

load_dotenv()

logger = logging.getLogger(__name__)

openai_api_key = os.getenv("OPENAI_API_KEY")
if not openai_api_key:
    raise ValueError("A variável OPENAI_API_KEY não foi encontrada no ficheiro .env")

# --- Configuração do cliente HTTP para proxy corporativo ---
# Para usar o certificado do proxy da Intraer, defina REQUESTS_CA_BUNDLE=/caminho/cert.pem no .env
# Nunca use verify=False em produção — permite ataques MITM que expõem dados sigilosos.
proxy_url = os.getenv("http_proxy") or os.getenv("HTTP_PROXY") or os.getenv("https_proxy") or os.getenv("HTTPS_PROXY")
ssl_verify = os.getenv("REQUESTS_CA_BUNDLE") or os.getenv("SSL_CERT_FILE") or True

logger.debug("Configurando cliente OpenAI. Proxy: %s | SSL verify: %s", proxy_url or "nenhum", ssl_verify)

if proxy_url:
    http_client = httpx.Client(
        proxy=proxy_url,
        verify=ssl_verify,
        timeout=60.0,
    )
else:
    http_client = httpx.Client(verify=ssl_verify)

model = ChatOpenAI(
    model="gpt-4.1",
    temperature=0,
    api_key=openai_api_key,
    http_client=http_client,
    max_retries=3,  # retry automático com backoff exponencial em RateLimitError/Timeout
)
logger.debug("Cliente OpenAI inicializado com sucesso.")

# --- MODELOS DE DADOS ---

# Modelo para representar um único militar acusado
class MilitarAcusado(BaseModel):
    nome_completo: Optional[str] = Field(
        default="",
        description=(
            "Nome completo do militar ACUSADO — quem COMETEU a falta descrita no documento. "
            "NUNCA inclua: quem assinou o documento, quem relatou o fato, o comandante destinatário, "
            "testemunhas, vítimas (exceto em brigas/rixas onde todos são acusados), "
            "ou qualquer militar mencionado apenas como contexto."
        ),
    )
    nome_guerra: Optional[str] = Field(
        default="",
        description="Nome de guerra (sobrenome em maiúsculas) do militar ACUSADO. Ex: SILVA, SANTOS.",
    )
    saram: Optional[str] = Field(
        default="",
        description=(
            "SARAM/Matrícula do militar ACUSADO. Tem 6 ou 7 dígitos. "
            "Se aparecerem vários SARAMs no documento, use SOMENTE o associado ao transgressor — "
            "geralmente aparece junto ao nome do acusado na descrição da falta."
        ),
    )
    posto_graduacao: Optional[str] = Field(
        default="",
        description="Posto ou graduação do militar ACUSADO. Ex: S2, CB, 3S, Sgt, Ten.",
    )
    transgressao_individual: Optional[str] = Field(
        default="",
        description=(
            "Trecho copiado LITERALMENTE do documento que descreve o que ESTE acusado específico fez. "
            "Se todos cometeram o mesmo ato num mesmo trecho, copie esse trecho para todos. "
            "PROIBIDO inventar, resumir ou interpretar."
        ),
    )

# Modelo principal para a análise
class AnaliseTransgressao(BaseModel):
    acusados: List[MilitarAcusado] = Field(
        description=(
            "Lista com UM item para CADA militar que COMETEU a transgressão. "
            "NÃO inclua: signatário do documento, quem relatou, comandante, testemunhas, "
            "ou militares mencionados apenas como contexto. "
            "Inclua TODOS os transgressores — não pare no primeiro nome encontrado."
        ),
    )
    transgressao: str = Field(description="Trecho do documento copiado LITERALMENTE, palavra por palavra. Não altere nenhuma palavra. Não acrescente nada. Não interprete. Apenas transcreva.")
    local: str = Field(description="O local onde a transgressão ocorreu.")
    data_ocorrencia: str = Field(description="A data da transgressão no formato AAAA-MM-DD. Se não mencionada, retorne string vazia.")
    protocolo_comaer: str = Field(description="O número de protocolo COMAER, se houver.")
    oficio_transgressao: str = Field(description="O número do documento/ofício de transgressão.")
    data_oficio: str = Field(description="A data de emissão do documento (AAAA-MM-DD).")

    class Config:
        extra = "forbid"


# --- FUNÇÃO DE ANÁLISE (PROMPT REFINADO) ---
def analisar_documento_pdf(conteudo_pdf: str) -> AnaliseTransgressao:
    """
    Função que invoca a IA para analisar o conteúdo do PDF e extrair os dados estruturados,
    com foco na identificação correta dos acusados.
    """
    structured_llm = model.with_structured_output(AnaliseTransgressao)

    sys_prompt = """
Você é um extrator de dados de documentos militares. Sua única função é COPIAR informações do documento. Você NÃO reescreve, NÃO interpreta, NÃO resume, NÃO acrescenta nada.

═══════════════════════════════════════════
PASSO 1 — ENTENDA O DOCUMENTO ANTES DE PREENCHER
═══════════════════════════════════════════
Antes de extrair qualquer dado, responda mentalmente:
a) PROPÓSITO: Qual é o assunto do documento? (ex: "relato de ausência sem licença", "comunicado de embriaguez em serviço")
b) ACUSADO(S): Quem COMETEU a falta? (quem o documento ACUSA — o objeto do relato)
c) OUTROS MENCIONADOS: Quem mais aparece no documento SEM ter cometido a falta?
   - Quem ASSINOU o documento (signatário)
   - Quem RELATOU ou DENUNCIOU o fato
   - O COMANDANTE a quem o documento é dirigido (destinatário)
   - TESTEMUNHAS que presenciaram
   - SUPERVISORES mencionados como referência
   - Qualquer militar citado apenas para contextualizar

Somente os militares do item (b) vão para a lista `acusados`. Todos do item (c) são IGNORADOS.

═══════════════════════════════════════════
PASSO 2 — COMO IDENTIFICAR O ACUSADO NO TEXTO
═══════════════════════════════════════════
O acusado é identificado por padrões como:
✔ "O militar [NOME/POSTO/SARAM] foi flagrado..."
✔ "Verificou-se que [NOME] se encontrava..."
✔ "[NOME] se ausentou sem autorização..."
✔ "[NOME] agrediu / recusou / faltou / chegou atrasado..."
✔ "Conforme o exposto, [NOME] cometeu/praticou..."
✔ Listas numeradas: "1º - [NOME], 2º - [NOME]..." como envolvidos/acusados

O acusado NÃO é identificado por:
✘ "Assina: [NOME]" / "[NOME] - Comandante" / "De: [NOME]" / "Para: [NOME]"
✘ "Testemunha: [NOME]" / "Presenciado por [NOME]"
✘ "Conforme relatório do [NOME]" / "Segundo informação do Sgt [NOME]"
✘ "[NOME] é o chefe/supervisor de [acusado]"
✘ Nomes que aparecem APENAS no cabeçalho, rodapé ou bloco de assinatura

═══════════════════════════════════════════
PASSO 3 — REGRAS DE EXTRAÇÃO
═══════════════════════════════════════════
TRANSCRIÇÃO LITERAL:
- Os campos `transgressao` e `transgressao_individual` devem ser CÓPIAS EXATAS do texto.
- PROIBIDO corrigir ortografia, pontuação ou gramática do documento original.
- PROIBIDO acrescentar frases como "o que configura", "demonstrando que", "em desacordo com".
- Se houver erro de digitação no documento, COPIE o erro.

MÚLTIPLOS ACUSADOS:
- A lista `acusados` deve ter UM item para CADA militar que COMETEU a falta.
- NÃO pare no primeiro nome — leia o documento inteiro.
- Faltas coletivas (briga, rixa, embriaguez em grupo, ausência coletiva) têm MÚLTIPLOS acusados.
- Se o documento listar "1º - FULANO, 2º - BELTRANO", cada um é um item separado.
- NUNCA retorne lista vazia se houver acusado identificável no documento.

SARAM:
- Tem 6 ou 7 dígitos. Associe SOMENTE ao acusado ao qual está vinculado no texto.
- Não transfira SARAM de uma pessoa para outra.

DATA DA OCORRÊNCIA:
- Use SOMENTE a data do FATO, nunca a data de elaboração, assinatura ou protocolo.
- Formato: AAAA-MM-DD. Data por extenso → converta. Intervalo → use o primeiro dia.
- Se a data do fato não constar, retorne string vazia.

CAMPO `transgressao_individual`:
- Copie LITERALMENTE o trecho que descreve o que AQUELE acusado específico fez.
- Se todos cometeram o mesmo ato no mesmo trecho, copie esse trecho para todos.
- PROIBIDO inventar texto que não esteja no documento.
"""

    human_prompt = (
        "Leia o documento abaixo com atenção.\n\n"
        "PASSO 1: Identifique o propósito do documento e quem COMETEU a falta (acusado).\n"
        "PASSO 2: Identifique quem NÃO é acusado (signatário, relator, destinatário, testemunhas) e IGNORE essas pessoas.\n"
        "PASSO 3: Extraia os dados copiando o texto LITERALMENTE, sem alterar nenhuma palavra.\n\n"
        "Certifique-se de incluir TODOS os acusados — não apenas o primeiro encontrado.\n\n"
        "Documento:\n{documento}"
    )

    prompt = ChatPromptTemplate.from_messages([
        ("system", sys_prompt),
        ("human", human_prompt)
    ])

    chain = prompt | structured_llm
    resultado = chain.invoke({"documento": conteudo_pdf})
    return resultado


# --- FUNÇÕES AUXILIARES ---

def enquadra_item(transgressao):
    class Item(BaseModel):
        item: list = Field(description="Defina uma lista de dicionários python com a chave 'numero' e o valor sendo o número do item escolhido e a chave 'descricao' e o valor sendo a descrição do item. Cada item da lista deve ser um dicionário com um item que foi enquadrado.")

    parser = PydanticOutputParser(pydantic_object=Item)

    sys_prompt = """
Você é um especialista em enquadramento disciplinar militar. Sua tarefa é identificar SOMENTE os itens do RDAER que se aplicam diretamente ao fato descrito na transgressão.

REGRAS OBRIGATÓRIAS:
1. Enquadre APENAS itens cujo texto descreve exatamente o que foi relatado. Se o item não tiver relação direta e clara com o fato, NÃO inclua.
2. NÃO enquadre itens por semelhança vaga ou interpretação ampla. O enquadramento deve ser óbvio e direto.
3. Prefira poucos itens certeiros a muitos itens duvidosos. É melhor enquadrar 1 item correto do que 5 com dúvida.
4. O item 100 ("concorrer de qualquer modo para a prática de transgressão") só deve ser usado se houver participação indireta explícita no relato.
5. PROIBIDO inventar ou deduzir fatos que não estão descritos no relato.

    São transgressões disciplinares:
    1 - aproveitar-se de missões de vôo para realizar vôos de caráter não militar ou pessoal;
    2 - utilizar-se sem ordem, de aeronave militar ou civil;
    3 - transportar, na aeronave que comanda, pessoal ou material sem autorização de autoridade competente ;
    4 - deixar de observar as regras de tráfego aéreo;
    5 - deixar de cumprir ou alterar , sem justo motivo, as determinações constantes da ordem de missão, ou qualquer outra determinação escrita ou verbal;
    6 - executar vôos a baixa altura acrobáticos ou de instrução fora das áreas para tal fim estabelecidas, excetuando-se os autorizados por autoridade competente;
    7 - fazer, ou permitir que se faça, a escrituração do relatório de vôo com dados que não correspondam com a realidade;
    8 - deixar de cumprir ou fazer cumprir, quando isso lhe competir, qualquer prescrição regularmentar;
    9 - deixar por negligência, de cumprir ordem recebida:
    10 - deixar de comunicar ao superior a execução de ordem dele recebida:
    11 - deixar de executar serviço para qual tenha sido escalado;
    12 - deixar de participar, a tempo à autoridade a que estiver imediatamente subordinado, a impossibilidade de comparecer ao local de trabalho, ou a qualquer ato de serviço ou instrução a que deva tomar parte ou a que deva assistir;
    13 - retardar, sem justo motivo, a execução de qualquer ordem;
    14 - permutar serviço, sem a devida autorização
    15 - declarar-se doente ou simular doença para se esquivar de qualquer serviço ou instrução;
    16 - trabalhar mal, intencionalmente ou por falta de atenção em qualquer serviço ou instrução;
    17 - ausentar-se, sem licença, do local do serviço ou de outro qualquer em que deva encontra-se por força de disposição legal ou ordem;
    18 -faltar ou chegar atrasado, sem justo motivo, a qualquer ato, serviço ou instrução de que deva participar ou a que deva assistir;
    19 - abandonar o serviço para o qual tenha sido designado;
    20 - deixar de cumprir punição legalmente imposta;
    21 - dirigir-se ou referir-se a superior de modo desrespeitoso;
    22 - procurar desacreditar autoridade ou superior hierárquico, ou concorrer para isso;
    23 - censurar atos superior ;
    24 - ofender moralmente ou procurar desacreditar outra pessoa quer seja militar ou civil, ou concorrer para isso;
    25 - deixar o militar quer uniformizado quer trajando civilmente, de cumprimentar o superior quando uniformizado, ou em traje civil desde que o conheça;
    26 - deixar o militar deliberadamente, de corresponder ao cumprimento que seja dirigido;
    27 - deixar o oficial ou aspirante-a-oficial, quando no quartel, de apresentar-se ao seu Comandante para cumprimentá-lo de acordo com as normas de cada Organização ;
    28 - deixar , quando sentado de oferecer o lugar a superior de pé por falta de lugar, exceto em teatro, cinemas, restaurantes ou casas análogas, bem como em transportes pagos;
    29 - deixar o oficial ou aspirante-a-oficial quando de serviço de Oficial-de-Dia de se apresentar regularmente a qualquer superior que entrar em sua Organização, quando disso tenha ciência;
    30 - retirar-se da presença de superior sem a devida licença ou ordem para o fazer;
    31 - entrar em qualquer Organização Militar ou dela sair por lugar que não o para isso destinado;
    32 - entrar, ou sair o militar em Organização Militar que não a sua, sem dar ciência ao Comandante ou Oficial de Serviço ou o respectivos substitutos;
    33 - entrar, sem permissão, em dependência destinada a superior, ou onde este se ache, ou em outro local cuja entrada lhe seja normalmente vedada;
    34 - desrespeitar, por palavras ou atos, as instituições, religiões ou os costumes do país estrangeiro em que se achar;
    35 - desrespeitar autoridade civil;
    36 - desrespeitar medidas gerais de ordem policial, embaraçar sua execução ou para isso concorrer;
    37 - representar contra o superior, sem fundamento ou sem observar as prescrições regularmentares;
    38 - comunicar a superior hierárquico que irá representar contra o mesmo e deixar de fazê-lo;
    39 - faltar, por ação ou omissão, ao respeito devido aos Símbolos Nacionais, Estaduais, Municipais, de nações amigas ou de instituições militares;
    40 - tomar parte, sem autorização, em competições desportivas militares de círculos diferentes;
    41 - usar de violência desnescessária no ato de efetuar prisão;
    42 - tratar o subordinado hierárquico com injustiça, prepotência ou maus tratos;
    43 - maltratar o preso que seja sob sua guarda;
    44 - consentir que presos conservem em seu poder objetos não permitidos ou instrumentos que se prestem à danificação das prisões;
    45 - introduzir, distribuir ou possuir, em Organização Militar, publicações, estampas prejudiciais à disciplina e à moral;
    46 - frequentar lugares incompatíveis com o decoro da sociedade;
    47 - desrespeitar as convenções sociais
    48 - ofender a moral ou os bons costumes, por atos, palavras e gestos;
    49 - porta-se incovenientemente ou sem compostura;
    50 - faltar à verdade ou tentar iludir outrem;
    51 - induzir ou concorrer intencionalmente para que outrem incorra em erro;
    52 - apropria-se de quantia ou objeto pertencente a terceiro era proveito próprio ou de outrem,
    53 - concorrer para discórdia, de sarmonia ou inimizade entre colegas de corporação ou entre superiores hierárquicos;
    54 - utilizar-se do anonimato para qualquer fim;
    55 - estar fora do unifrome ou trazê-lo em desalinho
    56 - ser descuidado na apresentação pessoal e no asseio do corpo;
    57 - travar disputa, rixa ou luta corporal;
    58 - embriagar-se com bebida alcoólica ou similar;
    59 - fazer uso de psicotrópicos, entorpecentes ou similar;
    60 - tomar parte em jogos proibidos por lei;
    61 - assumir compromissos, prestar declarações ou divulgar informações, em nome da Corporação ou da Unidade em que serve, sem estar para isso autorizado;
    62 - servir-se da condição de militar ou da função que exerce para usufuir vantagens pessoais;
    63 - contrair dívidas ou assumir compromissos superiores às suas possibilidades, comprometendo o bom nome da classe;
    64 - esquivar-se a satisfazer compromissos de ordem moral ou pecuniária que houver assumido;
    65 - realizar ou propor empréstimo de dinheiro a outro militar, visando auferição de lucro;
    66 -deixar de cumprir ou de fazer cumprir, o previsto em Regulamentos e Atos emanados de autoridade competente;
    67 -representar a corporação em qualquer ato, sem estar para isso autorizado;
    68 - vagar ou passear, o cabo, soldado ou taifeiro por logradouros públicos em horas de expediente, sem permissão escrita da autoridade competente;
    69 - publicar, pela comentar, difundir ou apregoar notícias exageradas, tendeciosas ou falsas , de caráter alarmante ou não, que possam gerar o desassossego público;
    70 - publicar, pela imprensa outro meio, sem permissão da autoridade competente, documentos oficiais ou fornecer dados neles contidos a pessoas não autorizadas;
    71 - travar polêmica, através dos meios de comunicação sobre assunto militar ou político;
    72 - autorizar, promover, assinar representações, documentos coletivos ou publicações de qualquer tipo, com finalidade política, de reivindicação ou de crítica a autoridades constituídas ou às suas atividades;
    73 - externar-se publicamente a respeito de assuntos políticos;
    74 - provocar ou participar, em Organização Militar, de discussão sobre política ou religião que possa causar desassossego;
    75 - ser indiscreto em relação a assuntos de caráter oficial, cuja divulgação possa ser prejudicial à disciplinar ou a boa ordem do serviço;
    76 - comparecer fardado a manifestações ou reuniões de caráter político;
    77 - fumar em lugares em que seja isso vedado;
    78 - deixar, quando for o caso, de punir o subordinado hierárquico que cometer transgressão, ou deixar de comunicá-la à autoridade competente;
    79 - deixar de comunicar ao superior imediato, ou na ausência deste a outro, qualquer informação sobre iminente perturbação da ordem pública ou da boa marcha do serviço, logo que disso tenha conhecimento;
    80 - deixar de apresentar-se sem justo motivo, por conclusão de férias, dispensa, licença, ou imediatamente após tomar conhecimento que qualquer delas lhe tenha sido interrompida ou suspensa;
    81 - deixar de comunicar ao órgão competente de sua Organização Militar o seu endereço domiciliar;
    82 - deixar de ter consigo documentos de identidade que o identifiquem;
    83 - deixar de estar em dia com as inspeções de saúde obrigatórias;
    84 -deixar de identificar-se, quando solicitado por quem de direito
    85 - recusar pagamento, fardamento, alimento e equipamento ou outros artigos de recebimento obrigatório;
    86 - ser descuidado com objetos pertencentes à Fazenda Nacional;
    87 - dar, vender, empenhar ou trocar peças de uniforme ou equipamento fornecidos pela Fazenda Nacional;
    88 - extraviar ou concorrer para que se extravie ou estrague qualquer objeto da Fazenda Nacional ou documento oficial, sob a sua responsabilidade;
    89 - abrir, ou tentar abrir, qualquer dependência da Organização Militar, fora das horas de expediente, desde que não seja o respectivo chefe ou por necessidade urgente de serviço;
    90 - introduzir bebidas alcoólicas, entorpercentes ou similares em Organização Militar sem que para isso esteja autorizado;
    91 - introduzir material inflamável ou explosivo em Organização Militar sem ser em cumprimento de ordem;
    92 - introduzir armas ou instrumentos proibidos em Organização Militar, ou deles estar de posse, sem autorização;
    93 - conversar com sentinela, vigia, plantão ou preso incomunicável;
    94 - conversar ou fazer ruído desnecessário, por ocasião de manobra, exercício, reunião para qualquer serviço ou após toque de silêncio;
    95 - dar toques, fazer sinais, içar ou arriar a Bandeira Nacional ou insígnias, sem ter ordem para isso;
    96 - fazer, ou permitir que se faça, dentro de Organização Militar rifas, sorteios coletas de dinheiro etc.. sem autorização do Comandante;
    97 - ingressar, como atleta, em equipe profissional, sem autorização do Comandante;
    98 - andar a praça armada, sem ser em serviço ou ser ter para isso ordem escrita, a qual deverá ser exibida quando solicitada;
    99 - usar traje civil, quando as disposições em vigor não o permitirem;
    100 - concorrer, de qualquer modo, para a prática de transgressão disciplinar.
    # Formatação #
    Você deve retornar no seguinte formato:
    <formato>
    {format_instructions}
    </formato>
    # Transgressão #
    {transgressao}
    """

    prompt_template = ChatPromptTemplate.from_messages(
        [("system", sys_prompt)],
    ).partial(format_instructions=parser.get_format_instructions())

    chain = prompt_template | model | parser
    resposta = chain.invoke({"transgressao": transgressao})
    return resposta


def verifica_agravante_atenuante(historico, transgressao, justificativa, itens, comportamento_anterior: str):
    class Item(BaseModel):
        item: list = Field(description="""Defina uma lista contendo um único dicionário python. O dicionário deve ter a chave 'agravantes' com uma lista das letras correspondentes, e a chave 'atenuantes' com uma lista das letras correspondentes.""")

    parser = PydanticOutputParser(pydantic_object=Item)

    sys_prompt = """
    # Contexto #
    Você é um especialista em determinar o que são circunstâncias atenuantes e agravantes no julgamento de uma transgressão disciplinar militar, de acordo com o Regulamento Disciplinar da Aeronáutica (RDAER). Você deve ser extremamente rigoroso e técnico.

    # Informações do RDAER #
    2 - São circunstâncias atenuantes:
    a) o bom comportamento;
    b) relevância de serviços prestados;
    c) falta de prática do serviço;
    d) ter sido a transgressão, cometida por influência de fatores adversos;
    e) ocorrência da transgressão para evitar mal maior;
    f) defesa dos direitos próprios ou de outrem.

    3 - São circunstâncias agravantes:
    a) mau comportamento;
    b) reincidência na mesma transgressão;
    c) prática simultânea ou conexão de duas ou mais transgressões;
    d) existência de conluio;
    e) premeditação ou má-fé;
    f) ocorrência de transgressão colocando em risco vidas humanas, segurança de aeronave, viaturas ou propriedade do Estado ou de particulares;
    g) ocorrência da transgressão em presença de subordinado, de tropa ou em público;
    h) abuso de autoridade hierárquica ou funcional;
    i) ocorrência da transgressão durante o serviço ou instrução.

    # Regras de Análise Obrigatórias #
    1.  **Atenuante 'a' (Bom Comportamento):** O militar SEMPRE começa com o atenuante 'a', a menos que a Regra 2 se aplique.
    2.  **Agravante 'a' (Mau Comportamento):** Se o 'Comportamento Anterior' fornecido for "Mau comportamento", remova o atenuante 'a' e adicione o agravante 'a'.
    3.  **Agravante 'c' (Conexão de Transgressões):** Se a transgressão atual foi enquadrada em mais de um item do RDAER (a lista de 'Itens da Transgressão Atual' terá mais de um elemento), adicione o agravante 'c'.
    4.  **Agravante 'i' (Ocorrência em Serviço):** Leia a descrição da 'Transgressão Atual'. Se o texto indicar que o fato ocorreu "durante o serviço", "em escala de serviço", "de serviço", "em missão", ou qualquer expressão sinônima, adicione OBRIGATORIAMENTE o agravante 'i'.
    5.  **Agravante 'b' (Reincidência):** ESTA É A VERIFICAÇÃO MAIS CRÍTICA. Compare os NÚMEROS dos itens da 'Itens da Transgressão Atual' com os NÚMEROS dos itens mencionados no 'Histórico do Militar'. Se houver QUALQUER número de item em comum, adicione OBRIGATORIAMENTE o agravante 'b'.

    # Dados para Análise #
    - **Transgressão Atual:** {transgressao}
    - **Itens da Transgressão Atual:** {itens}
    - **Histórico do Militar:** {historico}
    - **Justificativa do Militar:** {justificativa}
    - **Comportamento Anterior:** {comportamento_anterior}

    # Formato da Resposta #
    Você deve retornar no seguinte formato JSON, sem nenhum texto adicional.
    {format_instructions}
    """

    prompt_template = ChatPromptTemplate.from_messages(
        [("system", sys_prompt)],
    ).partial(format_instructions=parser.get_format_instructions())

    chain = prompt_template | model | parser
    resposta = chain.invoke({
        "transgressao": transgressao,
        "justificativa": justificativa,
        "historico": historico,
        "itens": itens,
        "comportamento_anterior": comportamento_anterior 
    })
    return resposta


def sugere_punicao(transgressao, agravantes, atenuantes, itens, observacao):

    class Formatador(BaseModel):
        punicao: dict = Field(description="Defina um dicionário python onde uma chave será 'punicao' e o respectivo valor será a punição definida e outra chave será 'explicacao' e o respectivo valor será a explicação do porquê você definiu esta punição")

    parser = PydanticOutputParser(pydantic_object=Formatador)

    sys_prompt = """
    # Contexto #
    Voce é um especialista em sugerir punições disciplinares, de acordo com o regulamento.

    # Regulamento #

    As transgressões disciplinares são classificadas em graves, médias e leves - conforme a gradação do dano que possam causar à disciplina, ao serviço ou à instrução.
    Será classificada como grave a transgressão:
    a) de natureza desonrosa;
    b) ofensiva à dignidade militar;
    c) atentatória às instituições ou ao Estado;
    d) de indisciplina de vôo;
    e) de negligência ou de imprudência na manutenção ou operação de aeronaves ou viaturas de forma
    a afetar a sua segurança;
    f) que comprometa a saúde ou coloque em perigo vida humana

    As punições disciplinares previstas neste regulamento, são:
    1 - Repreensão:
        a) verbal
        b) por escrito
    2 - Detenção até 30 dias.
    3 - Prisão até 30 dias.

    # Regras #
    1. Os dias definidos nas punições de detenção e prisão serão sempre um número par.
    2. Use os exemplos de padrão de punição como base para conseguir definir qual a punição mais justa. A partir dele aumente ou diminua a punição de acordo com os agravantes, atenuantes e observações apresentados.
    3. Os agravantes 'b', 'c', 'g', 'h', 'i' aumentam a punição em 2 dias, os agravantes 'a', 'd', 'e', f' aumentam a punição em 4 dias.
    4. O agravante de reincidência aumenta a punição em 2 dias para cada vez que o militar foi reincidente.
    5. Os atenuantes 'a', 'b', 'c' diminuem a punição em 2 dias, os atenuantes 'd', 'e', 'f' diminuem a punição em 4 dias.
    6. Se com as reduções realizadas pelos atenuantes resultarem em 0 dias, a punição será repreensão por escrito.
    7. Se a punição original for repreensão por escrito, os agravantes aumentaram para detenção, na respectiva quantidade de dias.
    8. Caso a transgressão apresentada seja completamente diferente dos exemplos de padrão de punição, não sendo possível usa-los como base, utilize o bom senso de acordo com a gravidade da situação.

    # Exemplos de padrão de punição #
    Falta ao serviço -> 6 dias de prisão
    Falta a missão -> 6 dias de detenção
    # Dados da ocorrência #
    Transgressão: {transgressao}
    Agravantes: {agravantes}
    Atenuantes: {atenuantes}
    Observação: {observacao}
    Itens em que foi enquadrado: {itens}
    # Formatação da resposta #
    Responda de acordo com o formato abaixo:
    {format_instructions}
    """

    rota_prompt_template = ChatPromptTemplate.from_messages(
        [("system", sys_prompt)],
    ).partial(format_instructions=parser.get_format_instructions())

    chain = rota_prompt_template | model | parser
    dicionario = {"transgressao": transgressao, "agravantes": agravantes, "atenuantes": atenuantes, "observacao": observacao, "itens": itens}
    resposta = chain.invoke(dicionario)
    return resposta

def analisar_e_resumir_defesa(alegacao_defesa: str):
    """
    Analisa a alegação de defesa, extrai os pontos-chave e gera um
    resumo formal e técnico para ser incluído no relatório de apuração.
    """

    sys_prompt = """
    Você é um Oficial Apurador encarregado de analisar a defesa de um militar. Sua tarefa é ler a alegação de defesa, identificar os argumentos centrais e sintetizá-los em um resumo técnico e formal para o relatório final.

    **Instruções:**
    1.  **Identifique os Argumentos Principais:** Leia a alegação de defesa e extraia os pontos essenciais. O militar nega o fato? Apresenta uma justificativa (ex: força maior, desconhecimento)? Apresenta circunstâncias atenuantes?
    2.  **Sintetize:** Crie um resumo conciso que capture a essência da defesa.
    3.  **Linguagem Formal:** Redija o resumo em linguagem formal e impessoal, adequada para um documento oficial militar.
    4.  **Limite de Palavras:** O resumo final não deve exceder 50 palavras.
    5. O resumo final deve vir em terceira pessoa e em formato que possa ser inserido logo após o texto: "aduzindo, em síntese, que "

    **Alegação de Defesa Original:**
    {alegacao_defesa}
    """

    prompt_template = ChatPromptTemplate.from_messages([
        ("system", sys_prompt)
    ])

    chain = prompt_template | model | StrOutputParser()

    resposta = chain.invoke({"alegacao_defesa": alegacao_defesa})

    return resposta

def reescrever_ocorrencia(transgressao: str):
    """
    Reescreve a descrição da transgressão de forma formal e objetiva para
    ser usada em documentos oficiais.
    """

    sys_prompt = """
    Você é um Oficial Apurador redigindo um relatório disciplinar. Sua tarefa é reescrever a descrição de uma transgressão para que ela seja formal, técnica e objetiva, adequada para um documento oficial.

    **Instruções:**
    1.  **Objetividade:** Remova qualquer linguagem informal, coloquial ou subjetiva.
    2.  **Formalidade:** Utilize terminologia militar e jurídica apropriada, como "deixou de cumprir", "agiu em desacordo com".
    3.  **Clareza e Riqueza de Detalhes:** Seja direto, claro e forneça o máximo de detalhes relevantes. O texto final não deve exceder 150 palavras.
    4.  **Foco nos Fatos:** Descreva o ato transgressor sem adjetivos ou opiniões. Mantenha o foco no que aconteceu, como aconteceu e quais foram as consequências diretas.
    5.  **Estrutura do Texto:** Comece o texto de forma que possa ser lido como uma continuação, sem introduções como "O militar..." ou "A transgressão foi...".
    6.  **Formatação:** O texto deve ser corrido, em um único parágrafo, e começar com letra minúscula para ser facilmente integrado em outros documentos.

    **Descrição Original da Transgressão:**
    {transgressao}
    """

    prompt_template = ChatPromptTemplate.from_messages([
        ("system", sys_prompt)
    ])

    chain = prompt_template | model | StrOutputParser()

    resposta = chain.invoke({"transgressao": transgressao})
    return resposta

def texto_relatorio(transgressao, justificativa):

    sys_prompt = """
    # Contexto #
    Você é um Oficial militar encarregado de fazer um relatório de apuração de transgressão disciplinar.

    # Tarefa #
    Sua tarefa é ler a alegação de defesa, identificar os argumentos centrais, confrontar os argumentos da defesa com os dados da transgressão e produzir um relatório final.

    # Instruções #
    1.  **Culpabilidade:** Considere que, se chegou a esta fase de produção do relatório, o militar já foi considerado culpado.
    2.  **Argumentação:** Cada ponto levantado pela alegação de defesa deve ser respondido informando o porque ele não procede. Leve em consideração as informações da transgressão.
    3.  **Linguagem Formal:** Redija o resumo em linguagem formal e impessoal, adequada para um documento oficial militar.
    4.  **Limite de Palavras:** O resumo final não deve exceder 75 palavras.

    # Formatação #

    Não escreva nada antes ou depois do texto do relatório. Escreva somente o texto diretamente.

    # Alegação de Defesa #
    <alegacao_defesa>
    {justificativa}
    </alegacao_defesa>

    # Transgressão #
    <transgressao>
    {transgressao}
    </transgressao>
    """

    prompt_template = ChatPromptTemplate([
        ("system", sys_prompt)
    ])

    chain = prompt_template | model | StrOutputParser()

    resposta = chain.invoke({"transgressao":transgressao, "justificativa": justificativa})

    return resposta
# def enquadra_item(transgressao):
#     class Item(BaseModel):
#         item: list = Field(description="Defina uma lista de dicionários python com a chave 'numero' e o valor sendo o número do item escolhido e a chave 'descricao' e o valor sendo a descrição do item. Cada item da lista deve ser um dicionário com um item que foi enquadrado.")

#     parser = PydanticOutputParser(pydantic_object=Item)
def personalizar_ocorrencia(transgressao_comum: str, posto: str, nome_guerra: str) -> str:
    """
    Adapta o texto da ocorrência para mencionar apenas o militar especificado,
    fazendo o mínimo de alterações possível no texto original.
    """
    sys_prompt = f"""Você é um escrivão militar. Sua tarefa é adaptar o texto abaixo para que ele se refira APENAS ao militar {posto} {nome_guerra}, fazendo o MÍNIMO de alterações possível.

REGRAS — LEIA COM ATENÇÃO:

1. CONSERVE ao máximo o texto original. Altere SOMENTE o que for estritamente necessário para remover referências a outros acusados.
2. Se o texto já menciona apenas {posto} {nome_guerra}, DEVOLVA O TEXTO SEM ALTERAR NENHUMA PALAVRA.
3. Se houver lista de acusados (ex: "S2 FULANO, CB CICLANO e S2 BELTRANO"), SUBSTITUA apenas essa lista pelo nome "{posto} {nome_guerra}" e ajuste o verbo para o singular. NÃO altere mais nada.
4. PROIBIDO corrigir erros de ortografia, pontuação ou gramática do texto original — se houver erro no original, mantenha o erro.
5. PROIBIDO remover cabeçalhos, datas, locais, referências a missões, nomes de testemunhas ou qualquer outro trecho do texto original.
6. PROIBIDO acrescentar qualquer palavra, frase, interpretação ou contexto que não esteja no texto original.
7. PROIBIDO mudar o nome "{posto} {nome_guerra}" — escreva exatamente como foi informado, sem abreviar, completar ou corrigir.
8. Retorne APENAS o texto adaptado, sem explicações, sem aspas, sem prefácio.

Texto original:
{transgressao_comum}
"""
    chain = ChatPromptTemplate.from_messages([("system", sys_prompt)]) | model | StrOutputParser()
    return chain.invoke({})


def verifica_similaridade(transgressao_nova, transgressao_antiga):

    sys_prompt = f"""Você é um especialista em análise de textos.
    Sua tarefa é verificar se dois textos diferentes estão se referindo ao mesmo fato ocorrido.
    Tenha atenção a datas, locais, pessoas envolvidas, etc.
    Textos escritos de formas diferentes podem se referir ao mesmo fato.

    Os textos são os seguintes:
    # Texto 1
    {transgressao_nova}

    # Texto 2
    {transgressao_antiga}

    # Output
    Responda somente YES ou NO. 
    **YES** caso sejam iguais e **NO** caso não sejam
    """
    parser = BooleanOutputParser()

    prompt_template = ChatPromptTemplate.from_messages(
        [("system", sys_prompt)],
    )
    chain = prompt_template | model | parser
    resposta = chain.invoke({"transgressao_nova": transgressao_nova, "transgressao_antiga": transgressao_antiga})
    return resposta