import chromadb
from config import PASTA_BANCO_VETORIAL

client_chroma = chromadb.PersistentClient(
    path=PASTA_BANCO_VETORIAL
)

# Coleção global para documentos base
colecao_global = client_chroma.get_or_create_collection(
    name="conhecimento_empresa"
)

def obter_colecao_usuario(session_id: str = None):
    """
    Retorna a coleção específica do usuário baseada no session_id.
    Se session_id não for fornecido, retorna a coleção global.
    
    Args:
        session_id: ID da sessão do usuário
        
    Returns:
        Collection: Coleção do ChromaDB para o usuário específico
    """
    if not session_id:
        return colecao_global
    
    # Cria uma coleção única para cada usuário
    nome_colecao = f"usuario_{session_id}"
    return client_chroma.get_or_create_collection(
        name=nome_colecao
    )

def adicionar_documento_usuario(session_id: str, documento: str, metadados: dict = None, doc_id: str = None):
    """
    Adiciona um documento à coleção específica do usuário.
    
    Args:
        session_id: ID da sessão do usuário
        documento: Texto do documento a ser adicionado
        metadados: Metadados opcionais para o documento
        doc_id: ID opcional para o documento (se não fornecido, será gerado)
    
    Returns:
        bool: True se adicionado com sucesso
    """
    try:
        colecao_usuario = obter_colecao_usuario(session_id)
        
        if not doc_id:
            import uuid
            doc_id = f"doc_{uuid.uuid4().hex[:8]}"
        
        if not metadados:
            metadados = {}
        
        colecao_usuario.upsert(
            documents=[documento],
            ids=[doc_id],
            metadatas=[metadados]
        )
        
        return True
    except Exception as e:
        print(f"Erro ao adicionar documento do usuário: {e}")
        return False

# Mantém compatibilidade com código antigo
colecao = colecao_global
