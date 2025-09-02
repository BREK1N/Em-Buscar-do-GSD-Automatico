from langchain_openai import ChatOpenAI
from dotenv import load_dotenv
from langchain.prompts import ChatPromptTemplate
from pydantic import BaseModel, Field
from langchain_core.output_parsers import PydanticOutputParser
import os

load_dotenv()

openai_api_key = os.getenv("OPENAI_API_KEY")
if not openai_api_key:
    raise ValueError("A variável OPENAI_API_KEY não foi encontrada no ficheiro .env")

model = ChatOpenAI(
    model="gpt-4o",
    temperature=0,
    api_key=openai_api_key
)

def enquadra_item(transgressao):
    class Item(BaseModel):
        item: list = Field(description="Defina uma lista de dicionários python com a chave 'numero' e o valor sendo o número do item escolhido e a chave 'descricao' e o valor sendo a descrição do item. Cada item da lista deve ser um dicionário com um item que foi enquadrado.")

    parser = PydanticOutputParser(pydantic_object=Item)

    sys_prompt = """
    Você é um especialista em enquadrar, de acordo com os itens, transgressões disciplinares.
    São transgressões disciplinares:
    1 - aproveitar-se de missões de vôo para realizar vôos de caráter não militar ou pessoal;
    2 - utilizar-se sem ordem, de aeronave militar ou civil;
    3 - transportar, na aeronave que comanda, pessoal ou material sem autorização de autoridade
    competente ;
    4 - deixar de observar as regras de tráfego aéreo;
    5 - deixar de cumprir ou alterar , sem justo motivo, as determinações constantes da ordem de
    missão, ou qualquer outra determinação escrita ou verbal;
    6 - executar vôos a baixa altura acrobáticos ou de instrução fora das áreas para tal fim estabelecidas,
    excetuando-se os autorizados por autoridade competente;
    7 - fazer, ou permitir que se faça, a escrituração do relatório de vôo com dados que não
    correspondam com a realidade;
    8 - deixar de cumprir ou fazer cumprir, quando isso lhe competir, qualquer prescrição
    regularmentar;
    9 - deixar por negligência, de cumprir ordem recebida:
    10 - deixar de comunicar ao superior a execução de ordem dele recebida:
    11 - deixar de executar serviço para qual tenha sido escalado;
    12 - deixar de participar, a tempo à autoridade a que estiver imediatamente subordinado, a
    impossibilidade de comparecer ao local de trabalho, ou a qualquer ato de serviço ou instrução a que
    deva tomar parte ou a que deva assistir;
    13 - retardar, sem justo motivo, a execução de qualquer ordem;
    14 - permutar serviço, sem a devida autorização
    15 - declarar-se doente ou simular doença para se esquivar de qualquer serviço ou instrução;
    16 - trabalhar mal, intencionalmente ou por falta de atenção em qualquer serviço ou instrução;
    17 - ausentar-se, sem licença, do local do serviço ou de outro qualquer em que deva encontra-se por
    força de disposição legal ou ordem;
    18 -faltar ou chegar atrasado, sem justo motivo, a qualquer ato, serviço ou instrução de que deva
    participar ou a que deva assistir;
    19 - abandonar o serviço para o qual tenha sido designado;
    20 - deixar de cumprir punição legalmente imposta;
    21 - dirigir-se ou referir-se a superior de modo desrespeitoso;
    22 - procurar desacreditar autoridade ou superior hierárquico, ou concorrer para isso;
    23 - censurar atos superior ;
    24 - ofender moralmente ou procurar desacreditar outra pessoa quer seja militar ou civil, ou
    concorrer para isso;
    25 - deixar o militar quer uniformizado quer trajando civilmente, de cumprimentar o superior
    quando uniformizado, ou em traje civil desde que o conheça;
    26 - deixar o militar deliberadamente, de corresponder ao cumprimento que seja dirigido;
    27 - deixar o oficial ou aspirante-a-oficial, quando no quartel, de apresentar-se ao seu Comandante
    para cumprimentá-lo de acordo com as normas de cada Organização ;
    28 - deixar , quando sentado de oferecer o lugar a superior de pé por falta de lugar, exceto em
    teatro, cinemas, restaurantes ou casas análogas, bem como em transportes pagos;
    29 - deixar o oficial ou aspirante-a-oficial quando de serviço de Oficial-de-Dia de se apresentar
    regularmente a qualquer superior que entrar em sua Organização, quando disso tenha ciência;
    30 - retirar-se da presença de superior sem a devida licença ou ordem para o fazer;
    31 - entrar em qualquer Organização Militar ou dela sair por lugar que não o para isso destinado;
    32 - entrar, ou sair o militar em Organização Militar que não a sua, sem dar ciência ao Comandante
    ou Oficial de Serviço ou o respectivos substitutos;
    33 - entrar, sem permissão, em dependência destinada a superior, ou onde este se ache, ou em outro
    local cuja entrada lhe seja normalmente vedada;
    34 - desrespeitar, por palavras ou atos, as instituições, religiões ou os costumes do país estrangeiro
    em que se achar;
    35 - desrespeitar autoridade civil;
    36 - desrespeitar medidas gerais de ordem policial, embaraçar sua execução ou para isso concorrer;
    37 - representar contra o superior, sem fundamento ou sem observar as prescrições regularmentares;
    38 - comunicar a superior hierárquico que irá representar contra o mesmo e deixar de fazê-lo;
    39 - faltar, por ação ou omissão, ao respeito devido aos Símbolos Nacionais, Estaduais, Municipais,
    de nações amigas ou de instituições militares;
    40 - tomar parte, sem autorização, em competições desportivas militares de círculos diferentes;
    41 - usar de violência desnescessária no ato de efetuar prisão;
    42 - tratar o subordinado hierárquico com injustiça, prepotência ou maus tratos;
    43 - maltratar o preso que seja sob sua guarda;
    44 - consentir que presos conservem em seu poder objetos não permitidos ou instrumentos que se
    prestem à danificação das prisões;
    45 - introduzir, distribuir ou possuir, em Organização Militar, publicações, estampas prejudiciais à
    disciplina e à moral;
    46 - frequentar lugares incompatíveis com o decoro da sociedade;
    47 - desrespeitar as convenções sociais
    48 - ofender a moral ou os bons costumes, por atos, palavras e gestos;
    49 - porta-se incovenientemente ou sem compostura;
    50 - faltar à verdade ou tentar iludir outrem;
    51 - induzir ou concorrer intencionalmente para que outrem incorra em erro;
    52 - apropria-se de quantia ou objeto pertencente a terceiro era proveito próprio ou de outrem,
    53 - concorrer para discórdia, de sarmonia ou inimizade entre colegas de corporação ou entre
    superiores hierárquicos;
    54 - utilizar-se do anonimato para qualquer fim;
    55 - estar fora do unifrome ou trazê-lo em desalinho
    56 - ser descuidado na apresentação pessoal e no asseio do corpo;
    57 - travar disputa, rixa ou luta corporal;
    58 - embriagar-se com bebida alcoólica ou similar;
    59 - fazer uso de psicotrópicos, entorpecentes ou similar;
    60 - tomar parte em jogos proibidos por lei;
    61 - assumir compromissos, prestar declarações ou divulgar informações, em nome da Corporação
    ou da Unidade em que serve, sem estar para isso autorizado;
    62 - servir-se da condição de militar ou da função que exerce para usufuir vantagens pessoais;
    63 - contrair dívidas ou assumir compromissos superiores às suas possibilidades, comprometendo o
    bom nome da classe;
    64 - esquivar-se a satisfazer compromissos de ordem moral ou pecuniária que houver assumido;
    65 - realizar ou propor empréstimo de dinheiro a outro militar, visando auferição de lucro;
    66 -deixar de cumprir ou de fazer cumprir, o previsto em Regulamentos e Atos emanados de
    autoridade competente;
    67 -representar a corporação em qualquer ato, sem estar para isso autorizado;
    68 - vagar ou passear, o cabo, soldado ou taifeiro por logradouros públicos em horas de expediente,
    sem permissão escrita da autoridade competente;
    69 - publicar, pela comentar, difundir ou apregoar notícias exageradas, tendeciosas ou falsas , de
    caráter alarmante ou não, que possam gerar o desassossego público;
    70 - publicar, pela imprensa outro meio, sem permissão da autoridade competente, documentos
    oficiais ou fornecer dados neles contidos a pessoas não autorizadas;
    71 - travar polêmica, através dos meios de comunicação sobre assunto militar ou político;
    72 - autorizar, promover, assinar representações, documentos coletivos ou publicações de qualquer
    tipo, com finalidade política, de reivindicação ou de crítica a autoridades constituídas ou às suas
    atividades;
    73 - externar-se publicamente a respeito de assuntos políticos;
    74 - provocar ou participar, em Organização Militar, de discussão sobre política ou religião que
    possa causar desassossego;
    75 - ser indiscreto em relação a assuntos de caráter oficial, cuja divulgação possa ser prejudicial à
    disciplinar ou a boa ordem do serviço;
    76 - comparecer fardado a manifestações ou reuniões de caráter político;
    77 - fumar em lugares em que seja isso vedado;
    78 - deixar, quando for o caso, de punir o subordinado hierárquico que cometer transgressão, ou
    deixar de comunicá-la à autoridade competente;
    79 - deixar de comunicar ao superior imediato, ou na ausência deste a outro, qualquer informação
    sobre iminente perturbação da ordem pública ou da boa marcha do serviço, logo que disso tenha
    conhecimento;
    80 - deixar de apresentar-se sem justo motivo, por conclusão de férias, dispensa, licença, ou
    imediatamente após tomar conhecimento que qualquer delas lhe tenha sido interrompida ou
    suspensa;
    81 - deixar de comunicar ao órgão competente de sua Organização Militar o seu endereço
    domiciliar;
    82 - deixar de ter consigo documentos de identidade que o identifiquem;
    83 - deixar de estar em dia com as inspeções de saúde obrigatórias;
    84 -deixar de identificar-se, quando solicitado por quem de direito
    85 - recusar pagamento, fardamento, alimento e equipamento ou outros artigos de recebimento
    obrigatório;
    86 - ser descuidado com objetos pertencentes à Fazenda Nacional;
    87 - dar, vender, empenhar ou trocar peças de uniforme ou equipamento fornecidos pela Fazenda
    Nacional;
    88 - extraviar ou concorrer para que se extravie ou estrague qualquer objeto da Fazenda Nacional ou
    documento oficial, sob a sua responsabilidade;
    89 - abrir, ou tentar abrir, qualquer dependência da Organização Militar, fora das horas de
    expediente, desde que não seja o respectivo chefe ou por necessidade urgente de serviço;
    90 - introduzir bebidas alcoólicas, entorpercentes ou similares em Organização Militar sem que para
    isso esteja autorizado;
    91 - introduzir material inflamável ou explosivo em Organização Militar sem ser em cumprimento
    de ordem;
    92 - introduzir armas ou instrumentos proibidos em Organização Militar, ou deles estar de posse,
    sem autorização;
    93 - conversar com sentinela, vigia, plantão ou preso incomunicável;
    94 - conversar ou fazer ruído desnecessário, por ocasião de manobra, exercício, reunião para
    qualquer serviço ou após toque de silêncio;
    95 - dar toques, fazer sinais, içar ou arriar a Bandeira Nacional ou insígnias, sem ter ordem para
    isso;
    96 - fazer, ou permitir que se faça, dentro de Organização Militar rifas, sorteios coletas de dinheiro
    etc.. sem autorização do Comandante;
    97 - ingressar, como atleta, em equipe profissional, sem autorização do Comandante;
    98 - andar a praça armada, sem ser em serviço ou ser ter para isso ordem escrita, a qual deverá ser
    exibida quando solicitada;
    99 - usar traje civil, quando as disposições em vigor não o permitirem;
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

def verifica_agravante_atenuante(historico, transgressao, justificativa, itens):

    class Item(BaseModel):
        item: list = Field(description="""Defina um dicionário python com a chave 'agravantes' e o valor sendo as letras correspondentes as situações agravantes
                            e a chave 'atenuantes' e o valor sendo as letras correspondentes as situações atenuantes
                           e a chave 'itens' e o valor sendo os itens que o militar foi enquadrado
                        """)


    parser = PydanticOutputParser(pydantic_object=Item)

    sys_prompt = """
    # Contexto #
    Você é um especialista em determinar o que são circunstâncias atenuantes e agravantes no julgamento de uma transgressão disciplinar praticada por um militar.
    Você deve avaliar com muita atenção se a justificativa apresentada realmente é válida, pois o militar tentará de qualquer formar possível ser justificado.
    # Informações #
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
    f) ocorrência de transgressão colocando em risco vidas humanas, segurança de aeronave, viaturas
    ou propriedade do Estado ou de particulares;
    g) ocorrência da transgressão em presença de subordinado, de tropa ou em público;
    h) abuso de autoridade hierárquica ou funcional;
    i) ocorrência da transgressão durante o serviço ou instrução.
    # Regras #
    1. O militar ter bom ou mal comportamento depende exclusivamente do seu histórico
    2. Se o militar for enquadrado em mais de um item ele está automaticamente enquadrado na letra c dos agravantes
    # Justificativa apresentada pelo militar #
    {justificativa}
    # Histórico do militar #
    {historico}
    # Itens em que o militar foi enquadrado durante a atual transgressão #
    {itens}

    # Formatação #
    Você deve retornar no seguinte formato:
    <formato>
    {format_instructions}
    </formato>
    # Transgressão #
    {transgressao}"""

    prompt_template = ChatPromptTemplate.from_messages(
        [("system", sys_prompt)],
    ).partial(format_instructions=parser.get_format_instructions())

    chain = prompt_template | model | parser
    resposta = chain.invoke({"transgressao": transgressao, "justificativa": justificativa, "historico": historico, "itens": itens})
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
    class AnaliseDefesa(BaseModel):
        resumo_tecnico: str = Field(
            description="Um resumo formal e técnico da alegação de defesa, com no máximo 50 palavras, adequado para um relatório disciplinar militar."
        )

    parser = PydanticOutputParser(pydantic_object=AnaliseDefesa)

    sys_prompt = """
    Você é um Oficial Apurador encarregado de analisar a defesa de um militar. Sua tarefa é ler a alegação de defesa, identificar os argumentos centrais e sintetizá-los em um resumo técnico e formal para o relatório final.

    **Instruções:**
    1.  **Identifique os Argumentos Principais:** Leia a alegação de defesa e extraia os pontos essenciais. O militar nega o fato? Apresenta uma justificativa (ex: força maior, desconhecimento)? Apresenta circunstâncias atenuantes?
    2.  **Sintetize:** Crie um resumo conciso que capture a essência da defesa.
    3.  **Linguagem Formal:** Redija o resumo em linguagem formal e impessoal, adequada para um documento oficial militar.
    4.  **Limite de Palavras:** O resumo final não deve exceder 50 palavras.

    **Alegação de Defesa Original:**
    {alegacao_defesa}

    **Formato da Resposta (apenas o JSON):**
    {format_instructions}
    """

    prompt_template = ChatPromptTemplate.from_messages([
        ("system", sys_prompt)
    ]).partial(format_instructions=parser.get_format_instructions())

    chain = prompt_template | model | parser

    resposta = chain.invoke({"alegacao_defesa": alegacao_defesa})
    return resposta.resumo_tecnico

def reescrever_ocorrencia(transgressao: str):
    """
    Reescreve a descrição da transgressão de forma formal e objetiva para
    ser usada em documentos oficiais.
    """
    class OcorrenciaFormal(BaseModel):
        texto_reescrito: str = Field(
            description="A descrição da transgressão, reescrita de forma formal, impessoal e objetiva, com no máximo 50 palavras."
        )

    parser = PydanticOutputParser(pydantic_object=OcorrenciaFormal)

    sys_prompt = """
    Você é um Oficial Apurador redigindo um relatório disciplinar. Sua tarefa é reescrever a descrição de uma transgressão para que ela seja formal, técnica e objetiva, adequada para um documento oficial.

    **Instruções:**
    1.  **Objetividade:** Remova qualquer linguagem informal, coloquial ou subjetiva.
    2.  **Formalidade:** Utilize terminologia militar e jurídica apropriada.
    3.  **Clareza e Concisão:** Seja direto e claro. O texto final não deve exceder 50 palavras.
    4.  **Foco nos Fatos:** Descreva o ato transgressor sem adjetivos ou opiniões.

    **Descrição Original da Transgressão:**
    {transgressao}

    **Formato da Resposta (apenas o JSON):**
    {format_instructions}
    """

    prompt_template = ChatPromptTemplate.from_messages([
        ("system", sys_prompt)
    ]).partial(format_instructions=parser.get_format_instructions())

    chain = prompt_template | model | parser

    resposta = chain.invoke({"transgressao": transgressao})
    return resposta.texto_reescrito