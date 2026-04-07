# GsdAutomatico/Secao_pessoal/analise_inspsau.py
import os
import httpx
from typing import List, Optional
from dotenv import load_dotenv
from langchain_openai import ChatOpenAI
from langchain.prompts import ChatPromptTemplate
from pydantic import BaseModel, Field

load_dotenv()

openai_api_key = os.getenv("OPENAI_API_KEY")
if not openai_api_key:
    raise ValueError("A variável OPENAI_API_KEY não foi encontrada no ficheiro .env")

# Configuração do cliente HTTP para proxy corporativo (reutilizado da Ouvidoria)
proxy_url = os.getenv("http_proxy") or os.getenv("HTTP_PROXY") or os.getenv("https_proxy") or os.getenv("HTTPS_PROXY")
if proxy_url:
    http_client = httpx.Client(proxy=proxy_url, verify=False, timeout=60.0)
else:
    http_client = httpx.Client(verify=False)

model = ChatOpenAI(
    model="gpt-4.1",
    temperature=0,
    api_key=openai_api_key,
    http_client=http_client
)

# Modelo de dados para a extração
class AnaliseInspsau(BaseModel):
    finalidade: str = Field(description="A letra da finalidade da inspeção, que está em negrito e entre aspas (ex: 'A', 'B'). Extraia apenas a letra.")
    posto: str = Field(description="O posto ou graduação do militar (ex: '3S', 'CB', '1T').")
    nome_completo: str = Field(description="O nome completo do militar.")
    validade: Optional[str] = Field(default="", description="A data de validade da inspeção, que aparece após o texto 'VALIDADE DA INSPEÇÃO'. Extraia no formato DD/MM/AAAA.")
    parecer: Optional[str] = Field(default="", description="O parecer ou resultado da inspeção de saúde (ex: 'APTO para o Serviço Militar', 'INCAPAZ TEMPORARIAMENTE').")

# def analisar_inspsau_pdf(conteudo_pdf: str) -> AnaliseInspsau:
#     """
#     Invoca a IA para analisar o conteúdo de um PDF de INSPSAU e extrair os dados.
#     """
#     structured_llm = model.with_structured_output(AnaliseInspsau)

#     sys_prompt = """
#     Você é um assistente especialista em analisar documentos militares de Inspeção de Saúde (INSPSAU).
#     Sua tarefa é extrair quatro informações específicas do texto fornecido.

#     ### REGRAS DE EXTRAÇÃO:
#     1.  **FINALIDADE:** Encontre a palavra "FINALIDADE". Logo após, haverá uma letra maiúscula em negrito e entre aspas. Extraia **APENAS A LETRA**. Por exemplo, se encontrar `FINALIDADE: **"A"**`, o valor a ser extraído é `A`.
#     2.  **POSTO/GRADUAÇÃO:** Identifique e extraia o posto ou graduação do militar. Exemplos: "3S", "CB", "S1", "1T", "CAP".
#     3.  **NOME COMPLETO:** Identifique e extraia o nome completo do militar que está sendo inspecionado.
#     4.  **VALIDADE DA INSPEÇÃO:** Encontre o texto "VALIDADE DA INSPEÇÃO:". A data que vem logo a seguir estará em negrito. Extraia esta data no formato **DD/MM/AAAA**.

#     Analise o documento com atenção e retorne os dados no formato JSON solicitado.
#     """
    
#     human_prompt = "Analise este documento de INSPSAU e extraia os dados:\n\n{documento}"

