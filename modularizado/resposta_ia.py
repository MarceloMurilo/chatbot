from groq import Groq
from config import GROQ_API_KEY, MODELO_IA
from prompt_base import PROMPT_BASE


client = Groq(api_key=GROQ_API_KEY)

def gerar_resposta(pergunta, contexto):
    if not contexto:
        contexto = "Nenhuma informação encontrada nos documentos."

    prompt = PROMPT_BASE.format(
        contexto=contexto,
        pergunta=pergunta
    )

    stream = client.chat.completions.create(
        model=MODELO_IA,
        messages=[{"role": "user", "content": prompt}],
        temperature=0.3,
        top_p=0.1,
        reasoning_effort="medium",
        stream=True
    )

    print("\nIA: ", end="")
    for chunk in stream:
        content = chunk.choices[0].delta.content or ""
        content = content.replace("*", "")
        print(content, end="")
    print()


def stream_resposta(pergunta, contexto, historico_conversa: str = ""):
    """
    Gera resposta em modo streaming, produzindo pedaços de texto para consumo
    em APIs (ex.: FastAPI + StreamingResponse). Remove asteriscos/markdown.
    
    Args:
        pergunta: Pergunta do usuário
        contexto: Contexto dos documentos
        historico_conversa: Histórico formatado da conversa (opcional)
    """
    if not contexto:
        contexto = "Nenhuma informação encontrada nos documentos."

    # Se não há histórico, deixa vazio (não adiciona linha extra)
    historico_formatado = historico_conversa if historico_conversa else ""

    prompt = PROMPT_BASE.format(
        contexto=contexto,
        historico_conversa=historico_formatado,
        pergunta=pergunta
    )

    stream = client.chat.completions.create(
        model=MODELO_IA,
        messages=[{"role": "user", "content": prompt}],
        temperature=0.1,
        top_p=0.05,
        reasoning_effort="medium",
        stream=True
    )

    for chunk in stream:
        content = chunk.choices[0].delta.content or ""
        content = content.replace("*", "")
        if content:
            yield content
