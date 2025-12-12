from typing import Optional, Dict

from fastapi import FastAPI, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse, JSONResponse
from pydantic import BaseModel
from dotenv import load_dotenv
import os
import re
import json
import unicodedata
import google.generativeai as genai
from google.cloud import speech
from groq import Groq

from ingesta import processar_arquivos
from rag import buscar_contexto
from verificador_base_fixa import buscar_resposta_fixa
from resposta_ia import stream_resposta
from sessoes import session_store
from config import GROQ_API_KEY, MODELO_IA
from google_maps import gerar_links_orgaos
from contexto_conversa import formatar_historico_conversa


load_dotenv()
genai.configure(api_key=os.getenv("GOOGLE_API_KEY"))
client_groq = Groq(api_key=GROQ_API_KEY)


class Perfil(BaseModel):
    nome: Optional[str] = None
    idade: Optional[int] = None
    genero: Optional[str] = None
    papel: Optional[str] = None
    problema: Optional[str] = None
    localidade: Optional[str] = None
    intent: Optional[str] = None
    eixo: Optional[str] = None        # CPF, RG, BOLSA, PASSAPORTE, GOVBR, IMPOSTO_RENDA, OUTRO
    subtrilha: Optional[str] = None   # bloqueado, emissao, pendente, etc.


class ChatRequest(BaseModel):
    pergunta: str
    session_id: Optional[str] = None
    perfil: Optional[Perfil] = None
    transcricao: Optional[str] = None


class SessionRequest(BaseModel):
    session_id: str
    perfil: Perfil


def tentar_preencher_perfil_livre(texto: str) -> Dict:
    partes = [p.strip() for p in re.split(r"[,\n]", texto) if p.strip()]
    perfil: Dict = {}
    texto_lower = texto.lower()

    if partes:
        # tenta capturar nome se frase for curta tipo "sou Joao" ou "meu nome e ..."
        if "me chamo" in texto_lower or texto_lower.startswith("sou "):
            tokens = texto.split()
            if len(tokens) >= 2:
                perfil["nome"] = tokens[-1]
        if "meu nome" in texto_lower:
            tokens = texto.replace("é", " ").replace("É", " ").split()
            for i, t in enumerate(tokens):
                if t.lower() == "nome" and i + 1 < len(tokens):
                    perfil["nome"] = tokens[i + 1]
                    break

        for p in partes:
            m = re.search(r"(\d{1,3})", p)
            if m:
                try:
                    idade = int(m.group(1))
                    if 0 < idade < 130:
                        perfil["idade"] = idade
                        break
                except Exception:
                    pass

        if any(g in texto_lower for g in ["mulher", "feminino"]):
            perfil["genero"] = "mulher"
        elif any(g in texto_lower for g in ["homem", "masculino"]):
            perfil["genero"] = "homem"
        elif "trans" in texto_lower:
            perfil["genero"] = "trans"
        elif "nb" in texto_lower or "nao bin" in texto_lower or "não bin" in texto_lower:
            perfil["genero"] = "nao-binario"

        if "mãe" in texto_lower or "mae" in texto_lower:
            perfil["papel"] = "mae"
        elif "pai" in texto_lower:
            perfil["papel"] = "pai"
        elif "respons" in texto_lower:
            perfil["papel"] = "responsavel"
        elif "idos" in texto_lower:
            perfil["papel"] = "idoso"

        estados = [
            "acre", "alagoas", "amapa", "amazonas", "bahia", "ceara", "distrito federal", "espirito santo", "goias",
            "maranhao", "mato grosso", "mato grosso do sul", "minas gerais", "para", "paraiba", "parana",
            "pernambuco", "piaui", "rio de janeiro", "rio grande do norte", "rio grande do sul", "rondonia",
            "roraima", "santa catarina", "sao paulo", "sergipe", "tocantins"
        ]
        siglas = ["ac", "al", "ap", "am", "ba", "ce", "df", "es", "go", "ma", "mt", "ms", "mg", "pa", "pb", "pr",
                  "pe", "pi", "rj", "rn", "rs", "ro", "rr", "sc", "sp", "se", "to"]
        
        # Normaliza brasilia/brasília para distrito federal
        if "brasilia" in texto_lower or "brasília" in texto_lower:
            perfil["localidade"] = "distrito federal"
        else:
            for estado in estados:
                if estado in texto_lower:
                    perfil["localidade"] = estado
                    break
            if "localidade" not in perfil:
                tokens = [t.strip(",. ").lower() for t in texto.split()]
                for t in tokens:
                    if t in siglas:
                        perfil["localidade"] = t
                        break

        if "problema" not in perfil or not perfil.get("problema"):
            if len(partes) >= 2:
                perfil["problema"] = ", ".join(partes[-2:])
            else:
                perfil["problema"] = texto

    return {k: v for k, v in perfil.items() if v}


