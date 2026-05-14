import os
import httpx
from pydantic import BaseModel, Field
from typing import List, Optional
from dotenv import load_dotenv
from langchain_openai import ChatOpenAI
from langchain.prompts import ChatPromptTemplate

load_dotenv()

openai_api_key = os.getenv("OPENAI_API_KEY")
proxy_url = os.getenv("http_proxy") or os.getenv("HTTP_PROXY") or os.getenv("https_proxy") or os.getenv("HTTPS_PROXY")
if proxy_url:
    http_client = httpx.Client(proxy=proxy_url, verify=False, timeout=60.0)
else:
    http_client = httpx.Client(verify=False)

model = ChatOpenAI(
    model="gpt-4o",
    temperature=0,
    api_key=openai_api_key,
    http_client=http_client
)

class MilitarFalta(BaseModel):
    nome_guerra: str = Field(description="Nome de guerra do militar faltoso")
    posto: str = Field(description="Posto ou graduação do militar (Ex: 3S, CB, S2)")
    saram: Optional[str] = Field(default="", description="SARAM do militar, se constar")

class AnaliseFQ(BaseModel):
    faltosos: List[MilitarFalta] = Field(default_factory=list, description="Lista de militares identificados como FALTOSOS / AUSENTES.")

def analisar_fq_documento(conteudo_pdf: str) -> AnaliseFQ:
    structured_llm = model.with_structured_output(AnaliseFQ)
    sys_prompt = """
    Você é um assistente especialista em analisar Fichas de Faltas ao Quartel (FQ) e relatórios de efetivo militares.
    Sua tarefa é ler o texto extraído do documento e identificar TODOS os militares que estão explicitamente marcados com FALTA, FALTOSO, AUSENTE, "F" ou que não compareceram ao expediente.
    Extraia o posto/graduação, nome de guerra e SARAM (se houver) de cada um.
    ATENÇÃO: NÃO inclua militares que estão "Presentes", "De Férias", "De Serviço", "Baixados" ou "Dispensados". Apenas os que tiveram falta.
    """
    prompt = ChatPromptTemplate.from_messages([
        ("system", sys_prompt),
        ("human", "Analise este documento e extraia os faltosos:\n\n{documento}")
    ])
    chain = prompt | structured_llm
    return chain.invoke({"documento": conteudo_pdf})