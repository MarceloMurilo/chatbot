import os
from pypdf import PdfReader
from docx import Document
from config import PASTA_DOCUMENTOS
from banco_dados import colecao_global

def dividir_texto(texto, tamanho_chunk=1000, overlap=200):
    chunks = []
    inicio = 0

    while inicio < len(texto):
        fim = inicio + tamanho_chunk
        chunks.append(texto[inicio:fim])
        inicio += tamanho_chunk - overlap

    return chunks

def extrair_texto(caminho_arquivo):
    extensao = os.path.splitext(caminho_arquivo)[1].lower()

    try:
        if extensao == ".pdf":
            leitor = PdfReader(caminho_arquivo)
            return "\n".join(
                [p.extract_text() for p in leitor.pages if p.extract_text()]
            )

        if extensao == ".docx":
            doc = Document(caminho_arquivo)
            return "\n".join(p.text for p in doc.paragraphs)

        if extensao == ".txt":
            with open(caminho_arquivo, "r", encoding="utf-8") as f:
                return f.read()

    except Exception as e:
        print(f"Erro ao ler {caminho_arquivo}: {e}")

    return None

def processar_arquivos():
    """
    Processa todos os arquivos na pasta de documentos e os adiciona ao banco vetorial.
    """
    if not os.path.exists(PASTA_DOCUMENTOS):
        os.makedirs(PASTA_DOCUMENTOS, exist_ok=True)
        print(f"[ingesta] Pasta criada: {PASTA_DOCUMENTOS}")
        print("[ingesta] Adicione arquivos e tente novamente.")
        return

    arquivos = [
        f for f in os.listdir(PASTA_DOCUMENTOS)
        if f.endswith((".txt", ".pdf", ".docx"))
    ]

    if not arquivos:
        print(f"[ingesta] ⚠️ Nenhum arquivo encontrado em {PASTA_DOCUMENTOS}")
        return

    print(f"[ingesta] Encontrados {len(arquivos)} arquivo(s) para processar")
    total_chunks = 0

    for nome in arquivos:
        caminho = os.path.join(PASTA_DOCUMENTOS, nome)
        print(f"[ingesta] Processando: {nome}")
        texto = extrair_texto(caminho)

        if not texto:
            print(f"[ingesta] ⚠️ Não foi possível extrair texto de {nome}")
            continue

        if len(texto.strip()) == 0:
            print(f"[ingesta] ⚠️ Arquivo {nome} está vazio")
            continue

        chunks = dividir_texto(texto)
        ids = [f"{nome}_part_{i}" for i in range(len(chunks))]
        metadados = [{"origem": nome, "parte": i} for i in range(len(chunks))]

        try:
            colecao_global.upsert(
                documents=chunks,
                ids=ids,
                metadatas=metadados
            )
            total_chunks += len(chunks)
            print(f"[ingesta] ✅ {nome}: {len(chunks)} chunks salvos ({len(texto)} caracteres)")
        except Exception as e:
            print(f"[ingesta] ❌ Erro ao salvar {nome}: {e}")
            import traceback
            traceback.print_exc()

    print(f"[ingesta] ✅ Ingestão finalizada. Total: {total_chunks} chunks processados")
