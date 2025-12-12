from banco_dados import obter_colecao_usuario, colecao_global
from resposta_ia import gerar_resposta
from verificador_base_fixa import buscar_resposta_fixa

def buscar_contexto(pergunta, session_id: str = None, combinar_global: bool = True):
    """
    Busca contexto no banco vetorial.
    
    Args:
        pergunta: Pergunta do usuário
        session_id: ID da sessão do usuário (opcional)
        combinar_global: Se True, combina resultados da coleção global e do usuário
    
    Returns:
        str: Contexto encontrado
    """
    contexto_parts = []
    
    try:
        # Aumenta número de resultados para melhor cobertura
        n_results = 5
        
        # Busca na coleção do usuário (se houver session_id)
        if session_id:
            colecao_usuario = obter_colecao_usuario(session_id)
            resultados_usuario = colecao_usuario.query(
                query_texts=[pergunta],
                n_results=n_results
            )
            
            if resultados_usuario["documents"] and resultados_usuario["documents"][0]:
                contexto_parts.extend(resultados_usuario["documents"][0])
        
        # Busca na coleção global (documentos base)
        if combinar_global or not session_id:
            resultados_global = colecao_global.query(
                query_texts=[pergunta],
                n_results=n_results
            )
            
            if resultados_global["documents"] and resultados_global["documents"][0]:
                contexto_parts.extend(resultados_global["documents"][0])
        
        # Remove duplicatas mantendo ordem
        contexto_unico = []
        visto = set()
        for doc in contexto_parts:
            if doc not in visto:
                contexto_unico.append(doc)
                visto.add(doc)
        
        if contexto_unico:
            return "\n---\n".join(contexto_unico)
        
        # Log para debug
        print(f"[buscar_contexto] Nenhum resultado encontrado para: {pergunta}")

    except Exception as e:
        print(f"[buscar_contexto] Erro na busca: {e}")

    return ""

def responder(pergunta):
    # 🔹 1. Tenta base fixa
    resposta_fixa = buscar_resposta_fixa(pergunta)
    if resposta_fixa:
        print("\nIA:", resposta_fixa)
        return

    # 🔹 2. Fallback para RAG
    contexto = buscar_contexto(pergunta)
    gerar_resposta(pergunta, contexto)
