import os
import chromadb
from groq import Groq
from dotenv import load_dotenv
from pypdf import PdfReader
from docx import Document

# --- CONFIGURAÇÕES GERAIS ---
load_dotenv() # Carrega sua GROQ_API_KEY do arquivo .env
PASTA_DOCUMENTS = "./documentos"

# Modelo recomendado para Groq (Rápido e bom em Português)
MODELO_IA = "openai/gpt-oss-120b" 

# Inicialização dos Clientes
client_groq = Groq(api_key=os.environ.get("GROQ_API_KEY"))

# Inicializa ChromaDB (Banco de dados vetorial local)
client_chroma = chromadb.PersistentClient(path="./banco_vetorial")
colecao = client_chroma.get_or_create_collection(name="conhecimento_empresa")

# --- HELPER: DIVISÃO DE TEXTO (A CORREÇÃO PRINCIPAL) ---
def dividir_texto(texto, tamanho_chunk=1000, overlap=200):
    """
    Divide o texto em pedaços (chunks) com sobreposição.
    
    Args:
        texto: O conteúdo completo do arquivo.
        tamanho_chunk: Tamanho máximo de caracteres por pedaço (1000 evita erro de limite).
        overlap: Quantos caracteres repetir entre pedaços (200 evita cortar frases ao meio).
    """
    chunks = []
    inicio = 0
    
    # Loop de "janela deslizante"
    while inicio < len(texto):
        fim = inicio + tamanho_chunk
        chunks.append(texto[inicio:fim])
        
        # Avança o cursor, mas volta um pouco (overlap) para manter contexto
        inicio += tamanho_chunk - overlap
        
    return chunks

# --- MÓDULO 1: LEITURA DE ARQUIVOS ---
def extrair_texto(caminho_arquivo):
    """Detecta a extensão e retorna o texto bruto do arquivo."""
    extensao = os.path.splitext(caminho_arquivo)[1].lower()
    
    try:
        if extensao == ".pdf":
            leitor = PdfReader(caminho_arquivo)
            texto = ""
            for pag in leitor.pages:
                texto_pag = pag.extract_text()
                if texto_pag:
                    texto += texto_pag + "\n"
            return texto
            
        elif extensao == ".docx":
            doc = Document(caminho_arquivo)
            return "\n".join([p.text for p in doc.paragraphs])
            
        elif extensao == ".txt":
            with open(caminho_arquivo, 'r', encoding='utf-8') as f:
                return f.read()
                
    except Exception as e:
        print(f"Erro ao ler {caminho_arquivo}: {e}")
        
    return None

# --- MÓDULO 2: BANCO DE DADOS (INGESTÃO COM CHUNKING) ---
def processar_arquivos():
    """Lê arquivos, divide em chunks inteligentes e salva no ChromaDB."""
    print(f"\n--- Processando arquivos em '{PASTA_DOCUMENTS}' ---")
    
    if not os.path.exists(PASTA_DOCUMENTS):
        os.makedirs(PASTA_DOCUMENTS)
        print(f"Pasta '{PASTA_DOCUMENTS}' criada. Coloque seus arquivos lá e tente novamente.")
        return

    arquivos = [f for f in os.listdir(PASTA_DOCUMENTS) if f.endswith(('.txt', '.pdf', '.docx'))]

    if not arquivos:
        print("Nenhum arquivo compatível encontrado na pasta.")
        return

    novos_chunks_total = 0

    for nome_arquivo in arquivos:
        caminho = os.path.join(PASTA_DOCUMENTS, nome_arquivo)
        print(f"Lendo: {nome_arquivo}...")
        conteudo_total = extrair_texto(caminho)
        
        if conteudo_total:
            # 1. Aplicamos a divisão do texto com overlap
            pedacos = dividir_texto(conteudo_total, tamanho_chunk=1000, overlap=200)
            
            # 2. Preparamos IDs únicos e Metadados para cada pedaço
            ids_pedacos = [f"{nome_arquivo}_part_{i}" for i in range(len(pedacos))]
            metadatas_pedacos = [{"origem": nome_arquivo, "parte": i} for i in range(len(pedacos))]
            
            # 3. Salvamos no banco
            colecao.upsert(
                documents=pedacos,
                ids=ids_pedacos,
                metadatas=metadatas_pedacos
            )
            print(f"  -> Salvo: {len(pedacos)} chunks criados.")
            novos_chunks_total += len(pedacos)
            
    print(f"--- Ingestão concluída! Total de {novos_chunks_total} novos fragmentos memorizados. ---")

# --- MÓDULO 3: O RAG (BUSCA + GERAÇÃO) ---
def buscar_contexto(pergunta):
    """Busca os 3 trechos mais relevantes no banco."""
    try:
        resultados = colecao.query(query_texts=[pergunta], n_results=3)
        if resultados['documents'] and len(resultados['documents'][0]) > 0:
            # Junta os documentos encontrados em um único texto
            return "\n---\n".join(resultados['documents'][0])
    except Exception as e:
        print(f"Erro na busca: {e}")
    return ""

def gerar_resposta(pergunta, contexto):
    """Monta o prompt e chama a API da Groq."""
    
    if not contexto:
        print("⚠️  Aviso: Não encontrei informações relevantes nos documentos. A IA pode alucinar.")
        contexto = "Nenhuma informação específica encontrada nos documentos fornecidos."

    prompt = f"""
    Você é um especialista e assistente da empresa. 
    Use APENAS o contexto abaixo para responder à pergunta do usuário.
    Se a resposta não estiver no contexto, diga educadamente que o documento não menciona isso.
    
    CONTEXTO RECUPERADO DOS ARQUIVOS:
    {contexto}

    PERGUNTA DO USUÁRIO:
    {pergunta}
    """

    try:
        stream = client_groq.chat.completions.create(
            model=MODELO_IA,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.3, # Baixa temperatura para ser mais fiel aos dados
            top_p=0.1,
            reasoning_effort="medium",
            stream=True
        )

        print("\n🤖 IA: ", end="")
        for chunk in stream:
            print(chunk.choices[0].delta.content or "", end="")
        print("\n")
        
    except Exception as e:
        print(f"\nErro de conexão com a Groq: {e}")

# --- MÓDULO 4: INTERFACE DE USUÁRIO ---
def iniciar_chat():
    print("\n--- Chat Iniciado (Digite 'sair' para voltar ao menu) ---")
    while True:
        pergunta = input("\nVocê: ")
        if pergunta.lower() in ["sair", "exit"]:
            break
            
        print("🔍 Consultando banco de dados...")
        contexto = buscar_contexto(pergunta)
        
        # Opcional: Mostra o contexto recuperado (bom para debug)
        # print(f"[DEBUG - Contexto usado]: {contexto[:200]}...") 
        
        gerar_resposta(pergunta, contexto)

if __name__ == "__main__":
    while True:
        print("\n=== SISTEMA RAG (CHROMA + GROQ) ===")
        print("1. Processar Arquivos (Atualizar Memória)")
        print("2. Conversar")
        print("3. Sair")
        
        opcao = input("Escolha: ")
        
        if opcao == "1":
            processar_arquivos()
        elif opcao == "2":
            iniciar_chat()
        elif opcao == "3":
            print("Encerrando...")
            break
        else:
            print("Opção inválida.")