import threading
from typing import Dict, Optional, List, Tuple


class SessionStore:
    """
    Armazena perfis de sessão em memória (não persistente).
    Estrutura simples para protótipo; para produção, usar Redis ou banco.
    """

    def __init__(self) -> None:
        self._data: Dict[str, Dict] = {}
        self._lock = threading.Lock()

    def upsert(self, session_id: str, perfil: Dict) -> None:
        with self._lock:
            self._data[session_id] = perfil

    def get(self, session_id: str) -> Optional[Dict]:
        with self._lock:
            return self._data.get(session_id)
    
    def adicionar_mensagem(self, session_id: str, pergunta: str, resposta: str) -> None:
        """
        Adiciona uma mensagem (pergunta + resposta) ao histórico da sessão.
        """
        with self._lock:
            if session_id not in self._data:
                self._data[session_id] = {}
            
            if "conversa" not in self._data[session_id]:
                self._data[session_id]["conversa"] = []
            
            # Adiciona a nova mensagem
            self._data[session_id]["conversa"].append({
                "pergunta": pergunta,
                "resposta": resposta
            })
            
            # Limita o histórico a 20 mensagens (10 turnos de conversa)
            if len(self._data[session_id]["conversa"]) > 20:
                self._data[session_id]["conversa"] = self._data[session_id]["conversa"][-20:]
    
    def obter_historico(self, session_id: str, max_mensagens: int = 10) -> List[Tuple[str, str]]:
        """
        Retorna o histórico de mensagens da sessão.
        
        Args:
            session_id: ID da sessão
            max_mensagens: Número máximo de mensagens a retornar (padrão: 10)
        
        Returns:
            Lista de tuplas (pergunta, resposta)
        """
        with self._lock:
            if session_id not in self._data:
                return []
            
            conversa = self._data[session_id].get("conversa", [])
            # Retorna as últimas N mensagens
            conversa_recente = conversa[-max_mensagens:] if len(conversa) > max_mensagens else conversa
            
            return [(msg["pergunta"], msg["resposta"]) for msg in conversa_recente]


session_store = SessionStore()
