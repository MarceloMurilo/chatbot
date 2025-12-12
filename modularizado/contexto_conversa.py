"""
Módulo para gerenciar contexto de conversa com janela deslizante (sliding window).
"""
from typing import List, Tuple, Optional


def formatar_historico_conversa(historico: List[Tuple[str, str]], max_chars: int = 2000) -> str:
    """
    Formata o histórico de conversa em um texto legível, limitando o tamanho.
    Usa janela deslizante: mantém as mensagens mais recentes que cabem no limite.
    
    Args:
        historico: Lista de tuplas (pergunta, resposta)
        max_chars: Número máximo de caracteres no histórico formatado
    
    Returns:
        String formatada com o histórico da conversa
    """
    if not historico:
        return ""
    
    # Formata cada mensagem
    mensagens_formatadas = []
    tamanho_total = 0
    
    # Começa pelas mensagens mais recentes e vai adicionando até o limite
    for pergunta, resposta in reversed(historico):
        mensagem = f"Usuario: {pergunta}\nAssistente: {resposta}\n---\n"
        tamanho_mensagem = len(mensagem)
        
        # Se adicionar esta mensagem ultrapassar o limite, para
        if tamanho_total + tamanho_mensagem > max_chars and mensagens_formatadas:
            break
        
        mensagens_formatadas.insert(0, mensagem)
        tamanho_total += tamanho_mensagem
    
    if not mensagens_formatadas:
        return ""
    
    # Adiciona cabeçalho
    cabecalho = "HISTORICO DA CONVERSA (mensagens anteriores):\n"
    texto_final = cabecalho + "".join(mensagens_formatadas)
    
    return texto_final


def extrair_resumo_conversa(historico: List[Tuple[str, str]]) -> str:
    """
    Extrai um resumo das informações importantes da conversa.
    Útil para incluir no contexto quando o histórico completo é muito longo.
    
    Args:
        historico: Lista de tuplas (pergunta, resposta)
    
    Returns:
        String com resumo da conversa
    """
    if not historico:
        return ""
    
    # Extrai informações-chave das últimas mensagens
    temas = []
    localidades = []
    documentos = []
    
    for pergunta, resposta in historico[-5:]:  # Últimas 5 mensagens
        pergunta_lower = pergunta.lower()
        
        # Detecta documentos mencionados
        if "cpf" in pergunta_lower:
            documentos.append("CPF")
        if "cnh" in pergunta_lower or "habilitacao" in pergunta_lower:
            documentos.append("CNH")
        if "rg" in pergunta_lower or "identidade" in pergunta_lower:
            documentos.append("RG")
        if "passaporte" in pergunta_lower:
            documentos.append("Passaporte")
        if "cnpj" in pergunta_lower:
            documentos.append("CNPJ")
        
        # Detecta localidades
        estados = ["maranhao", "para", "sao paulo", "rio de janeiro", "minas gerais", 
                   "bahia", "ceara", "parana", "rio grande do sul", "santa catarina"]
        for estado in estados:
            if estado in pergunta_lower:
                localidades.append(estado.title())
                break
    
    resumo_partes = []
    if documentos:
        resumo_partes.append(f"Documentos mencionados: {', '.join(set(documentos))}")
    if localidades:
        resumo_partes.append(f"Localidades mencionadas: {', '.join(set(localidades))}")
    
    if resumo_partes:
        return "CONTEXTO DA CONVERSA: " + " | ".join(resumo_partes)
    
    return ""