DOC_KEYWORDS = [
    "cpf", "rg", "identidade", "cin", "sus", "cartao sus", "cartão sus",
    "bolsa", "auxilio", "auxílio", "cadunico", "cadúnico", "passaporte",
    "gov", "gov.br", "imposto", "irpf", "ir", "cnpj", "mei", "empresa"
]


def has_assunto_doc(texto: str) -> bool:
    lower = texto.lower()
    return any(chave in lower for chave in DOC_KEYWORDS)


def contexto_relevante(contexto: str, pergunta: str, eixo: Optional[str]) -> bool:
    """
    Confere se o contexto contém termos do assunto principal (palavras-chave da pergunta ou eixo).
    Evita responder com documentos desconexos (ex.: IRPF para pergunta de CNPJ).
    """
    ctx_lower = contexto.lower()
    pergunta_lower = pergunta.lower()

    termos = {kw for kw in DOC_KEYWORDS if kw in pergunta_lower}
    if eixo:
        eixo_l = eixo.lower()
        if eixo_l == "cpf":
            termos.update(["cpf"])
        elif eixo_l == "rg":
            termos.update(["rg", "identidade", "cin"])
        elif eixo_l == "sus":
            termos.update(["sus", "cartao sus", "cartão sus", "cartao do sus", "sistema unico de saude"])
        elif eixo_l == "bolsa":
            termos.update(["bolsa", "auxilio", "auxílio", "cadunico", "cadúnico"])
        elif eixo_l == "passaporte":
            termos.update(["passaporte"])
        elif eixo_l == "govbr":
            termos.update(["gov", "gov.br"])
        elif eixo_l == "imposto_renda":
            termos.update(["imposto", "irpf", "imposto de renda", "ir"])
        elif eixo_l == "cnpj":
            termos.update(["cnpj", "empresa", "mei", "abertura de empresa"])

    # Se não há termo para checar, não bloqueia
    if not termos:
        return True

    return any(t in ctx_lower for t in termos)


def extrair_perfil_llm(texto: str) -> Dict:
    prompt = f"""
    Extraia dados do perfil a partir do texto do cidadão.
    Campos: nome (primeiro nome), genero (identidade de gênero), papel (mãe, pai, responsável, idoso), idade (número), localidade (estado/UF ou cidade), problema (frase curta do pedido).
    Responda apenas em JSON com chaves: nome, genero, papel, idade, localidade, problema. Use string vazia se não souber.

    Texto: {texto}
    """
    try:
        completion = client_groq.chat.completions.create(
            model=MODELO_IA,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.1,
            top_p=0.1,
        )
        content = completion.choices[0].message.content or "{}"
        data = json.loads(content)
        return {k: v for k, v in data.items() if v}
    except Exception as e:
        print(f"[perfil_llm][erro] {type(e).__name__}: {e}")
        return {}


def detectar_papel_llm(texto: str) -> Optional[str]:
    """
    Usa LLM para detectar se o atendimento é para o próprio usuário ou para alguém da família.
    Retorna: "titular" (para si mesmo) ou "responsavel" (para alguém da família)
    """
    prompt = f"""Analise a resposta do usuário e determine se o atendimento é para ele mesmo ou para alguém da família.

Exemplos de respostas que indicam "para si mesmo" (titular):
- "sou eu", "sou eu mesmo", "é pra mim", "para mim", "pra mim", "eu mesmo", "para mim mesmo", "é para mim", "eu", "para eu", "pra eu"

Exemplos de respostas que indicam "para alguém da família" (responsavel):
- "filho", "filha", "dependente", "para meu filho", "para minha filha", "para alguém da família", "para outro"

Resposta do usuário: "{texto}"

Responda APENAS com uma palavra: "titular" ou "responsavel"
Se não conseguir determinar com certeza, responda "titular".
"""
    try:
        completion = client_groq.chat.completions.create(
            model=MODELO_IA,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.1,
            top_p=0.1,
        )
        content = completion.choices[0].message.content or "titular"
        content = content.strip().lower()
        # Remove possíveis espaços ou pontuação
        content = re.sub(r'[^\w]', '', content)
        if "responsavel" in content or "responsvel" in content:
            return "responsavel"
        return "titular"
    except Exception as e:
        print(f"[detectar_papel_llm][erro] {type(e).__name__}: {e}")
        return None