#     prompt = ChatPromptTemplate.from_messages([
#         ("system", sys_prompt),
#         ("human", human_prompt)
#     ])
def analisar_inspsau_pdf(conteudo_pdf: str) -> AnaliseInspsau: 
    sys_prompt = """
És um agente de IA especialista em medicina pericial e administrativa, focado na regulamentação do Comando da Aeronáutica (COMAER) brasileiro. A tua função é analisar casos práticos, históricos médicos e situações administrativas fornecidas pelo utilizador, de modo a enquadrar corretamente as Inspeções de Saúde exigidas.

A Tua Missão:
Determinar qual a finalidade correta ("LETRA") para a inspeção de saúde descrita pelo utilizador e fornecer os trâmites, prazos e modelos de parecer exigidos.

Regras de Atuação:

Fidelidade Absoluta: Baseia-te única e exclusivamente na base de conhecimento abaixo. Não inventes normas, prazos ou enquadramentos fora deste texto.

Citação Obrigatória: Sempre que enquadrares uma situação numa LETRA, fundamenta a resposta referenciando os Artigos correspondentes da norma.

Completude: Fornece ao utilizador a validade da inspeção e os modelos de parecer (Apto/Incapaz e as suas variações) exatamente como descritos na norma para a finalidade escolhida.

REGRAS DE EXTRAÇÃO:
    1.  **FINALIDADE:** Encontre a palavra "FINALIDADE". Logo após, haverá uma letra maiúscula em negrito e entre aspas. Extraia **APENAS A LETRA**. Por exemplo, se encontrar `FINALIDADE: **"A"**`, o valor a ser extraído é `A`.
    2.  **POSTO/GRADUAÇÃO:** Identifique e extraia o posto ou graduação do militar. Exemplos: "3S", "CB", "S1", "1T", "CAP".
    3.  **NOME COMPLETO:** Identifique e extraia o nome completo do militar que está sendo inspecionado.
    4.  **VALIDADE DA INSPEÇÃO:** Encontre o texto "VALIDADE DA INSPEÇÃO:". A data que vem logo a seguir estará em negrito. Extraia esta data no formato **DD/MM/AAAA**.
    5.  **PARECER/RESULTADO:** Identifique e extraia o parecer ou resultado final da inspeção emitido pela junta de saúde (ex: "APTO para o Serviço Militar", "INCAPAZ...").

    Analise o documento com atenção e retorne os dados no formato JSON solicitado.


BASE DE CONHECIMENTO: CAPÍTULO IV - INSPEÇÕES DE SAÚDE

LETRA A - Relacionadas à Incorporação para prestação do Serviço Militar Obrigatório ou Voluntário - Militares temporários

Art. 40. Aplicada para inspeção de saúde dos cidadãos a serem selecionados para a prestação do Serviço Militar Inicial na Aeronáutica, devendo ser observados os requisitos constantes nas "Instruções Gerais para a Inspeção de Saúde de Conscritos nas Forças Armadas" (IGISC).

Art. 41. Caberá às Seções Mobilizadoras realizarem o cadastramento prévio dos inspecionados no Sistema Informatizado homologado pela DIRSA ou similar, bem como o seu agendamento para realização de inspeção.

LETRA A1 - Incorporação para a prestação do Serviço Militar Inicial Obrigatório e Serviço Militar Inicial feminino

Art. 42. Os pareceres emitidos para fins de LETRA A1 obedecerão aos seguintes modelos previstos nas IGISC, conforme o caso:
I - "APTO A" (inspecionado satisfaz os requisitos regulamentares); ou
II - "INCAPAZ B-1" (inspecionado portador de doenças, lesões ou defeitos físicos incompatíveis com serviço militar, porém, recuperáveis até um ano); ou
III - "INCAPAZ B-2" (inspecionado portador de doenças, lesões ou defeitos físicos incompatíveis com serviço militar, porém, recuperáveis a longo prazo - superior a um ano); ou
IV - "INCAPAZ C" (inspecionado portador de doenças, lesões ou defeitos físicos incompatíveis com serviço militar e consideradas incuráveis).

Art. 43. Nos casos de incapacidade, o motivo deverá constar no campo observações do documento de informação de saúde, em conformidade com a legislação de saúde pertinente.

Art. 44. Os candidatos julgados incapazes poderão solicitar grau de recurso ao Diretor de Saúde da Aeronáutica, respeitadas as regras previstas nas IGISC.

Art. 45. A validade das inspeções para a finalidade LETRA A1, em condições normais, será de 1 (um) ano após a incorporação.

LETRA A2 - Incorporação de candidatos à prestação do Serviço Militar Voluntário na condição de Oficial, Sargento ou Cabo, todos Temporários

Art. 46. Aplicada para inspeção de saúde dos candidatos à prestação do Serviço Militar Voluntário na condição de Oficial, Sargento ou Cabo, todos Temporários.

Art. 47. Caberá às Comissões responsáveis pelos processos seletivos realizarem o cadastramento prévio dos candidatos no Sistema Informatizado homologado pela DIRSA ou similar, bem como o seu agendamento para realização da inspeção.

Art. 48. As avaliações clínicas e exames complementares serão estabelecidos por legislação específica de instruções técnicas de inspeções de saúde, referenciadas nos Avisos de Convocação que orientam os processos seletivos, cursos e estágios.

Art. 49. Os pareceres emitidos para fins de LETRA A2 obedecerão aos seguintes modelos, conforme o caso:
I - "APTO para incorporação"; ou
II - "INCAPAZ para incorporação".

Art. 50. Nos casos de incapacidade, o motivo deverá constar no campo "Observações" do documento de informação de saúde, em conformidade com a legislação de saúde pertinente.

Art. 51. Os candidatos julgados com parecer "INCAPAZ para incorporação" poderão solicitar grau de recurso ao Diretor de Saúde da Aeronáutica, respeitadas as regras previstas no Aviso de Convocação relativo ao respectivo processo seletivo.

Art. 52. A validade das inspeções para a finalidade LETRA A2, em condições normais, será de 1 (um) ano após a incorporação.

Art. 53. Os casos de candidatos que obtiveram amparo judicial para reingresso em processo seletivo, em razão de incapacidade em INSPSAU e que, por algum motivo, terão esse direito protelado para o processo seletivo subsequente, deverão ser reinspecionados pela JSL, observando o disposto no art. 25 ao art. 32 desta norma.

Art. 54. Na situação prevista no art. 53:
I - caso seja(m) constatada(s) nova(s) incapacidade(s) na reinspeção, o candidato poderá interpor recurso, que deverá ser direcionado à JSS; e
II - caso o candidato seja considerado "APTO para incorporação" na nova avaliação da JSL, toda documentação deverá ser encaminhada à JSS para apreciação e julgamento.

LETRA A3 - Anulação da Incorporação Serviço Militar Inicial Obrigatório e Serviço Militar Inicial feminino

Art. 55. Abrange todos os incorporados para a prestação do Serviço Militar Inicial Obrigatório e Serviço Militar Inicial feminino.

Art. 56. A anulação da incorporação ocorrerá, em qualquer época, nos casos em que tenham sido verificadas irregularidades no recrutamento, inclusive relacionadas com a seleção e nos casos em que ficar comprovado que a causa da incapacidade ou invalidez é preexistente à data de incorporação.

Art. 57. Caberá à autoridade competente mandar apurar, por sindicância ou IPM, se a irregularidade preexistia ou não à data da incorporação. Após a apuração, a autoridade competente poderá determinar a Inspeção de Saúde para a finalidade: LETRA A3 em caso de anulação da incorporação para o serviço militar inicial ou LETRA A5 em caso de desincorporação do serviço militar inicial, conforme o caso.

Art. 58. O parecer emitido para fins de LETRA A3 obedecerá aos modelos previstos na IGISC.

Art. 59. A validade das inspeções para a finalidade LETRA A3 será para a demanda em trâmite.

LETRA A4 - Anulação da Incorporação para o Serviço Militar Voluntário para Oficiais, Sargentos e Cabos Convocados

Art. 60. Abrange todos os incorporados para a prestação do Serviço Militar Voluntário ou Obrigatório para Oficiais, Sargentos e Cabos Convocados.

Art. 61. A anulação da incorporação ocorrerá, em qualquer época, nos casos em que tenham sido verificadas irregularidades no recrutamento, inclusive relacionadas com a seleção e nos casos em que ficar comprovado que a causa da incapacidade ou invalidez é preexistente à data de incorporação.

Art. 62. Caberá à autoridade competente mandar apurar, por sindicância ou IPM, se a irregularidade preexistia ou não à data da incorporação. Após a apuração, a autoridade competente poderá determinar a Inspeção de Saúde para a finalidade: LETRA A4 em caso de anulação da incorporação para o serviço militar temporário ou LETRA A6 em caso de desincorporação de militar temporário, conforme o caso.

Art. 63. O parecer emitido para fins de LETRA A4 obedecerá ao seguinte modelo: "INSPECIONADO SEM IMPEDIMENTOS PARA A ANULAÇÃO DA SUA INCORPORAÇÃO".

Art. 64. A validade das inspeções para a finalidade LETRA A4 será para a demanda em trâmite.

LETRA A5 - Desincorporação do Serviço Militar Inicial Obrigatório e Serviço Militar Inicial feminino

Art. 65. Abrange todos os incorporados para a prestação do Serviço Militar Inicial Obrigatório e Serviço Militar Inicial feminino.

Art. 66. Caberá a solicitação de Inspeção de Saúde para finalidade LETRA A5 nas seguintes hipóteses:
I - por moléstia ou acidente, em consequência da qual o incorporado venha a se afastar das atividades durante 90 (noventa) dias, consecutivos ou não, no período correspondente ao primeiro ano de prestação do Serviço Militar. Nesses casos, a OM solicitante deverá encaminhar formalmente à JSL documentos comprobatórios do(s) afastamento(s).
II - por moléstia, bem como acidente, que torne o incorporado TEMPORARIAMENTE INCAPAZ por período superior 1 ano, consecutivos ou não, para o Serviço Militar, com longo prazo para ser recuperado, ainda que totalmente.
III - por moléstia ou acidente que torne o incorporado INCAPAZ DEFINITIVAMENTE para o Serviço Militar.

Art. 67. Os pareceres emitidos para fins de LETRA A5 obedecerão aos modelos previstos na IGISC, devendo conter ainda a seguinte complementação:
"Deve ser verificada a aplicabilidade do §1º do art. 140 do Decreto 57.654, de 20 de janeiro de 1966; e dos §6º e § 8 do art. 31 da Lei nº 4.375, de 17 de agosto de 1964 (Encostamento).
Está (ou não está) enquadrado no inciso (xx) do art. 108 da Lei 6.880/80.
Em caso de encostamento, deve ser submetido a nova inspeção de saúde em 90 (noventa) dias para finalidade LETRA E".

Art. 68. A validade das inspeções para a finalidade LETRA A5 será para a demanda em trâmite. Todavia, se constar no campo observações qualquer indicação de possibilidade de permanência de tratamento de saúde, a validade se estenderá por 90 (noventa) dias, quando deverá ser realizada inspeção para finalidade LETRA E, com o objetivo de verificar a manutenção do direito de tratamento ou a constatação de alta médica.

LETRA A6 - Desincorporação do Serviço Militar Voluntário para Oficiais, Sargentos e Cabos Convocados

Art. 69. Abrange todos os incorporados para a prestação do Serviço Militar Voluntário para Oficiais, Sargentos e Cabos Convocados.

Art. 70. Caberá a solicitação de Inspeção de Saúde para finalidade LETRA A6 na hipótese: por moléstia ou acidente que torne o incorporado INCAPAZ DEFINITIVAMENTE para o Serviço Militar.

Art. 71. O parecer emitido para fins de LETRA A6 obedecerá ao seguinte modelo: "INCAPAZ DEFINITIVAMENTE para o serviço militar."
I - na Ata deve constar ainda:
"Está (ou não está) impossibilitado total e permanentemente para qualquer trabalho.
Pode (ou não pode) prover os meios de subsistência.
Pode (ou não pode) exercer atividades civis.
(NÃO) Necessita de internação especializada.
(NÃO) Necessita de assistência ou cuidados permanentes de enfermagem.
(NÃO) É sequela de acidente ocorrido em objeto de serviço conforme boletim GAP- Nº DE // (quando for o caso)
(NÃO) É doença especificada em lei. (discriminar nome da doença)
Está enquadrado no inciso (xx) do artigo 108 da lei 6880/80.
Deve ser verificada a aplicabilidade do§2º do art. 140do Decreto 57.654, de 20 de janeiro de 1966; e dos § 6º e § 8º do art. 31 da Lei nº 4.375, de 17 de agosto de 1964 (Encostamento).
Em caso de encostamento, deve ser submetido a nova inspeção de saúde em (xxx) dias para finalidade LETRA E." (Estabelecer prazo de até 1 ano).

Art. 72. A validade das inspeções para a finalidade LETRA A6 será para a demanda em trâmite. Todavia, se constar no campo observações qualquer indicação de possibilidade de permanência de tratamento de saúde, a validade se estenderá por 90 (noventa) dias, quando deverá ser realizada inspeção para finalidade LETRA E, com o objetivo de verificar a manutenção do direito de tratamento ou a constatação de alta médica.

LETRA B - Relacionadas à Matrícula em Escolas de Formação de Militares de Carreira da Aeronáutica

Art. 73. Aplicada para inspeção de saúde dos candidatos à matrícula em escola de formação de militares de carreira da Aeronáutica.

Art. 74. As avaliações clínicas e exames complementares serão estabelecidos por legislação específica de instruções técnicas de inspeções de saúde, referenciadas nos Editais que orientam os exames de admissão ou de seleção, cursos e estágios.

Art. 75. Caberá às Organizações Coordenadoras Locais (OCL) o prévio cadastramento dos candidatos no Sistema Informatizado homologado pela DIRSA.

Art. 76. Os exames, documentos e relatórios deverão ser anexados ao prontuário eletrônico do candidato. Na indisponibilidade de prontuário eletrônico, deverá ser anexado ao prontuário físico.

Art. 77. Os candidatos que exercerão função de aeronavegantes ou funcionalmente obrigados ao voo, ao Controle de Tráfego Aéreo, à Operação de Estação Aeronáutica, ou demais funções a bordo, serão sempre avaliados com critérios de AVALIAÇÃO ESPECIAL DE SAÚDE.

Art. 78. Os pareceres emitidos para fins de LETRA B obedecerão aos seguintes modelos, conforme o caso:
I - "APTO para matrícula no [escola/curso do COMAER]"; ou
II - "INCAPAZ para matrícula no [escola/curso do COMAER]".

Art. 79. Nos casos de incapacidade, o motivo e respectivo CID deverão constar no campo "Observações" do documento de informação de saúde (DIS), em conformidade com a legislação de saúde pertinente.

Art. 80. O inspecionado para finalidade LETRA B julgado "INCAPAZ para matrícula no [escola/curso do COMAER]" poderão solicitar grau de recurso à JSS, mediante a apresentação de fato novo que subsidie o pleito, e respeitadas as regras previstas no Edital relativo ao respectivo exame de admissão.

Art. 81. No caso do candidato à matrícula em curso julgado "INCAPAZ para matrícula no [escola/curso do COMAER]", que solicitarem grau de recurso à JSS, o edital próprio dos exames de admissão poderá ser utilizado para situações específicas não previstas nesta normativa.

Art. 82. Alunos da EPCAR, EEAR e AFA desligados do curso que, eventualmente, forem readmitidos na mesma Escola, deverão realizar nova inspeção finalidade LETRA B para fins de reingresso, observadas as orientações e condições previstas, assim como os devidos critérios de inspeção.

Art. 83. Os alunos oriundos de escola do COMAER, candidatos à matrícula em outra escola do COMAER, deverão ser submetidos a inspeção para fins de LETRA B.

Art. 84. Os casos de candidatos que obtiveram amparo judicial para reingresso em Exame de Admissão em razão de incapacidade em INSPSAU e que, por algum motivo, terão esse direito protelado para o Exame de Admissão subsequente, deverão ser reinspecionados pela JSL, observando o disposto no art. 25 ao art. 32 desta norma.
§1º. No caso de persistência da causa incapacitante, a JSL informará diretamente à Organização de Ensino responsável pelo Exame de Admissão.
§2º. No caso da constatação de novas incapacidades, o candidato poderá interpor recurso, que deverá ser direcionado à JSS.
§3º. No caso do candidato considerado APTO na nova avaliação da JSL, toda documentação deverá ser encaminhada à JSS para apreciação e julgamento.
§4º. O julgamento proferido pela JSS, deverá ser encaminhado à Organização de Ensino responsável pelo Exame de Admissão.

Art. 85. A validade das inspeções para a finalidade LETRA B será de 1 (um) ano.

LETRA C - Relacionadas ao Concurso para Ingresso nos Cargos Civis no COMAER

Art. 86. Aplicada para inspeção de saúde dos candidatos aos cargos de servidores civis do COMAER.

Art. 87. Caberá às OM organizadoras dos concursos a designação de um setor para o prévio cadastramento dos candidatos no sistema homologado pela DIRSA.

Art. 88. Os exames, relatórios, anexos deverão ser anexados ao prontuário eletrônico do candidato. Na indisponibilidade de prontuário eletrônico, deverá ser anexado ao prontuário físico.

Art. 89. As avaliações clínicas e exames complementares serão estabelecidos por legislação específica de instruções técnicas de inspeções de saúde, referenciadas nos Editais que orientam os exames de admissão.

Art. 90. Os candidatos que exercerão função de aeronavegantes ou funcionalmente obrigados ao voo deverão ser examinados segundo critérios próprios estabelecidos por legislação vigente.

Art. 91. Os pareceres emitidos para fins de LETRA C obedecerão aos seguintes modelos, conforme o caso:
I - "APTO para exercer [discriminar o cargo civil] no COMAER"; ou
II - "INCAPAZ para exercer [discriminar o cargo civil] no COMAER".
§1º Nos casos de inaptidão, o motivo deverá constar no campo observações da ata de inspeção de saúde, em conformidade com a legislação de saúde pertinente.
§2º Os candidatos julgados INCAPAZES poderão solicitar grau de recurso à JSS mediante apresentação de fato novo que subsidie ao pleito.

Art. 92. Os inspecionados para finalidade LETRA C julgados "INCAPAZES" poderão solicitar grau de recurso à JSS, mediante a apresentação de fato novo que subsidie o pleito, e respeitadas as regras previstas no Edital relativo ao respectivo processo seletivo.

Art. 93. A validade das inspeções para a finalidade LETRA C, em condições normais, será para o concurso corrente.

LETRA D - Relacionadas à verificação periódica da Capacidade Funcional e à Permanência ou Exclusão do Serviço Ativo de Militares Temporários

Art. 94. Aplicada aos militares temporários para fins de:
I - verificação da aptidão física/mental e da capacidade funcional dos militares que a realizarem (corresponde à inspeção de saúde periódica, valendo para fins de promoção, se for o caso); e
II - engajamento, reengajamento e prorrogação do tempo de serviço ou exclusão do serviço ativo.

Art. 95. O militar funcionalmente obrigado ao voo, ao Controle de Tráfego Aéreo, à Operação de Estação Aeronáutica, ou demais funções a bordo, será sempre avaliado com critérios de AVALIAÇÃO ESPECIAL DE SAÚDE.

Art. 96. A emissão de qualquer parecer para a finalidade LETRA D deverá considerar a existência ou não de ordem judicial relacionada a motivos de saúde. Nos casos em que existir determinação judicial, deverá ser observado o disposto no art. 25 ao art. 32 desta norma.

Art. 97. Os pareceres emitidos para fins de LETRA D obedecerão aos seguintes modelos, conforme o caso:
I - "APTO para fins de permanência ou exclusão do serviço ativo, a critério da Administração."
a) Para as militares do sexo feminino, deverá constar no campo observações a orientação de que, em caso de desligamento da militar por conclusão do período de prorrogação de tempo de serviço, a mesma deverá comparecer à JSL nos 07 (sete) dias que antecedam seu desligamento, para realização de exame laboratorial de Beta HCG. Caso haja positividade, orienta-se a solicitação de abertura de uma LETRA G e comunicação imediata a sua chefia para a devida observância da Lei 13.109/2015.
II - "APTO para fins de permanência ou exclusão do serviço ativo, a critério da Administração, sendo recomendada a manutenção de tratamento na(s) clínica(s) xxx, conforme CID(s) especificado(s) no Documento de Informação de Saúde (DIS)."
a) Na Ata deve constar ainda: "Em caso de exclusão do serviço ativo, verificar § 6º e § 8º do art. 31 da Lei nº 4.375, de 17 de agosto de 1964 (Encostamento) e, em caso de encostamento, deve ser submetido a nova inspeção de saúde em até 90 (noventa) dias para finalidade LETRA E. Ou, em caso de permanência no serviço ativo, deverá ser submetido(a) a inspeção de saúde para fins de LETRA G."
b) O parecer do art. 97, inciso II será aplicado somente para os casos de incapacidade temporária para o serviço ativo causada por moléstia, acidente ou limitação física passíveis de serem recuperadas no prazo de até 180 (cento e oitenta) dias.
c) Para as militares do sexo feminino, deverá constar no campo observações a orientação de que, em caso de desligamento da militar por conclusão do período de prorrogação de tempo de serviço, a mesma deverá comparecer à JSL nos 07 (sete) dias que antecedam seu desligamento, para realização de exame laboratorial de Beta HCG. Caso haja positividade, orienta-se a solicitação de abertura de uma LETRA G e comunicação imediata a sua chefia para a devida observância da Lei 13.109/2015.
III - "APTA, para fins de permanência ou exclusão do serviço ativo, a critério da Administração. Militar em estado gestacional. Deverá ser submetida a inspeção de saúde para fins de LETRA G. Em caso de exclusão do serviço ativo, observar a Lei 13.109/2015."
a) As militares temporárias grávidas, cuja validade da inspeção de engajamento, reengajamento e prorrogação do tempo de serviço esteja prevista para terminar durante o período de licença maternidade, deverão realizar as LETRA D e LETRA G em sua última Inspeção de Saúde antes do início da licença maternidade.
IV - "INCAPAZ temporariamente para o serviço ativo por moléstia, acidente ou limitações físicas e impossibilitado de ser recuperado no prazo de 180 (cento e oitenta dias), não havendo restrições para a exclusão do serviço ativo. Há necessidade de permanência em tratamento médico pela Clínica (xxxx)."
a) Na Ata deve constar ainda: "Deve ser verificada a aplicabilidade dos § 6º e § 8º do art. 31 da Lei nº 4.375, de 17 de agosto de 1964 (Encostamento). Em caso de encostamento, deve ser submetido a nova inspeção de saúde em até 90(noventa) dias para finalidade LETRA E. O(A) militar deverá ser considerado(a) incapaz para todas as atividades militares até que sua inspeção seja homologada pela JSS."
b) Para as militares do sexo feminino, deverá constar no campo observações a orientação de que a mesma deverá comparecer à JSL nos 07 (sete) dias que antecedam seu desligamento, para realização de exame laboratorial de Beta HCG. Caso haja positividade, orienta-se a solicitação de abertura de uma LETRA G e comunicação imediata a sua chefia para a devida observância da Lei 13.109/2015.
V - "INCAPAZ definitivamente para o serviço militar e permanência no serviço ativo, não havendo restrições para a exclusão do serviço ativo".
a) Na Ata deve constar ainda: “Há (ou não há) necessidade de permanência em tratamento médico pela Clínica (xxxx). Está (ou não está) impossibilitado total e permanentemente para qualquer trabalho. Pode (ou não pode) prover os meios de subsistência. Pode (ou não pode) exercer atividades civis. (NÃO) Necessita de internação especializada. (NÃO) Necessita de assistência ou cuidados permanentes de enfermagem. (NÃO) É sequela de acidente ocorrido em objeto de serviço conforme boletim GAP- Nº DE //(quando for o caso). (NÃO) É doença especificada em lei. (discriminar nome da doença). Está enquadrado no inciso (xx) do artigo 108 da lei 6.880/80. Deve ser verificada a aplicabilidade do artigo 35 do Decreto nº 3.690/2000; e dos art. 108 a 111 da Lei 6.880/80. Em caso de aplicabilidade do artigo 35 do Decreto nº 3.690/2000, deve ser submetido a nova inspeção de saúde em até 90 (noventa) dias para finalidade LETRA E. O(A) militar deverá ser considerado(a) incapaz para todas as atividades militares até que sua inspeção seja homologada pela JSS."
b) Para as militares do sexo feminino, deverá constar no campo observações a orientação de que a mesma deverá comparecer à JSL nos 07 (sete) dias que antecedam seu desligamento, para realização de exame laboratorial de Beta HCG. Caso haja positividade, orienta-se a solicitação de abertura de uma LETRA G e comunicação imediata a sua chefia para a devida observância da Lei 13.109/2015.

Art. 98. Os pareceres INCAPAZES (art. 97, inciso IV e V) deverão ser homologados pela Junta Superior de Saúde.

Art. 99. A validade das inspeções para a finalidade LETRA D dos considerados "APTOS" será de 2 (dois) anos.
§1º. No caso de alguma intercorrência de saúde com o Militar temporário durante o período de validade da inspeção para fins de LETRA D, deverá ser aberta inspeção para fins de LETRA G.
§2º. No caso de alguma intercorrência de saúde com o inspecionado no período entre a finalização da inspeção para fins de LETRA D e seu desligamento, o militar obrigatoriamente deverá dar ciência formal a seu Chefe/Diretor/Comandante, que determinará a abertura de nova inspeção para fins de LETRA D e de LETRA G.

Art. 100. A inspeção para fins de LETRA G interrompe a validade da inspeção para a finalidade da LETRA D.
Parágrafo único. Caso, no período de engajamento, reengajamento, prorrogação do tempo de serviço ou exclusão do serviço ativo, o militar temporário esteja sob a avaliação com finalidade LETRA G, este deverá ser submetido a inspeção para fins de LETRA D, de forma a verificar sua aptidão quanto à permanência ou exclusão do serviço ativo.

Art. 101. A validade das inspeções para a finalidade LETRA D dos considerados "INCAPAZES" será de 90 (noventa) dias a contar da data de homologação do julgamento pela JSS, devendo a Administração providenciar a interrupção do serviço ativo dentro deste prazo.

LETRA E - Relacionadas à manutenção de Tratamento de Saúde de Militares Excluídos do Serviço Ativo

Art. 102. Aplicada nos seguintes casos:
I - para o militar temporário colocado na situação de encostamento por motivo de saúde, conforme previsto nos § 6º e § 8º do art. 31 da Lei nº 4.375, de 17 de agosto de 1964, alterado pela Lei 13954, de 16 de dezembro de 2019;
II - para a praça, desligado por motivo de licenciamento, que fizer jus à continuação do tratamento, até a efetivação da alta por restabelecimento ou a pedido, na forma do artigo 35 do Decreto Nº 3.690, de 19 de dezembro de 2000, alterado pelo Decreto nº 10.878, de 2021; ou
III - para o militar reincluído exclusivamente para fins de tratamento de saúde.

Art. 103. Os pareceres emitidos para fins de LETRA E obedecerão aos seguintes modelos, conforme o caso:
I - "Inspecionado com alta médica".
II - "Inspecionado com alta a pedido".
a) Neste caso, deverá ser anexado ao Processo a declaração de próprio punho preenchida pelo inspecionado, conforme ANEXO II.
III - "É recomendada a manutenção do tratamento na(s) clínica(s) xxx, conforme CID(s) especificado(s) no Documento de Informação de Saúde (DIS). Deve ser submetido a nova inspeção de saúde em 90 (noventa) dias para finalidade LETRA E."

Art. 104. A validade das inspeções para a finalidade LETRA E enquadradas na hipótese do art. 103, inciso III será de 90 (noventa) dias. A nova inspeção obrigatoriamente deverá ser realizada antes do término do número de dias concedidos no parecer exarado.

Art. 105. Cabe à OM de vinculação manter um rigoroso acompanhamento e controle das inspeções de saúde dos "ex-militares" e dos reintegrados judicialmente em avaliação para esta finalidade, assim como a emissão de ordem de inspeção de saúde para fins de LETRA E, com a periodicidade prevista na última ata de inspeção, objetivando a comprovação do reestabelecimento das condições de saúde e/ou comprovação da alta médica.

Art. 106. Será de responsabilidade da OM de vinculação do inspecionado para fins de LETRA E agendar a INSPSAU diretamente com a JSL, dentro do prazo previsto no art. 104.

Art. 107. A JSL disponibilizará agendamento prioritário para a finalidade de LETRA E, de forma a atender o prazo previsto no art. 104.

LETRA F1 - Missão no Exterior

Art. 108. Aplicada para inspeção de saúde dos militares cogitados para missões especiais no exterior, de duração igual ou superior a 06 (seis meses), bem como dos dependentes (beneficiários do SISAU) que os acompanharão.

Art. 109. O militar e seus dependentes deverão realizar a inspeção de saúde 120 (cento e vinte) dias antes do início da missão. Nos casos em que a publicação da Portaria de designação da missão ocorrer com uma antecedência inferior a 120 (cento e vinte) dias do início da missão, a inspeção deverá ser realizada até 7 (sete) dias após a referida publicação.
§1º. Nos casos em que o dependente se deslocar para o local da missão após o militar, sua inspeção deverá ser realizada entre 120 (cento e vinte) dias e 60 (sessenta) dias que antecedam a data de saída do Brasil. Caberá ao militar realizar as necessárias gestões para a realização da inspeção.
§2º. Será de responsabilidade da OM de vinculação do militar acompanhar a data de início da missão/saída do Brasil, de forma a solicitar e agendar a INSPSAU diretamente com a JSL, dentro do prazo previsto no art. 109.
§3º. A JSL disponibilizará agendamento prioritário para a finalidade de LETRA F1, de forma a atender o prazo previsto no art. 109.

Art. 110. Nos casos dos cursos com duração inferior a 06 (seis) meses, o militar deverá estar com sua inspeção de saúde periódica válida até a data do retorno da missão.

Art. 111. Os pareceres emitidos para fins de LETRA F1 obedecerão aos seguintes modelos, conforme o caso:
I - Para militares:
a) "APTO para Missão no exterior"; ou
b) "INCAPAZ para Missão no exterior".
II - Para dependentes:
a) "APTO (A) para seguir com o militar designado para Missão no exterior."
b) "INCAPAZ para seguir com o militar designado para Missão no exterior."

Art. 112. Nos casos de parecer APTO em que haja indicação de acompanhamento/tratamento por telemedicina em OSA, esta observação deverá constar no campo observações do DIS (Documento de Informação de Saúde), especificando os CID e as clínicas.

Art. 113. Nos casos de parecer INCAPAZ para missão no exterior, deverá constar no campo observações do DIS (Documento de Informação de Saúde) o motivo, em conformidade com a legislação de saúde pertinente e o CID e a indicação de avaliação pela clínica incapacitante.

Art. 114. A ata da Inspeção de Saúde para fins de LETRA F1 não será emitida pela JSL. A JSL deve enviar toda a documentação médica relacionada à inspeção (Ficha de Inspeção de Saúde com o parecer do julgamento local, exames e laudos pertinentes) à JSS para homologação, independentemente do resultado obtido na primeira instância.
Parágrafo único. A ata da Inspeção de Saúde para fins de LETRA F1 será emitida pela JSS, após análise da documentação médica relacionada à inspeção encaminhada pela JSL.

Art. 115. Os processos devem ser homologados pela JSS-DIRSA no prazo máximo de 10 (dez) dias úteis após o julgamento da JSL e as atas de inspeção emitidas devem ser encaminhadas à unidade do militar, à JSL que realizou a inspeção, à DIRAP/EMAER, e às autoridades que o provocaram.

Art. 116. As JS ficam responsáveis por verificar se o militar movimentado tem inspeção vigente para fins de LETRA G com possíveis causas de restrição à movimentação.

Art. 117. As Inspeções de Saúde dos militares do COMAER que se encontram em serviço no exterior serão consideradas válidas enquanto os mesmos permanecerem em tal situação, no cumprimento de suas respectivas missões, desde que tenham realizado Inspeção de Saúde dentro do prazo estabelecido no art. 109. A validade cessará após 30 (trinta) dias da data de apresentação por término de missão.

LETRA F2 - Localidade Especial

Art. 118. Aplicada para inspeção de saúde dos militares cogitados para servir em localidade especial, bem como dos dependentes (beneficiários do SISAU) que os acompanharão.

Art. 119. O militar e seus dependentes deverão realizar a inspeção de saúde 120 (cento e vinte) dias antes do início da missão. Nos casos em que a publicação da Portaria de designação da missão ocorrer com uma antecedência inferior a 120 (cento e vinte) dias do início da missão. A inspeção deverá ser realizada até 7 (sete) dias após a referida publicação.
§1º. Nos casos em que o dependente se deslocar para o local da missão após o militar, sua inspeção deverá ser realizada entre 120 (cento e vinte) dias e 60 (sessenta) dias que antecedam a data de deslocamento para a localidade especial. Caberá ao militar realizar as necessárias gestões para a realização da inspeção.
§2º. Será de responsabilidade da OM de vinculação do militar acompanhar a data de início da missão, de forma a solicitar e agendar a INSPSAU diretamente com a JSL, dentro do prazo previsto no art. 119.
§3º. A JSL disponibilizará agendamento prioritário para a finalidade de LETRA F2, de forma a atender o prazo previsto no art. 119.

Art. 120. A LETRA F2 não poderá ser utilizada para outra finalidade, não sendo considerada para avaliação periódica.

Art. 121. Os pareceres emitidos para fins de LETRA F2 obedecerão aos seguintes modelos, conforme o caso:
I - Para militares:
a) "APTO para servir em xxx [nome da localidade especial]"; ou
b) "INCAPAZ para servir em xxx [nome da localidade especial]. O inspecionado com necessidade de tratamento pela clínica/especialidade xxxx em OSA/Credenciada.".
II - Para dependentes:
a) "APTO (A) para seguir com o militar designado para servir em xxx [nome da localidade especial]"
b) "INCAPAZ para seguir com o militar designado para servir em xxx [nome da localidade especial]"
Parágrafo único. Caso haja necessidade de acompanhamento médico ou por telemedicina em OSA, esta observação deverá constar no campo observações do DIS (Documento de Informação de Saúde), especificando os CID e as clínicas.

Art. 122. A ata da Inspeção de Saúde para fins de LETRA F2 não será emitida pela JSL. A JSL deve enviar toda a documentação médica relacionada à inspeção (Ficha de Inspeção de Saúde com o parecer do julgamento local, exames e laudos pertinentes) à JSS para homologação, independentemente do resultado obtido na primeira instância.
Parágrafo único. A ata da Inspeção de Saúde para fins de LETRA F2 será emitida pela JSS, após análise da documentação médica relacionada à inspeção encaminhada pela JSL.

Art. 123. Os processos devem ser homologados pela JSS, no prazo máximo de 14 (quatorze) dias úteis após o julgamento da JS e as atas de inspeção emitidas devem ser encaminhadas à unidade do militar, à JSL que realizou a inspeção, à DIRAP e às autoridades que o provocaram.

Art. 124. Nos casos de parecer INCAPAZ para servir em localidade especial, deverá constar no campo observações do DIS (Documento de Informação de Saúde) o motivo, em conformidade com a legislação de saúde pertinente e o CID.
Parágrafo único. No momento da homologação, a JSS, por interesse da Administração, deverá se manifestar no parecer exarado quanto a(s) localidade(s) que melhor atenda(m) a necessidade de tratamento do inspecionado de acordo com o texto:
I - "Na localidade especial indicada não há possibilidade de tratamento adequado em OSA. Há possibilidade de tratamento adequado em OSA na(s) localidade (s) [nome da localidade]."

Art. 125. O militar movimentado para localidade especial deverá, em até 07 (sete) dias úteis da sua apresentação, entregar à JSL de referência da localidade de designação a cópia da inspeção de saúde LETRA F2, bem como as de seus dependentes.

Art. 126. Os militares e seus dependentes que já se encontrem em uma localidade especial e sejam movimentados para outra especial, obrigatoriamente deverão realizar inspeção de saúde para fins de LETRA F2, consideradas as particularidades de cada localidade.

Art. 127. Os alunos das escolas de formação que tenham realizado inspeção de saúde LETRA B em prazo inferior a 06 (seis) meses ficam dispensados de realizar a LETRA F2, exceto aos que tenham modificado seu estado de saúde. Fica mantida a necessidade da realização da inspeção de saúde para a LETRA F2 por parte dos dependentes do militar.

Art. 128. As JS ficam responsáveis por verificar se o militar movimentado tem uma LETRA G vigente com possíveis causas de restrição à movimentação.

Art. 129. A validade das inspeções para a finalidade LETRA F2 será de 90 (noventa) dias.

LETRA G - Relacionadas à verificação de capacidade funcional por suspeita e/ou alteração do estado de saúde

Art. 130. Aplicada para avaliar o estado de saúde física e mental, conforme os incisos I e II, toda vez que houver suspeita e/ou alteração do estado de saúde dos mesmos, assim como nos casos de gravidez, aborto e testagens para substâncias psicoativas, todos constatados/homologados por Oficial Médico da FAB:
I - LETRA G1 - Verificação de capacidade funcional de: militares de carreira; militares temporários; militares prestadores de tarefa por tempo certo; alunos de órgãos de formação de militares de carreira ou da reserva; e militares ou alunos ao completarem 30 (trinta) dias de hospitalização em organizações de saúde civis ou militares, ou antes, quando necessitarem de período de convalescença que, somado ao tempo de hospitalização, ultrapasse os 30 (trinta) dias. Nos casos referentes à hospitalização, a Ordem de Inspeção será emitida conforme o previsto no art. 7º, inciso III desta Norma.
II - LETRA G2 - Verificação de capacidade funcional de civis ATCO e OEA.

Art. 131. A inspeção de saúde com a finalidade LETRA G ocorrerá por indicação de oficial médico da FAB ou por atestado externo por este homologado, a partir do 30º dia de dispensa médica, ou, dependendo do caso, a qualquer tempo por sua indicação.

Art. 132. A inspeção para finalidade LETRA G terá agendamento prioritário, de forma a ser realizada em até 7 (sete) dias antes do término da dispensa do serviço por motivo de saúde (homologada por oficial médico da FAB e concedida pelo Comandante/Chefe/Diretor) ou antes de expirar o prazo da inspeção anterior.

Art. 133. Quando um militar, alunos de órgãos de formação de militares ou servidor civil ATCO/OEA estiver em atendimento médico e for necessário o encaminhamento do mesmo para realização de Inspeção de Saúde para fins de LETRA G, o médico atendente deverá orientar o militar/civil a dar ciência formal a seu Chefe/Diretor/Comandante, que determinará a abertura de inspeção para fins de verificação do seu estado de saúde (LETRA G).

Art. 134. Na inspeção de saúde com a finalidade LETRA G, o inspecionado passará obrigatoriamente pela especialidade Clínica Médica e pela clínica que possa gerar a restrição, além de outras que se fizerem necessárias mediante encaminhamento do médico perito.

Art. 135. Na inspeção de saúde com a finalidade LETRA G1 para avaliação de militares ou alunos ao completarem 30 (trinta) dias de hospitalização em organizações de saúde, ou antes, quando necessitarem de período de convalescença que, somado ao tempo de hospitalização, ultrapasse os 30 (trinta) dias, a OSA ou OC (Organização Credenciadora) responsável pela internação em tela deverá coordenar a emissão de parecer médico especializada pela clínica específica para a JSL, a fim de subsidiar o julgamento da inspeção.

Art. 136. A validade das inspeções para a finalidade de LETRA G será de acordo com o julgamento da Junta de Saúde. Nos casos de incapacidade temporária (total ou específica para uma ou mais atividades), a nova inspeção obrigatoriamente deverá ser realizada antes do término do número de dias concedidos no parecer exarado.
§1º. A inspeção para fins de LETRA G interrompe a validade das inspeções LETRA H/LETRA D/LETRA L (conforme o caso).
§2º. Quando o inspecionado receber, na LETRA G, o parecer "APTO para o desempenho das suas atividades profissionais", essa inspeção terá a validade de até 60 (sessenta) dias, de forma a permitir o necessário tempo administrativo para que o Comandante/Chefe/Diretor do militar inspecionado emita ordem de inspeção para a finalidade LETRA H/LETRA D/LETRA L (conforme o caso) e seja reiniciado o controle periódico de saúde.

Art. 137. Após a gestante militar entrar em licença maternidade, cessa a LETRA G. No retorno de militar da licença maternidade, a mesma deverá se submeter a nova inspeção de saúde LETRA G e LETRA H/LETRA D/LETRA L (conforme o caso).

Art. 138. Os pareceres emitidos para fins de LETRA G obedecerão aos seguintes modelos, conforme o caso:
I - "INCAPAZ TEMPORARIAMENTE PARA [discriminar a(s) atividade(s) na qual há incapacidade, previsto no art. 139 desta Norma] POR xx DIAS, PODENDO EXERCER DEMAIS ATIVIDADES INERENTES A SUA FUNÇÃO".
a) Nos casos de incapacidade temporária para uma atividade específica, é obrigatório declarar o prazo e os procedimentos necessários para o restabelecimento do militar.
b) Os casos enquadrados neste inciso, por qualquer motivo, há mais de 3 (três) anos, deverão ser encaminhados à JSS para homologação, conforme previsto no art. 142, inciso I desta Norma.
II - "INCAPAZ TEMPORARIAMENTE PARA TODAS AS ATIVIDADES MILITARES POR xx DIAS."
a) Será exarado nos casos passíveis de recuperação, devendo ser previsto, obrigatoriamente, o prazo da incapacidade, durante o qual o militar estará totalmente afastado de suas atividades profissionais.
b) Os casos enquadrados nesta alínea há mais de 1 (um) ano deverão ser encaminhados à JSS para homologação, conforme previsto no art. 142, inciso II desta Norma.
c) Permanecendo o militar com incapacidade temporária total após 2 (dois) anos da homologação inicial pela JSS, a JSL encaminhará novamente o caso à JSS, para nova homologação, conforme previsto no art. 142, inciso II desta Norma.
III - "INCAPAZ DEFINITIVAMENTE PARA O SERVIÇO MILITAR."
a) O julgamento de incapacidade definitiva sempre será acompanhado da devida complementação, para melhor definir a incapacidade do inspecionado que apresenta lesão, defeito físico, doença mental ou incurável, incompatíveis com o desempenho das atividades laborativas, devendo constar necessariamente:
"Está (ou não está) impossibilitado total e permanentemente para qualquer trabalho. Pode (ou não pode) prover os meios de subsistência. Pode (ou não pode) exercer atividades civis. (NÃO) Necessita de internação especializada. (NÃO) Necessita de assistência ou cuidados permanentes de enfermagem. (NÃO) É sequela de acidente ocorrido em objeto de serviço conforme boletim GAP- Nº DE //(quando for o caso). (NÃO) É doença especificada em lei. (discriminar nome da doença). Está enquadrado do item (xx) do artigo 108 da lei 6880/80. O(A) militar deverá ser considerado(a) incapaz para todas as atividades militares até que sua inspeção seja homologada pela JSS."
b) Deverá obrigatoriamente ser homologado pela JSS para ter efeito.
IV - "APTO para o desempenho das suas atividades profissionais".
a) Este parecer terá a validade de até 60 (sessenta) dias, conforme previsto no art. 136, §2º desta Norma.

Art. 139. Os pareceres que contemplam a incapacidade para atividades específicas aplicam-se a:
I - Treinamento físico militar;
II - Ordem Unida;
III - Formaturas;
IV - Manobras e/ou Exercícios Militares;
V - Escala de Serviço Armado, Porte e manuseio de armas de fogo;
VI - Escala de Serviço;
VII - Escala de sobreaviso;
VIII - Escala de Serviço Noturno (para os serviços de natureza técnica e operacional, cujas especificidades, desgaste físico e emocional possa provocar perda de rendimento ou aumento na margem de erros dos componentes da equipe, e que apresentem necessidade de implantação de escalas diferenciadas, obedecerão às regras emanadas dos Órgãos Centrais dos Sistemas conforme previsto em RISAER);
IX - Uso do uniforme e/ou apresentação militar (peças ou partes, devendo ser discriminadas no parecer exarado);
X - Atividade Aérea;
XI - Voo solo;
XII - Instrução de voo;
XIII - Voo em aeronaves com assento ejetável;
XIV - Voo em aeronaves com capacidade de cargas acelerativas iguais ou superiores a 6g/s;
XV - Voo acrobático;
XVI - Controle de tráfego aéreo;
XVII - Operação em estação aeronáutica;
XVIII - Operações insalubres (devendo ser discriminadas conforme Laudo Ambiental ou similar);
XIX - Manipulação de alimentos;
XX - Exposição à radiação ionizante;
XXI - Exposição a ruídos iguais ou maiores a 85 decibéis (dB);
XXII - Exposição solar prolongada;
XXIII - Condução de veículos militares;
XXIV - Condução de motocicletas;
XXV - Trabalho em altura;
XXVI - Mergulho; e
XXVII - Paraquedismo.
XXVIII - Atividades não listadas, e que serão descritas no corpo do parecer.
Parágrafo único. A emissão de incapacidade em atividades não discriminadas no art. 139 deverá ser precedida de pedido de autorização da JSL à Divisão de Medicina Pericial (DMP) da DIRSA, via cadeia de comando.

Art. 140. Os inspecionados que tenham o parecer de "INCAPAZ TEMPORARIAMENTE POR xx DIAS PARA alguma atividade específica" em uma AVALIAÇÃO ESPECIAL DE SAÚDE somente poderão ser reinspecionados, durante a validade ou ao término da restrição, pela JSL que emitiu este parecer, ou ainda pela JSL do CEMAL. Excepcionalmente, por decisão da DIRSA, através da Divisão de Medicina Pericial, poderão ser inspecionados em uma JSL de maior proximidade a sua localização, desde que sua inspeção vigente tenha sido feita em prontuário eletrônico/sistema informatizado para que seja possível a consulta ao seu resultado de inspeção anterior ou desde que toda a sua documentação pericial seja enviada a JSL examinadora.
§1º. Os inspecionados que tenham o parecer de "INCAPAZ TEMPORARIAMENTE PARA O EXERCÍCIO DA ATIVIDADE AÉREA MILITAR", "INCAPACIDADE TEMPORÁRIA PARA ATIVIDADE DE CONTROLE DE TRÁFEGO AÉREO" e "INCAPACIDADE TEMPORÁRIA PARA ATIVIDADE DE OPERADOR DE ESTAÇÃO AERONÁUTICA", deverão ser encaminhados para avaliação pela JSL do Hospital de Força Aérea / Aeronáutica de referência, após completarem 180 (cento e oitenta) dias na incapacidade específica.
§2º. No caso de Hospitais de Força Aérea / Aeronáutica de referência sediados na localidade do Rio de Janeiro, os inspecionados de que trata o art. 140, §1º, serão encaminhados para avaliação no CEMAL.

Art. 141. Nos casos de LETRA G que os militares apresentarem incapacidade parcial ou total e se tornarem portadores de Atestado de Origem (AO), de resultado de Inquérito Sanitário de Origem (ISO) e de relatório final de Inquérito Epidemiológico (IE) cujo laudo aponte causa ocupacional, deverá constar no parecer emitido pela JSS o documento comprobatório ratificando o ocorrido.

Art. 142. Para os militares de carreira, deverão ser verificadas as possíveis consequências administrativas:
I - os casos de Parecer "INCAPAZ TEMPORARIAMENTE para uma finalidade específica" (art. 138, inciso 'I' desta Norma) há mais de 3 (três) anos deverão ser encaminhados à JSS para homologação. Após homologação, deverão ser encaminhados pela JSS à DIRAP, a fim de ser verificada a aplicabilidade do art. 82-A e artigos 106 a 111 da Lei nº 6.880/1980.
II - os casos de Parecer "INCAPAZ TEMPORARIAMENTE PARA TODAS AS ATIVIDADES" (art. 138, inciso 'Il' desta Norma), em que o militar esteja enquadrado há mais de 1 (um) ano, deverão ser encaminhados à JSS para homologação. Após essa homologação, deverão ser encaminhados pela JSS à DIRAP para ser verificada a aplicabilidade do art. 82, inciso I da Lei 6.880/1980.
a) Permanecendo o militar com incapacidade temporária total após 2 (dois) anos da homologação inicial pela JSS, a JSL encaminhará novamente o caso à JSS, para nova homologação. Após essa nova homologação, deverá ser encaminhado uma vez mais à DIRAP, a fim de ser verificada a aplicabilidade do art. 106, inciso III da Lei nº 6.880/1980.
III - os casos de Parecer "INCAPAZ DEFINITIVAMENTE PARA O SERVIÇO MILITAR" (art. 138, inciso III desta Norma) homologados pela JSS deverão ser encaminhados à DIRAP, a fim de ser verificada a aplicabilidade do art. 82-A e artigos 106 a 111 da Lei nº 6.880/1980.
Parágrafo único. O militar de carreira sem estabilidade assegurada, desligado por motivo de licenciamento, que fizer jus à continuação do tratamento, até a efetivação da alta por restabelecimento ou a pedido, na forma do art. 35 do Decreto nº 3.690, deve ser submetido a nova inspeção de saúde em até 90 (noventa) dias para finalidade LETRA E.

Art. 143. Os alunos considerados "INCAPAZES" nas inspeções para fins de LETRA G estarão sujeitos às providências administrativas previstas nos regulamentos das instituições de ensino a que estiverem subordinados.

Art. 144. No caso de militares temporários enquadrados nas situações a seguir, deverão ser verificadas, pela OM do inspecionado, as possíveis consequências administrativas:
I - se incapacidade temporária superior a 180 dias, verificar a aplicabilidade do art. 39, inciso II, do Decreto 10.986/2022; e, ainda, a aplicabilidade dos § 6º e § 8º do art. 31 da Lei nº 4.375, de 17 de agosto de 1964 (Encostamento).
II - se incapacidade definitiva, verificar a aplicabilidade do inciso II-A do art. 106, assim como do art. 108 e do art. 111 da Lei nº 6.880/1980.

LETRA H - Relacionadas à verificação periódica da capacidade funcional dos militares de carreira

Art. 145. Aplicada para verificação periódica da capacidade física/mental dos militares de carreira (exceto aqueles que estejam funcionalmente obrigados ao controle do tráfego aéreo e/ou operação de estação aeronáutica), com ou sem estabilidade assegurada, incluindo os alunos de órgãos de formação de militares.
Parágrafo único. Para os militares de carreira, com ou sem estabilidade assegurada, que estejam funcionalmente obrigados ao controle do tráfego aéreo e/ou operação de estação aeronáutica, a verificação periódica de saúde será realizada por meio da inspeção para fins de LETRA L.

Art. 146. A emissão de qualquer parecer para esta finalidade deverá considerar a existência ou não de ordem judicial relacionada a motivos de saúde. Nos casos em que existir determinação judicial, deverá ser observado o disposto no art. 25 ao art. 32 desta norma.

Art. 147. O parecer emitido para finalidade LETRA H obedecerá ao seguinte modelo:
I - "APTO para o desempenho das suas atividades profissionais".
II - "APTO para o desempenho das suas atividades profissionais por xxx dias [para os casos em que a Junta de Saúde/AMP decidir reduzir o prazo de validade da inspeção, conforme art. 148, do Parágrafo único desta Norma]".
III - "INCAPAZ TEMPORARIAMENTE PARA [discriminar a(s) atividade(s) na qual há incapacidade] POR xx DIAS, PODENDO EXERCER DEMAIS ATIVIDADES INERENTES A SUA FUNÇÃO. Deverá realizar LETRA G na próxima inspeção".
IV - "INCAPAZ TEMPORARIAMENTE PARA TODAS AS ATIVIDADES POR xx DIAS. Deverá realizar LETRA G na próxima inspeção".

Art. 148. A validade das inspeções para a finalidade LETRA H será estabelecida de acordo com o grupo e a função exercida (conforme ANEXO III - Classificação dos Inspecionados e Periodicidade das Inspeções).
Parágrafo único. A Junta de Saúde/AMP tem a prerrogativa de reduzir os prazos de validade das inspeções de saúde periódicas, de acordo com o diagnóstico estabelecido e a necessidade de identificar se o acompanhamento periódico ou o tratamento sugerido em parecer(es) anterior(es) da JS estão sendo eficazes.

Art. 149. A inspeção para fins de LETRA G interrompe a validade da inspeção para a finalidade da LETRA H.

LETRA I - Relacionada aos Cursos Operacionais do COMAER ou início de Atividade Aérea

Art. 150. Aplica-se ao militar não Aeronavegante quando:
I - indicado para fazer curso operacional; ou
II - formalmente designado a iniciar função como Aeronavegante, mediante publicação em Boletim Interno.
Parágrafo único. Ao militar não Aeronavegante que se mantenha em função de Aeronavegante, as próximas inspeções periódicas (LETRA D ou LETRA H, conforme o caso) deverão ser realizadas com critérios de "AVALIAÇÃO ESPECIAL DE SAÚDE", enquanto exercer a função de Aeronavegante.

Art. 151. Os pareceres emitidos para fins de LETRA I obedecerão aos seguintes modelos, conforme o caso:
I - "APTO para o exercício de atividades operacionais/de Aeronavegantes/de voo"; ou
II - "INCAPAZ para o exercício de atividades operacionais/de Aeronavegantes/de voo".

Art. 152. A validade das inspeções para a finalidade LETRA I dos militares de terra indicados para curso operacional será para a demanda em trâmite.

Art. 153. A validade das inspeções para a finalidade LETRA I dos militares de terra designados a iniciar função como Aeronavegante será estabelecida de acordo com o grupo e a função exercida (conforme ANEXO III - Classificação dos Inspecionados e Periodicidade das Inspeções).

LETRA J - Relacionadas à designação de militares inativos como PTTC

Art. 154. Aplicada para a verificação da aptidão física e mental dos militares inativos da Aeronáutica, desde que não inválidos e não reformados por motivo de saúde, para fins de contratação inicial para prestação de tarefa por tempo certo.

Art. 155. O militar inativo estará dispensado da realização de inspeção de saúde para finalidade LETRA J1 quando as seguintes condições estiverem presentes concomitantemente:
I - estar com inspeção periódica (LETRA H) válida, com parecer "APTO", na data de contratação para PTTC; e
II - ser designado para tarefa que não implique o uso de critérios de saúde diferentes dos utilizados na última inspeção com a finalidade LETRA H válida.

Art. 156. Na INSPSAU destinada à contratação inicial para prestação de tarefa por tempo certo, os militares serão avaliados conforme a tarefa a ser exercida quanto aos critérios de "AVALIAÇÃO ESPECIAL DE SAÚDE" ou "AVALIAÇÃO REGULAR DE SAÚDE".

Art. 157. A partir da contratação inicial, os militares veteranos designados para a prestação de tarefas sujeitas a critérios de "AVALIAÇÃO ESPECIAL DE SAÚDE", deverão realizar INSPSAU para verificação periódica de capacidade funcional (LETRA H ou LETRA L, conforme o caso), de forma similar aos militares da ativa que exercem tais funções, respeitadas as periodicidades previstas nesta norma.

Art. 158. Os pareceres emitidos para fins de LETRA J obedecerão aos seguintes modelos, conforme o caso:
I - "APTO para Prestação de Tarefa por Tempo Certo"; ou
II - "INCAPAZ para Prestação de Tarefa por Tempo Certo".
Parágrafo único. Nos casos de incapacidade, deverá constar o motivo no campo "Observações" do documento de informação de saúde (DIS), a causa dessa incapacidade, em conformidade com a legislação de saúde pertinente, e o CID.

Art. 159. A validade das inspeções para a finalidade LETRA J será para a demanda em trâmite.

LETRA L - Relacionadas à Licença do Pessoal de Navegação AÉREA - LPNA

Art. 160. A Licença do Pessoal de Navegação Aérea (LPNA) é o documento de validade permanente, emitido pelo DECEA (Departamento de Controle do Espaço Aéreo), necessário ao exercício específico das seguintes funções, no âmbito do SISCEAB (Sistema de Controle do Espaço Aéreo Brasileiro):
I - Controlador de Tráfego Aéreo (ATCO);
II - Profissional em Informação Aeronáutica (AIS);
III - Profissional em Meteorologia Aeronáutica (MET);
IV - Operador de Estação Aeronáutica (OEA);
V - Radioperador de Plataforma Marítima (RPM); e
VI - Gerente de Controle do Espaço Aéreo (GCEA).

Art. 161. A inspeção para fins de LETRA L é aplicada para:
I - verificação inicial da capacidade física e mental dos candidatos civis e militares que exercerão uma das funções listadas no art. 160; e
II - inspeção periódica dos militares de carreira, PTTC e servidores civis do COMAER que exercem uma das funções listadas no art. 160.
Parágrafo único. Os critérios de Avaliação de Saúde Especial ou Regular, serão definidos de acordo com o pré-requisito específico para cada função listada no art. 160.

Art. 162. LETRA L1 - Aplicada nos seguintes casos:
I - aos alunos da Escola de Especialistas da Aeronáutica (EEAR), que desempenharão uma das funções listadas no art. 160, antes do término do curso, com o objetivo de avaliarem sua capacidade laborativa e permanência no serviço ativo. Os que obtiverem parecer "INCAPAZ" não poderão exercer aquela função específica e seguirão os trâmites administrativos cabíveis da Escola;
II - aos demais militares que necessitem da concessão de LPNA, conforme a legislação específica em vigor, e que eventualmente necessitem exercer atividade operacional de uma das funções listadas no art. 160; e
III - aos militares que precisem revalidar sua inspeção de saúde para fins de LETRA L (ou seu Certificado Médico Aeronáutico - CMA) vencida há mais de 05 (cinco) anos. Enquadram-se nessa condição os militares na inatividade, que retornam a uma das funções listadas no art. 160.
Parágrafo único. Na Inspeção de Saúde de revalidação serão aplicados os exames realizados em uma inspeção inicial, porém o julgamento obedece aos requisitos de uma inspeção de revalidação.

Art. 163. LETRA L2 - Aplicada na inspeção periódica dos militares de carreira, com ou sem estabilidade assegurada, e PTTC que exerçam uma das funções listadas no art. 160.

Art. 164. A verificação periódica da aptidão física e mental dos militares temporários que exercem uma das funções listadas no art. 160 ocorrerá por meio da finalidade LETRA D, com critério de AVALIAÇÃO DE SAÚDE ESPECIAL ou REGULAR, conforme a previsão estabelecida no pré-requisito específico para a concessão da LPNA.

Art. 165. LETRA L3 - Aplicada nos seguintes casos:
I - verificação inicial da capacidade física e mental do candidato civil que exercerá uma das funções listadas no art. 160;
II - aos servidores civis do COMAER que precisem revalidar sua inspeção de saúde para fins de LETRA L (ou seu Certificado Médico Aeronáutico - CMA) vencida há mais de 05 (cinco) anos.

Art. 166. LETRA L4 - Aplicada na inspeção periódica de servidores civis do COMAER que exerçam uma das funções listadas no art. 160.

Art. 167. Não deverão realizar a inspeção para finalidade L2 ou L4 (periódicos) os inspecionados que tenham incapacidade ao exercício de uma das funções listadas no art. 160.

Art. 168. Os civis e militares envolvidos com uma das funções listadas no art. 160 que apresentarem indícios de comprometimento de seus requisitos de aptidão psicofísica não poderão continuar operando, devendo ser encaminhados imediatamente pela Autoridade Aeronáutica/OSA/JSL/AMP, para uma nova inspeção de saúde, ainda que esteja válido o seu CMA.
§1º. Todo militar ou civil que exerça uma das funções listadas no art. 160, ao perceber uma diminuição, alteração e/ou perda de sua aptidão psicofísica para o exercício de sua atividade é responsável por comunicar sua condição de saúde ao responsável do Órgão ao qual está subordinado.
§2º. São também responsáveis pelo reporte previsto no §1º do art. 168:
I - o Agente Médico Pericial e/ou o médico de OSA que tome conhecimento da diminuição das condições psicofísicas dos militares ou civis em tela, de modo que possa interferir no exercício seguro de suas atribuições;
II - o médico assistente, não enquadrado no inciso I, do §2º, do art. 168, quando tenha conhecimento de que os militares ou civis em tela apresentem alteração no seu estado psicofísico que venha a colocar em risco a sua capacidade laborativa, comprometendo a segurança do tráfego aéreo, deverá fazer este comunicado, o mais rápido possível, à AMP/JSL que emitiu o parecer de aptidão para fins de LETRA L ou à Diretoria de Saúde da Aeronáutica, diretamente ou através do seu Conselho Regional de Medicina;
III - os serviços médicos da Empresa Prestadora de Serviço de Tráfego Aéreo; e
IV - as Empresas Prestadoras de Serviço de Tráfego Aéreo que tomem conhecimento através de atestado médico externo ao seu serviço médico.

Art. 169. Os candidatos civis a Controladores de Tráfego Aéreo e os Operadores de Estação Aeronáutica civis da Aeronáutica e das empresas prestadoras de Serviço de Tráfego Aéreo (todos civis), serão inspecionados de acordo com a ICA 63-15 (Inspeção de Saúde e Certificado Médico Aeronáutico para controlador de Tráfego Aéreo e Operador de Estação Aeronáutica).

Art. 170. O resultado da Inspeção de Saúde dos Controladores de Tráfego Aéreo e operadores de estação aeronáutica, civis e militares, (QSS BCT/BCO, QOECTA, QOECOM e civis ATCO e OEA) deverá ser inserido no SISTEMA DE GERENCIAMENTO DE PESSOAL OPERACIONAL (SGPO), no Módulo Saúde, pelo Gerente de Saúde, de acordo com o previsto na PORTARIA CONJUNTA DECEA/DIRSA N° 01 de 22 de setembro de 2015, com o objetivo de promover a informatização do controle dos processos de emissão e revalidação da habilitação técnica desses profissionais, enquanto o processo de informatização não se dê de forma automática.

Art. 171. Os pareceres emitidos para fins de LETRA L1 e L2 (referentes a militares) obedecerão aos seguintes modelos, conforme o caso:
I - "APTO à (concessão) de Licença do Pessoal de Navegação Aérea (LPNA)".
II - "APTO ao desempenho das atividades profissionais de controlador de tráfego aéreo/Operador de Estação Aeronáutica/ Gerente de Controle do Espaço Aéreo/ Profissional em Informação Aeronáutica/ Profissional em Meteorologia Aeronáutica/ Radioperador de Plataforma Marítima."
III - "INCAPAZ à (concessão) de Licença do Pessoal de Navegação Aérea (LPNA)". Nos casos de incapacidade, deverá constar o motivo no campo "Observações", em conformidade com a legislação de saúde pertinente e o CID.
IV - "INCAPAZ TEMPORARIAMENTE PARA [discriminar a(s) atividade(s) na qual há incapacidade] POR xx DIAS, PODENDO EXERCER DEMAIS ATIVIDADES PROFISSIONAIS DE CONTROLADOR DE TRÁFEGOAÉREO/OPERADOR DE ESTAÇÃO Aeronáutica/ GCEA/AIS/MET/RPM. Deverá realizar LETRA G na próxima inspeção".
V - "INCAPAZ TEMPORARIAMENTE PARA O CONTROLE DO TRÁFEGOAÉREO/OPERAÇÃO DE ESTAÇÃO AERONÁUTICA/ GCEA/AIS/MET/RPM. Deverá realizar LETRA G na próxima inspeção".
Parágrafo único. O inspecionado que se encontrar INCAPAZ na inspeção LETRA L, terá esta inspeção cancelada e substituída pela LETRA G.

Art. 172. Os pareceres emitidos para fins de LETRA L3 e L4 (referentes a civis) obedecerão aos modelos previstos na ICA 63-15.

Art. 173. A validade das inspeções para a finalidade LETRA L1 e L2 (referentes a militares) será estabelecida de acordo com o grupo e a função exercida (conforme ANEXO III - Classificação dos Inspecionados e Periodicidade das Inspeções), podendo ter sua validade reduzida a critério da JS/AMP.

Art. 174. A validade das inspeções para a finalidade LETRA L3 e L4 (referentes a civis) será de acordo com o previsto na ICA 63-15.

LETRA N1 - Inclusão por Ordem Judicial/Reinclusão

Art. 175. Aplicada para fins de inclusão por ordem judicial/ reinclusão. Os casos que possuam ordem judicial relacionada a motivos de saúde deverão observar o art. 25 ao art. 32 desta Norma.

Art. 176. O militar que exerça função como Aeronavegante, controlador de tráfego aéreo, operador de estação aeronáutica ou demais funções a bordo, deverá ser avaliado com critérios de AVALIAÇÃO ESPECIAL DE SAÚDE e LETRA L quando for o caso.

Art. 177. Os pareceres emitidos para finalidade LETRA N1 obedecerão aos seguintes modelos, conforme o caso:
I - "APTO para [Inclusão / Reinclusão]"; ou
II - "INCAPAZ para [Inclusão / Reinclusão]".
Parágrafo único. Nos casos de inaptidão, o motivo deverá constar no campo observações da ata de inspeção de saúde, em conformidade com a legislação de saúde pertinente.

Art. 178. Os inspecionados julgados INCAPAZES poderão solicitar grau de recurso à JSS.

Art. 179. A validade das inspeções para a finalidade LETRA N1 será para a demanda em trâmite.

LETRA N2 - Reversão

Art. 180. Aplicada nos casos em que o militar agregado retorna ao respectivo Corpo ou Quadro tão logo cesse o motivo que determinou sua agregação.

Art. 181. O militar que exerça função como Aeronavegante, Controlador de Tráfego Aéreo, Operador de Estação Aeronáutica ou demais funções a bordo, deverá ser avaliado com critérios de AVALIAÇÃO ESPECIAL DE SAÚDE e LETRA L quando for o caso.

Art. 182. Os pareceres emitidos para finalidade LETRA N2 obedecerão aos seguintes modelos, conforme o caso:
I - "APTO para Reversão"; ou
II - "INCAPAZ para Reversão".
Parágrafo único. Nos casos de inaptidão, o motivo deverá constar no campo observações da ata de inspeção de saúde, em conformidade com a legislação de saúde pertinente.

Art. 183. Os inspecionados julgados INCAPAZES poderão solicitar grau de recurso à JSS.

Art. 184. A validade das inspeções para a finalidade LETRA N2 será para a demanda em trâmite.

LETRA N3 - Designação para o Serviço Ativo - DSA

Art. 185. Aplicada para a verificação da aptidão física e mental do militar inativo da Aeronáutica, desde que não inválido, a ser designado para o serviço ativo.

Art. 186. O militar inativo designado para o serviço ativo estará dispensado da realização de inspeção de saúde para finalidade LETRA N3 quando as seguintes condições estiverem presentes concomitantemente:
I - estar com inspeção periódica (LETRA H) válida na data da designação para o serviço ativo, com parecer "APTO"; e
II - ser designado para o serviço ativo visando ao exercício de atividades que não impliquem o uso de critérios de saúde diferentes dos utilizados na última inspeção finalidade LETRA H válida.

Art. 187. Os militares deverão ser avaliados conforme as atividades a serem exercidas quanto aos critérios de "AVALIAÇÃO ESPECIAL DE SAÚDE" OU "AVALIAÇÃO REGULAR DE SAÚDE".

Art. 188. O militar que exerça função como aeronavegante, controlador de tráfego aéreo, operador de estação aeronáutica ou demais funções a bordo, deverão ser avaliados com critérios de AVALIAÇÃO ESPECIAL DE SAÚDE.

Art. 189. Os pareceres emitidos para fins de LETRA N3 obedecerão aos seguintes modelos, conforme o caso:
I - "APTO para Designação para o Serviço Ativo"; ou
II - "INCAPAZ para Designação para o serviço Ativo".
Parágrafo único. Nos casos de incapacidade, deverá constar o motivo no campo "Observações", em conformidade com a legislação de saúde pertinente e o CID.

Art. 190. A validade das inspeções para a finalidade LETRA N3 será estabelecida de acordo com o grupo e a função exercida (conforme ANEXO III Classificação dos Inspecionados e Periodicidade das Inspeções), podendo ter sua validade reduzida a critério da JS/AMP.

Art. 191. Após a designação para o serviço ativo, os inspecionados passarão a ser avaliados de acordo as finalidades com os critérios e periodicidade previstos para a especialidade designada.

LETRA O - Relacionadas aos Benefícios/Licenças

Art. 192. Aplicada aos militares e respectivos dependentes, bem como aos pensionistas e servidores civis aposentados, para os efeitos declarados nos requerimentos de Inspeção de Saúde ou na Ordem de Inspeção expedida por interesse da Administração.

Art. 193. Subdivide-se nos seguintes tipos:
I - LETRA O1 - Assistência pré-escolar fora da faixa etária;
II - LETRA O2 - Adicional de invalidez;
III - LETRA O3 - Habilitação à pensão militar;
IV - LETRA O4 - Habilitação à pensão especial. Serão consideradas para fins de concessão de pensão especial à viúva de militar ou servidor civil, as atacadas de tuberculose ativa, alienação mental, neoplasia maligna, cegueira, hanseníase, paralisia irreversível e incapacitante ou cardiopatia grave, obedecendo os critérios de enquadramento da portaria de doenças especificadas em lei vigente, em conformidade a estas doenças especificadas. A invalidez da beneficiária será verificada mediante exame médico conforme previsto no artigo 4º da Lei 3738 de 4 de abril de 1960;
V - LETRA O5 - Habilitação a pensão civil;
VI - LETRA O6 - Isenção de imposto de renda para militar na inatividade;
VII - LETRA O7 - Isenção de imposto de renda para servidor civil aposentado;
VIII - LETRA O8 - Isenção de imposto de renda para pensionista;
IX - LETRA O9 - Comprovação de incapacidade permanente para os atos da vida civil;
X - LETRA O10 - Licença para tratamento de saúde de pessoa da família;
XI - LETRA O11 - Reforma com proventos de grau hierárquico superior;
XII - LETRA O12 - Transferência por motivo de saúde do próprio militar;
XIII - LETRA O13 - Transferência por motivo de saúde do dependente;
XIV - LETRA O14 - Outros direitos previstos nas leis e regulamentos aplicáveis e de interesse do COMAER.

Art. 194. O militar ou o interessado, em sua OM de vinculação fará requerimento pessoal endereçado à autoridade da instância pericial a qual se encontrar subordinado, e solicitará Inspeção de Saúde, para obtenção do benefício, expressa em termos bem claros.
§1º. Uma vez verificada a existência de amparo legal para o que foi solicitado, o Comandante/Chefe/Diretor da OM de vinculação determinará a ordem de Inspeção de Saúde, para publicação.
§2º. O requerimento do processo administrativo referente à habilitação à pensão (civil, militar e especial) e a transferência por motivo de saúde (do próprio militar e de seus dependentes), deve ser realizado somente após a conclusão da INSPSAU, solicitada conforme o art. 194.

Art. 195. Após a determinação de Inspeção de Saúde pela autoridade competente, o processo contendo o requerimento deverá ser encaminhado à autoridade da instância pericial pertinente.

Art. 196. Caberá ao interessado anexar as informações médicas e administrativas necessárias para compor o Processo, podendo a administração restituir o mesmo, caso não preencha os requisitos necessários para apreciação.

Art. 197. Para os casos de concessão de benefício financeiro (auxílio pré-escolar fora de faixa, isenção de imposto de renda, auxílio invalidez e melhorias de proventos), os julgamentos corresponderão ao que estiver determinado e publicado, por extenso, nas Ordens de Inspeção de Saúde das Autoridades Competentes das OM do COMAER, atendendo a finalidade específica daquela inspeção a ser realizada.
Parágrafo único. Todos os julgamentos que ensejarem a concessão de benefícios pecuniários previstos em lei somente terão efeito após serem homologados pela JSS.

Art. 198. As inspeções de saúde LETRA O9 deverão ser realizadas para os casos em se deseja assegurar ao dependente, que possua incapacidade permanente para os atos da vida Civil, o direito de permanecer ou ser inserido como beneficiário do FUNSA ou pensão.

Art. 199. Para os casos das LETRA O10 e LETRA O13, em que o inspecionado é pessoa da família, e não o militar, a solicitação da Inspeção de Saúde deverá ser no nome do dependente e, no requerimento, deverá estar explícito o que se requer.

Art. 200. Não será concedido benefício previsto em lei ou regulamento, decorrente de moléstia do militar ou de seus dependentes, sem que se realize Inspeção de Saúde para a devida finalidade.

Art. 201. Nos casos de LETRA O10, deverão ser observados o seguinte:
I - confirmação da patologia sobre data de diagnóstico, proposta terapêutica, gravidade do caso, urgência no atendimento, possíveis riscos, evolução clínica da doença, entre outros que sirvam para subsidiar a Administração quanto à decisão de efetivar ou não a licença requerida;
II - o prazo mínimo de afastamento será de 15 dias e o máximo de 6 meses;
III - para essa finalidade, serão consideradas pessoas da família as estabelecidas pelo RISAER;
IV - para cada nova prorrogação, um novo processo com nova inspeção de saúde deverá ser aberto, respeitando o prazo máximo de afastamento estabelecido no inciso II, do art. 201; e
V - Poderá ser requerido Laudo Social para avaliar situação do inspecionado, a critério da JSL.

Art. 202. Para os casos de LETRA O12 e LETRA O13, poderá ser requerido Laudo Social para avaliar situação do inspecionado, a critério da JSL.

Art. 203. No caso da impossibilidade de locomoção dos inspecionados, a Inspeção de Saúde ou a avaliação para confecção de Parecer Especializado deverá ser realizada na residência dos mesmos ou no estabelecimento hospitalar que estiverem internados. A JSL poderá demandar a OSA ou OC (Organização Credenciadora) responsável pela internação em tela para emitir parecer médico especializado, a fim de subsidiar o julgamento da inspeção.
Parágrafo único. Excepcionalmente, a avaliação dos casos enquadrados no art. 203 poderá ser realizada por meio de análise documental, desde que não envolva a avaliação de dano pessoal, capacidade laborativa (invalidez), ou que seja de natureza médico legal.

Art. 204. Para os casos das LETRA O2, LETRA O6 e LETRA O11, deve-se observar que as solicitações deverão ser analisadas pelos médicos peritos exclusivamente do ponto de vista da saúde e, para tal, o resultado de julgamento deve ser completo, incluindo as respostas aos principais questionamentos que interessam às solicitações.

Art. 205. Todos os julgamentos da finalidade para fins de LETRA O que forem favoráveis ao benefício pleiteado deverão obrigatoriamente ser homologados pela JSS para ter validade, exceto as finalidades O10 e O14, esta última quando não estiver relacionada com ônus ao erário.

Art. 206. Os pareceres emitidos para finalidade LETRA O obedecerão, conforme o caso, aos modelos previstos no ANEXO IV - Modelos de Parecer para Inspeção de Saúde Finalidade LETRA O.
Parágrafo único. Para as finalidades LETRA O, a DIRSA poderá emitir orientações (Ordem Técnica) sobre os padrões de parecer estabelecidos para este fim.

LETRA P - Relacionadas à verificação da Aptidão Física e Mental dos envolvidos em acidentes ou incidentes aeronáuticos

Art. 207. Aplicada aos tripulantes e aos controladores de tráfego aéreo envolvidos em acidentes ou incidentes aeronáuticos, quando por determinação de autoridade competente, com ou sem lesões corporais.

Art. 208. Incidentes/Acidentes aeronáuticos de que tratam a LETRA P interrompem a LETRA H/L, se houver restrições e/ou incapacidades. Nesses casos, em sua próxima inspeção deverá ser avaliado para finalidade LETRA G.

Art. 209. Com o intuito de atender imediatamente o incidente aeronáutico, os órgãos responsáveis para encaminhamento para realização de saúde da LETRA P deverão acionar a Junta de Saúde Local mais próxima para realizar a abertura da Inspeção de Saúde. Essa ação se dará via Ofício de determinação de Inspeção de Saúde.

Art. 210. Quando o incidente/acidente ocorrer fora do expediente, o responsável da JSL deverá ser acionado para providenciar a abertura da Inspeção de Saúde no 1º dia útil subsequente ao ocorrido.
Parágrafo único. Na situação do art. 210 o militar deverá pelo menos realizar os exames laboratoriais e avaliação de Clínica Médica, com realização dos demais exames e clínicas no dia seguinte ou no próximo dia de expediente. Nessa inspeção, aplicam-se todos os exames e avaliações que integram uma inspeção inicial.

Art. 211. O exame pós-incidente/acidente deve contemplar as avaliações psicológicas e psiquiátricas pertinentes para detecção de estresse pós-traumático e exame toxicológico para detecção de substâncias psicoativas (ETSP).

Art. 212. Os controladores de tráfego aéreo e operadores de estação aeronáutica militares, quando envolvidos em acidentes e/ou incidentes aeronáuticos graves, realizam Inspeção de Saúde aplicando-se todos os exames de uma inspeção inicial.

Art. 213. O DECEA coordenará a Inspeção de Saúde dos ATCO ou OEA que estejam envolvidos em acidente/ incidente aeronáutico grave, no curso de sua atividade. A ICA 63-15 deve ser observada quanto aos procedimentos a serem adotados nesses casos.

Art. 214. São responsáveis pelo encaminhamento para a realização de Inspeção de Saúde para a LETRA P:
I - o órgão de investigação e prevenção de acidentes aeronáuticos que tome conhecimento do caso;
II - a organização de saúde Aeronáutica que tome conhecimento do caso; e
III - o setor de recursos humanos de OM do COMAER ou das empresas conveniadas que prestam serviço de controle de tráfego aéreo que tomem conhecimento do fato.

Art. 215. Os pareceres desta finalidade serão os mesmos aplicados à LETRA "G".

Art. 216. Os julgamentos de incapacidade definitiva somente terão efeito após serem homologados pela JSS.

Art. 217. Os casos de incapacidade temporária deverão ser inspecionados para fins de LETRA G em sua próxima inspeção.

LETRA R1 - Verificação de Estado de Saúde do Desertor e do Insubmisso

Art. 218. Aplicada ao desertor ou ao insubmisso, capturado ou que se apresente voluntariamente, a fim de verificar se o mesmo se encontra apto ou incapaz para o Serviço Militar, sem quaisquer considerações sobre sua capacidade de entendimento ou determinação, ao tempo da deserção.

Art. 219. A ata do desertor, quando não estabilizado/temporário e for julgado incapaz definitivamente para o Serviço Militar, deve ser enviada, com urgência, para a Auditoria Militar a qual foram distribuídos os autos da Instrução Provisória de Deserção (IPD).

Art. 220. Os pareceres emitidos para fins de LETRA R1 obedecerão aos seguintes modelos, conforme o caso:
I - "APTO para o Serviço Militar"; ou
II - "INCAPAZ para o Serviço Militar".

Art. 221. A validade das inspeções para a finalidade LETRA R1 será para a demanda em trâmite.

LETRA R2 - Verificação de Capacidade Cognitiva

Art. 222. Aplicada aos militares para verificação da capacidade de discernimento, entendimento e autodeterminação com permanência do juízo de valor e realidade, para que possam ser submetidos a processos para fins de justiça e disciplina. Deverão ser inspecionados obrigatoriamente nas especialidades de clínica médica e psiquiatria, e outras clínicas que se fizerem necessárias.

Art. 223. Os pareceres emitidos para fins de LETRA R2 obedecerão aos seguintes modelos, conforme o caso:
I - "Apto, com capacidade de discernimento, entendimento e autodeterminação, com permanência do juízo de valor e realidade, para fins de Justiça e Disciplina"; e
II - "INCAPAZ quanto a discernimento, entendimento e/ou autodeterminação. Deverá ser inspecionado para fins de LETRA G".

    """
    

    human_prompt = "Analise este documento de INSPSAU e extraia os dados de acordo com a sua base de conhecimento da NSCA:\n\n{documento}"
    
    structured_llm = model.with_structured_output(AnaliseInspsau)

    prompt = ChatPromptTemplate.from_messages([
        ("system", sys_prompt),
        ("human", human_prompt)
    ])
    chain = prompt | structured_llm
    resultado = chain.invoke({"documento": conteudo_pdf})
    return resultado