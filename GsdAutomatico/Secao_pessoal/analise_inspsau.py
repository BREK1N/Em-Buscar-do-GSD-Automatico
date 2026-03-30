# GsdAutomatico/Secao_pessoal/analise_inspsau.py
import os
import httpx
from typing import List
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

def analisar_inspsau_pdf(conteudo_pdf: str) -> AnaliseInspsau:
    """
    Invoca a IA para analisar o conteúdo de um PDF de INSPSAU e extrair os dados.
    """
    structured_llm = model.with_structured_output(AnaliseInspsau)

    sys_prompt = """
    Você é um assistente especialista em analisar documentos militares de Inspeção de Saúde (INSPSAU).
    Sua tarefa é extrair três informações específicas do texto fornecido.

    ### REGRAS DE EXTRAÇÃO:
    1.  **FINALIDADE:** Encontre a palavra "FINALIDADE". Logo após, haverá uma letra maiúscula em negrito e entre aspas. Extraia **APENAS A LETRA**. Por exemplo, se encontrar `FINALIDADE: **"A"**`, o valor a ser extraído é `A`.
    2.  **POSTO/GRADUAÇÃO:** Identifique e extraia o posto ou graduação do militar. Exemplos: "3S", "CB", "S1", "1T", "CAP".
    3.  **NOME COMPLETO:** Identifique e extraia o nome completo do militar que está sendo inspecionado.

    Analise o documento com atenção e retorne os dados no formato JSON solicitado.
    """
    
    human_prompt = "Analise este documento de INSPSAU e extraia os dados:\n\n{documento}"

    prompt = ChatPromptTemplate.from_messages([
        ("system", sys_prompt),
        ("human", human_prompt)
    ])

    chain = prompt | structured_llm
    resultado = chain.invoke({"documento": conteudo_pdf})
    return resultado