def preencher_resposta_curta(pergunta: str, perfil: Dict) -> Dict:
    texto = pergunta.strip()
    lower = texto.lower()

    if not perfil.get("nome"):
        tokens = texto.split()
        if len(tokens) == 1 and tokens[0].isalpha():
            perfil["nome"] = tokens[0]

    if not perfil.get("papel"):
        # Detecção melhorada com mais variações
        indicadores_titular = [
            "pra mim", "para mim", "é pra mim", "é para mim", "para mim mesmo", 
            "pra mim mesmo", "sou eu", "sou eu mesmo", "eu mesmo", "eu", 
            "para eu", "pra eu", "para si", "pra si"
        ]
        indicadores_responsavel = [
            "filho", "filha", "dependente", "para meu filho", "para minha filha",
            "para alguém", "para alguem", "para outro", "para outra pessoa"
        ]
        
        # Verifica indicadores simples primeiro
        if any(ind in lower for ind in indicadores_responsavel):
            perfil["papel"] = "responsavel"
        elif any(ind in lower for ind in indicadores_titular):
            perfil["papel"] = "titular"
        else:
            # Se não detectou, usa LLM para detectar
            papel_detectado = detectar_papel_llm(texto)
            if papel_detectado:
                perfil["papel"] = papel_detectado

    if not perfil.get("localidade"):
        # Normaliza brasilia/brasília para distrito federal
        if "brasilia" in lower or "brasília" in lower:
            perfil["localidade"] = "distrito federal"
        else:
            siglas = ["ac", "al", "ap", "am", "ba", "ce", "df", "es", "go", "ma", "mt", "ms",
                      "mg", "pa", "pb", "pr", "pe", "pi", "rj", "rn", "rs", "ro", "rr", "sc", "sp", "se", "to"]
            tokens = [t.strip(",. ").lower() for t in texto.split()]
            for t in tokens:
                if t in siglas:
                    perfil["localidade"] = t
                    break

    return perfil


def resumo_perfil(perfil: Dict) -> str:
    partes = []
    if perfil.get("nome"):
        partes.append(f"nome={perfil['nome']}")
    if perfil.get("localidade"):
        partes.append(f"estado={perfil['localidade']}")
    if perfil.get("papel"):
        partes.append(f"para={perfil['papel']}")
    if perfil.get("intent"):
        partes.append(f"assunto={perfil['intent']}")
    if perfil.get("problema"):
        partes.append(f"pedido={perfil['problema']}")
    if perfil.get("eixo"):
        partes.append(f"eixo={perfil['eixo']}")
    if perfil.get("subtrilha"):
        partes.append(f"subtrilha={perfil['subtrilha']}")
    return ", ".join(partes) if partes else "ainda não tenho dados suficientes."


def resposta_smalltalk(pergunta: str) -> Optional[str]:
    base = pergunta.strip().lower()
    gatilhos = ["oi", "olá", "ola", "bom dia", "boa tarde", "boa noite", "tudo bem", "como vai"]
    if any(base.startswith(g) for g in gatilhos) and not has_assunto_doc(base):
        return "Oi! Posso ajudar com RG, CPF, passaporte ou benefícios como Bolsa Família e SUS. Sobre o que você quer falar?"
    if "obrigado" in base or "valeu" in base:
        return "De nada! Se precisar de mais alguma coisa sobre documentos ou serviços públicos, é só falar."
    return None


def classificar_eixo(texto: str) -> str:
    t = texto.lower()
    if "cnpj" in t:
        return "CNPJ"
    if "cpf" in t:
        return "CPF"
    if "rg" in t or "identidade" in t or "cin" in t:
        return "RG"
    if "sus" in t or "sistema unico de saude" in t or "sistema único de saúde" in t or "cartao sus" in t or "cartão sus" in t:
        return "SUS"
    if "bolsa" in t or "auxilio" in t or "cadunico" in t:
        return "BOLSA"
    if "passaporte" in t:
        return "PASSAPORTE"
    if "gov" in t or "gov.br" in t:
        return "GOVBR"
    if "imposto" in t or "irpf" in t or "ir" in t:
        return "IMPOSTO_RENDA"
    return "OUTRO"


def classificar_subtrilha(texto: str) -> Optional[str]:
    t = texto.lower()
    if "bloque" in t or "cort" in t or "parou" in t:
        return "bloqueado"
    if "pend" in t or "diverg" in t:
        return "pendencia"
    if "primeira" in t or "primeiro" in t or "emitir" in t or "tirar" in t:
        return "emissao"
    if "renovar" in t or "segunda" in t or "2a via" in t:
        return "segunda_via"
    return None


app = FastAPI(title="Assistente Cidadão", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/ingest")
def ingest():
    processar_arquivos()
    return {"status": "ingestao_disparada"}


@app.post("/session")
def set_session(payload: SessionRequest):
    session_store.upsert(payload.session_id, payload.perfil.model_dump())
    return {"status": "perfil_atualizado"}


@app.post("/transcribe")
async def transcribe(file: UploadFile = File(...)):
    try:
        if not os.getenv("GOOGLE_APPLICATION_CREDENTIALS"):
            return JSONResponse(status_code=500, content={"detail": "GOOGLE_APPLICATION_CREDENTIALS não configurada para Speech-to-Text."})

        audio_bytes = await file.read()
        if not audio_bytes:
            return JSONResponse(status_code=400, content={"detail": "Arquivo de áudio vazio."})

        mime = (file.content_type or "").lower()
        print(f"[transcribe] mime={mime}, size_bytes={len(audio_bytes)}")

        encoding_map = {
            "audio/webm": speech.RecognitionConfig.AudioEncoding.WEBM_OPUS,
            "audio/ogg": speech.RecognitionConfig.AudioEncoding.OGG_OPUS,
            "audio/opus": speech.RecognitionConfig.AudioEncoding.OGG_OPUS,
            "audio/wav": speech.RecognitionConfig.AudioEncoding.LINEAR16,
            "audio/x-wav": speech.RecognitionConfig.AudioEncoding.LINEAR16,
            "audio/flac": speech.RecognitionConfig.AudioEncoding.FLAC,
            "audio/mpeg": speech.RecognitionConfig.AudioEncoding.MP3,
            "audio/mp3": speech.RecognitionConfig.AudioEncoding.MP3,
        }

        encoding = encoding_map.get(mime)
        if encoding is None:
            return JSONResponse(status_code=400, content={"detail": f"Formato de áudio não suportado: {mime}. Use webm/ogg opus, wav, flac ou mp3."})

        client_speech = speech.SpeechClient()
        audio = speech.RecognitionAudio(content=audio_bytes)
        sample_rate = 48000 if encoding in (speech.RecognitionConfig.AudioEncoding.WEBM_OPUS, speech.RecognitionConfig.AudioEncoding.OGG_OPUS) else None
        config = speech.RecognitionConfig(
            encoding=encoding,
            language_code="pt-BR",
            enable_automatic_punctuation=True,
            audio_channel_count=1,
            sample_rate_hertz=sample_rate,
        )
        response = client_speech.recognize(config=config, audio=audio)
        textos = [result.alternatives[0].transcript for result in response.results if result.alternatives]
        texto_final = " ".join(textos).strip()

        if not texto_final:
            print(f"[transcribe] resposta vazia do Speech. response={response}")
            return JSONResponse(status_code=500, content={"detail": "Transcrição vazia retornada pelo Speech-to-Text."})

        return {"text": texto_final}
    except Exception as e:
        print(f"[transcribe][erro] {type(e).__name__}: {e}")
        return JSONResponse(status_code=500, content={"detail": f"Erro na transcrição: {type(e).__name__}: {e}"})


@app.post("/chat")
def chat(payload: ChatRequest):
    pergunta = (payload.transcricao or payload.pergunta).strip()

    if not pergunta:
        return JSONResponse(status_code=400, content={"detail": "Pergunta vazia"})

    perfil_dict: Dict = {}
    hist: list = []
    if payload.session_id:
        armazenado = session_store.get(payload.session_id)
        if armazenado:
            hist = armazenado.get("history", [])
            perfil_dict = {k: v for k, v in armazenado.items() if k != "history"}

    mensagens_recentes = (hist + [pergunta])[-5:]

    def salvar_sessao():
        if payload.session_id:
            dados = dict(perfil_dict)
            dados["history"] = mensagens_recentes
            session_store.upsert(payload.session_id, dados)

    # Fallback seguro para perguntas estranhas sobre nome (se não houver nome salvo)
    if "qual" in pergunta.lower() and "meu nome" in pergunta.lower():
        # nome salvo?
        sess_nome = perfil_dict.get("nome")
        if sess_nome:
            return {"answer": f"Você me disse que seu nome é {sess_nome}."}
        return {"answer": "Eu não vejo seu nome automaticamente. Posso ajudar com RG, CPF ou Bolsa Família se você quiser."}

    resposta_gentil = resposta_smalltalk(pergunta)
    if resposta_gentil:
        salvar_sessao()
        return {"answer": resposta_gentil}

    if pergunta.lower() in ["só isso", "so isso", "mais nada", "acabou?"]:
        salvar_sessao()
        return {"answer": "Posso detalhar prazos, taxas, documentos ou onde ir no seu estado. O que mais você precisa?"}

    if payload.perfil:
        perfil_dict.update({k: v for k, v in payload.perfil.model_dump().items() if v})
        salvar_sessao()

    # Classifica eixo/subtrilha quando a mensagem tem assunto claro; evita marcar "OUTRO" em respostas curtas tipo "sim"
    pergunta_lower = pergunta.lower().strip()
    palavras_msg = pergunta_lower.split()
    respostas_curta = {"sim", "ok", "blz", "beleza", "certo", "isso", "ss", "s", "nao", "não"}
    tem_assunto_claro = any(
        chave in pergunta_lower
        for chave in ["cpf", "rg", "sus", "bolsa", "auxilio", "cadunico", "passaporte", "gov", "imposto"]
    ) or len(palavras_msg) >= 3 or (len(palavras_msg) >= 2 and not all(p in respostas_curta for p in palavras_msg))

    trocar_assunto = any(frase in pergunta_lower for frase in ["outro assunto", "agora outro", "mudar de assunto"])
    eixo_detectado = classificar_eixo(pergunta) if tem_assunto_claro else None
    subtrilha_detectada = classificar_subtrilha(pergunta) if tem_assunto_claro else None

    if eixo_detectado and (trocar_assunto or not perfil_dict.get("eixo")):
        perfil_dict["eixo"] = eixo_detectado
    if subtrilha_detectada and not perfil_dict.get("subtrilha"):
        perfil_dict["subtrilha"] = subtrilha_detectada

    if not perfil_dict.get("intent") and tem_assunto_claro:
        perfil_dict["intent"] = pergunta
    salvar_sessao()

    # Tenta preencher perfil com detecção automática
    if not all(perfil_dict.get(campo) for campo in ["nome", "genero", "papel", "idade", "problema", "localidade"]):
        auto = tentar_preencher_perfil_livre(pergunta)
        if auto:
            perfil_dict.update(auto)
            salvar_sessao()

    # Tenta extrair campos com LLM se ainda faltar
    if not all(perfil_dict.get(campo) for campo in ["nome", "genero", "papel", "idade", "problema", "localidade"]):
        llm_extra = extrair_perfil_llm(pergunta)
        if llm_extra:
            for k, v in llm_extra.items():
                if v and not perfil_dict.get(k):
                    perfil_dict[k] = v
            salvar_sessao()

    # Preenche campos simples
    perfil_dict = preencher_resposta_curta(pergunta, perfil_dict)
    salvar_sessao()

    if not perfil_dict.get("problema"):
        perfil_dict["problema"] = pergunta
    if not perfil_dict.get("intent") and tem_assunto_claro:
        perfil_dict["intent"] = pergunta
    salvar_sessao()

    # Perguntas sobre dados do perfil
    lower = pergunta.lower()
    if "meus dados" in lower or "que dados" in lower:
        salvar_sessao()
        return {"answer": f"Você me contou: {resumo_perfil(perfil_dict)}"}
    if "meu nome" in lower and perfil_dict.get("nome"):
        salvar_sessao()
        return {"answer": f"Você me disse que seu nome é {perfil_dict.get('nome')}. Posso seguir na orientação?"}

    # Monta bloco de perfil apenas com campos preenchidos (sem bloquear fluxo se faltar algo)
    partes_perfil = []
    if perfil_dict.get('nome'):
        partes_perfil.append(f"Nome: {perfil_dict.get('nome')}")
    if perfil_dict.get('localidade'):
        partes_perfil.append(f"Localidade: {perfil_dict.get('localidade')}")
    if perfil_dict.get('papel'):
        partes_perfil.append(f"Situação: {perfil_dict.get('papel')}")
    if perfil_dict.get('eixo'):
        partes_perfil.append(f"Assunto: {perfil_dict.get('eixo')}")
    
    bloco_perfil = ""
    if partes_perfil:
        bloco_perfil = "INFORMAÇÕES DO USUÁRIO:\n- " + "\n- ".join(partes_perfil) + "\n\n"

    faltando = []
    if not perfil_dict.get("localidade"):
        faltando.append("Localidade não informada (responder de forma geral).")
    if not perfil_dict.get("papel"):
        faltando.append("Papel não informado (se é para você ou dependente).")
    if not perfil_dict.get("nome"):
        faltando.append("Nome não informado.")
    if faltando:
        bloco_perfil += "DADOS FALTANTES PARA PERSONALIZAR MELHOR:\n- " + "\n- ".join(faltando) + "\n\n"

    if mensagens_recentes:
        bloco_perfil += "HISTÓRICO RECENTE (últimas 5 mensagens):\n- " + "\n- ".join(mensagens_recentes) + "\n\n"

    resposta_fixa = buscar_resposta_fixa(pergunta)
    if resposta_fixa:
        salvar_sessao()
        return {"answer": resposta_fixa}

    # Monta query de busca melhorada combinando pergunta atual com contexto da conversa
    query_busca = pergunta
    
    # Se a pergunta atual parece ser uma resposta (curta, sem verbo de ação), 
    # combina com o intent/eixo anterior ou histórico recente
    palavras_pergunta = pergunta_lower.split()
    historico_para_busca = " ".join(mensagens_recentes)
    
    # Se a pergunta é muito curta (1-2 palavras) e há um intent/eixo salvo ou histórico,
    # provavelmente é uma resposta a uma pergunta anterior
    if len(palavras_pergunta) <= 2 and (perfil_dict.get("intent") or perfil_dict.get("eixo") or historico_para_busca):
        termos_contexto = []
        if perfil_dict.get("eixo"):
            termos_contexto.append(perfil_dict.get("eixo"))
        if perfil_dict.get("intent") and len(perfil_dict.get("intent", "").split()) > 2:
            termos_contexto.append(perfil_dict.get("intent"))
        if historico_para_busca:
            termos_contexto.append(historico_para_busca)
        
        if termos_contexto:
            query_busca = f"{' '.join(termos_contexto)} {pergunta}"
    
    # Adiciona localidade à busca se disponível
    if perfil_dict.get("localidade") and perfil_dict.get("localidade") not in query_busca.lower():
        # Normaliza localidade
        localidade = perfil_dict.get("localidade").lower()
        if localidade == "brasilia" or localidade == "brasília":
            localidade = "distrito federal"
        query_busca = f"{query_busca} {localidade}"
    
    # Busca contexto com query melhorada
    contexto = buscar_contexto(query_busca, session_id=payload.session_id)
    
    # Se não encontrou, tenta buscar apenas com o eixo/intent
    if (not contexto or contexto.strip() == "") and perfil_dict.get("eixo"):
        contexto = buscar_contexto(perfil_dict.get("eixo"), session_id=payload.session_id)
    
    # Se ainda não encontrou, tenta com a pergunta original
    if (not contexto or contexto.strip() == "") and query_busca != pergunta:
        contexto = buscar_contexto(pergunta, session_id=payload.session_id)

    # Valida se o contexto achado tem relação com o assunto; se não, descarta para evitar resposta nada a ver
    if contexto and not contexto_relevante(contexto, pergunta, perfil_dict.get("eixo")):
        contexto = ""
    
    # Se não houver contexto, retorna mensagem clara
    if not contexto or contexto.strip() == "":
        return {"answer": "Não encontrei informações sobre isso nos documentos disponíveis. Pode reformular sua pergunta ou fornecer mais detalhes sobre o que precisa?"}
    
    # Gera links do Google Maps APENAS se houver pedido EXPLÍCITO de localização
    # Não gera links para perguntas gerais como "como tirar cpf"
    pergunta_lower = pergunta.lower()
    contexto_lower = contexto.lower() if contexto else ""
    pergunta_norm = unicodedata.normalize("NFKD", pergunta_lower).encode("ascii", "ignore").decode("ascii")
    
    # Indicadores de pedido EXPLÍCITO de localização (mais restritivo)
    pedidos_explicitos = [
        "me manda", "manda a", "envie a", "mostra a", "me mostra",
        "localização", "localizacao", "endereço", "endereco",
        "próximo", "proximo", "mais próximo", "perto", "mais perto",
        "onde fica", "onde está", "qual endereço", "qual o endereço"
    ]
    
    # Verifica se há pedido EXPLÍCITO na pergunta ou no contexto
    tem_pedido_explicito = any(termo in pergunta_lower for termo in pedidos_explicitos)
    pedidos_explicitos_norm = [
        unicodedata.normalize("NFKD", termo.lower()).encode("ascii", "ignore").decode("ascii")
        for termo in pedidos_explicitos
    ]
    pedidos_extras_norm = ["localiza", "localiz", "locaz", "loca", "onde fica", "onde esta", "onde ta"]
    if not tem_pedido_explicito:
        tem_pedido_explicito = any(
            termo in pergunta_norm for termo in pedidos_explicitos_norm + pedidos_extras_norm
        )
    
    # Só gera links se houver pedido EXPLÍCITO
    links_maps = []
    if tem_pedido_explicito:
        # Combina pergunta com contexto para melhor detecção do órgão
        pergunta_com_contexto = pergunta
        if perfil_dict.get("eixo"):
            pergunta_com_contexto = f"{pergunta} {perfil_dict.get('eixo')}"
        if perfil_dict.get("intent"):
            pergunta_com_contexto = f"{pergunta_com_contexto} {perfil_dict.get('intent')}"
        
        links_maps = gerar_links_orgaos(pergunta_com_contexto, perfil_dict.get("localidade"), forcar_geracao=True)
        
        # Se não gerou links mas há eixo no perfil, tenta gerar baseado no eixo
        if not links_maps and perfil_dict.get("eixo"):
            eixo = perfil_dict.get("eixo").lower()
            pergunta_artificial = f"{perfil_dict.get('eixo')} {pergunta}"
            links_maps = gerar_links_orgaos(pergunta_artificial, perfil_dict.get("localidade"), forcar_geracao=True)
    
    bloco_links = ""
    if links_maps:
        links_texto = []
        for link_info in links_maps:
            links_texto.append(f"{link_info['nome']}: {link_info['link']}")
        bloco_links = "\n\nLINKS DO GOOGLE MAPS PARA ENCONTRAR OS ÓRGÃOS:\n" + "\n".join(links_texto) + "\n"
    
    contexto_final = f"{bloco_perfil}DADOS DOS DOCUMENTOS:\n{contexto}{bloco_links}"
    
    # Obtém e formata o histórico da conversa
    historico_formatado = ""
    if payload.session_id:
        historico = session_store.obter_historico(payload.session_id, max_mensagens=8)
        if historico:
            historico_formatado = formatar_historico_conversa(historico, max_chars=1500)

    # Classe para acumular resposta durante streaming
    class AcumuladorResposta:
        def __init__(self):
            self.texto = ""
        
        def adicionar(self, pedaco: str):
            self.texto += pedaco

    acumulador = AcumuladorResposta()

    def responder_stream():
        for pedaco in stream_resposta(pergunta, contexto_final, historico_formatado):
            acumulador.adicionar(pedaco)
            yield pedaco
        
        # Após terminar de gerar a resposta, salva no histórico
        if payload.session_id and acumulador.texto:
            session_store.adicionar_mensagem(payload.session_id, pergunta, acumulador.texto)

    salvar_sessao()
    return StreamingResponse(responder_stream(), media_type="text/plain")
