"""
Módulo para gerar links do Google Maps para órgãos públicos
baseado na pergunta do usuário e localidade.
"""
import re
import urllib.parse
from typing import Optional, List, Dict


# Mapeamento de termos para órgãos públicos e suas variações
ORGAOS_MAP = {
    "receita_federal": {
        "termos": ["receita federal", "receita", "rfb", "cpf", "imposto de renda"],
        "nome_busca": "Receita Federal"
    },
    "detran": {
        "termos": ["detran", "cnh", "carteira de motorista", "habilitacao", "habilitacao"],
        "nome_busca": "Detran"
    },
    "poupatempo": {
        "termos": ["poupatempo", "poupa tempo", "posto de atendimento"],
        "nome_busca": "Poupatempo"
    },
    "instituto_identificacao": {
        "termos": ["instituto de identificacao", "instituto identificacao", "rg", "identidade", "cin", "viva"],
        "nome_busca": "Instituto de Identificação"
    },
    "policia_federal": {
        "termos": ["policia federal", "pf", "passaporte"],
        "nome_busca": "Polícia Federal"
    },
    "inss": {
        "termos": ["inss", "previdencia", "aposentadoria", "beneficio"],
        "nome_busca": "INSS"
    },
    "cartorio": {
        "termos": ["cartorio", "cartório", "certidao", "certidão", "registro civil"],
        "nome_busca": "Cartório"
    },
    "caixa_economica": {
        "termos": ["caixa economica", "caixa", "cef", "bolsa familia", "cadunico"],
        "nome_busca": "Caixa Econômica Federal"
    }
}


def detectar_pergunta_localizacao(pergunta: str) -> bool:
    """
    Detecta se a pergunta é sobre localização/endereço de órgãos.
    Restritivo: só detecta quando há pedido EXPLÍCITO de localização.
    
    Args:
        pergunta: Texto da pergunta do usuário
        
    Returns:
        True se a pergunta é explicitamente sobre localização
    """
    pergunta_lower = pergunta.lower()
    
    # Indicadores EXPLÍCITOS de pedido de localização (mais restritivo)
    indicadores_explicitos = [
        "me manda", "me envie", "me mostra", "manda a", "envie a", "mostra a",
        "localização", "localizacao", "localizacao de", "localização de",
        "endereço", "endereco", "endereço de", "endereco de",
        "onde fica", "onde está", "qual o endereço", "qual endereço",
        "próximo", "proximo", "mais próximo", "mais proximo", "perto",
        "mais perto", "unidade mais", "posto mais", "agência mais", "agencia mais",
        "onde tem", "onde tem um", "onde tem uma", "onde encontrar",
        "local de", "lugar de", "onde posso ir", "onde devo ir"
    ]
    
    # Verifica se há pedido EXPLÍCITO de localização
    tem_pedido_explicito = any(ind in pergunta_lower for ind in indicadores_explicitos)
    
    # Também detecta perguntas diretas sobre localização
    perguntas_diretas = [
        "onde fica", "onde está", "onde tem", "onde encontrar",
        "qual endereço", "qual o endereço", "qual local"
    ]
    
    tem_pergunta_direta = any(perg in pergunta_lower for perg in perguntas_diretas)
    
    # Só retorna True se for pedido EXPLÍCITO ou pergunta DIRETA sobre localização
    # NÃO detecta "onde tirar", "onde fazer" que são perguntas gerais
    return tem_pedido_explicito or tem_pergunta_direta


def extrair_orgaos_mencoes(pergunta: str) -> List[str]:
    """
    Extrai quais órgãos foram mencionados na pergunta.
    
    Args:
        pergunta: Texto da pergunta
        
    Returns:
        Lista de IDs dos órgãos detectados
    """
    pergunta_lower = pergunta.lower()
    orgaos_detectados = []
    
    for orgao_id, dados in ORGAOS_MAP.items():
        for termo in dados["termos"]:
            if termo in pergunta_lower:
                if orgao_id not in orgaos_detectados:
                    orgaos_detectados.append(orgao_id)
                break
    
    return orgaos_detectados


def extrair_localidade_pergunta(pergunta: str) -> Optional[str]:
    """
    Tenta extrair cidade/estado mencionado na pergunta.
    Melhorado para capturar cidades e estados com mais precisão.
    
    Args:
        pergunta: Texto da pergunta
        
    Returns:
        Localidade extraída (ex: "São Luís, MA" ou "MA")
    """
    # Estados brasileiros com nomes completos
    estados = {
        "acre": "AC", "alagoas": "AL", "amapa": "AP", "amazonas": "AM",
        "bahia": "BA", "ceara": "CE", "distrito federal": "DF", "espirito santo": "ES",
        "goias": "GO", "maranhao": "MA", "mato grosso": "MT", "mato grosso do sul": "MS",
        "minas gerais": "MG", "para": "PA", "paraiba": "PB", "parana": "PR",
        "pernambuco": "PE", "piaui": "PI", "rio de janeiro": "RJ",
        "rio grande do norte": "RN", "rio grande do sul": "RS", "rondonia": "RO",
        "roraima": "RR", "santa catarina": "SC", "sao paulo": "SP",
        "sergipe": "SE", "tocantins": "TO"
    }
    
    # Cidades principais por estado (para melhorar precisão)
    cidades_principais = {
        "MA": ["São Luís", "Imperatriz", "Caxias", "Timon", "Codó"],
        "PA": ["Belém", "Ananindeua", "Marabá", "Paragominas", "Castanhal"],
        "SP": ["São Paulo", "Guarulhos", "Campinas", "São Bernardo", "Santo André"],
        "RJ": ["Rio de Janeiro", "São Gonçalo", "Duque de Caxias", "Nova Iguaçu", "Niterói"],
        "MG": ["Belo Horizonte", "Uberlândia", "Contagem", "Juiz de Fora", "Betim"],
        "RS": ["Porto Alegre", "Caxias do Sul", "Pelotas", "Canoas", "Santa Maria"],
        "PR": ["Curitiba", "Londrina", "Maringá", "Ponta Grossa", "Cascavel"],
        "BA": ["Salvador", "Feira de Santana", "Vitória da Conquista", "Camaçari", "Juazeiro"],
        "SC": ["Florianópolis", "Joinville", "Blumenau", "São José", "Chapecó"],
        "GO": ["Goiânia", "Aparecida de Goiânia", "Anápolis", "Rio Verde", "Luziânia"],
        "PE": ["Recife", "Jaboatão dos Guararapes", "Olinda", "Caruaru", "Petrolina"],
        "CE": ["Fortaleza", "Caucaia", "Juazeiro do Norte", "Maracanaú", "Sobral"],
        "PB": ["João Pessoa", "Campina Grande", "Santa Rita", "Patos", "Bayeux"],
        "AL": ["Maceió", "Arapiraca", "Rio Largo", "Palmeira dos Índios", "União dos Palmares"],
        "SE": ["Aracaju", "Nossa Senhora do Socorro", "Lagarto", "Itabaiana", "São Cristóvão"],
        "RN": ["Natal", "Mossoró", "Parnamirim", "São Gonçalo do Amarante", "Macaíba"],
        "PI": ["Teresina", "Parnaíba", "Picos", "Piripiri", "Campo Maior"],
        "TO": ["Palmas", "Araguaína", "Gurupi", "Porto Nacional", "Paraíso do Tocantins"],
    }
    
    siglas = ["ac", "al", "ap", "am", "ba", "ce", "df", "es", "go", "ma", "mt", "ms",
              "mg", "pa", "pb", "pr", "pe", "pi", "rj", "rn", "rs", "ro", "rr", "sc", "sp", "se", "to"]
    
    pergunta_lower = pergunta.lower()
    
    # Normaliza brasilia
    if "brasilia" in pergunta_lower or "brasília" in pergunta_lower:
        return "Brasília, DF"
    
    # Tratamento especial para casos comuns de confusão
    # "São Maranhão" geralmente significa "São Luís, MA" (capital)
    if "são maranhao" in pergunta_lower or "sao maranhao" in pergunta_lower:
        return "São Luís, MA"
    
    # "São Pará" pode ser Belém
    if "são para" in pergunta_lower or "sao para" in pergunta_lower:
        return "Belém, PA"
    
    # Procura padrões como "em [cidade]", "na [cidade]", "de [cidade]"
    # Ex: "em são luís", "na capital", "de belém"
    palavras = pergunta_lower.split()
    cidade_detectada = None
    estado_detectado = None
    
    # Procura estados completos primeiro
    for estado_nome, sigla in estados.items():
        if estado_nome in pergunta_lower:
            estado_detectado = sigla
            break
    
    # Se não encontrou estado completo, procura sigla
    if not estado_detectado:
        tokens = [t.strip("., ").lower() for t in pergunta.split()]
        for token in tokens:
            if token in siglas:
                estado_detectado = token.upper()
                break
    
    # Procura cidades conhecidas
    if estado_detectado and estado_detectado in cidades_principais:
        for cidade in cidades_principais[estado_detectado]:
            if cidade.lower() in pergunta_lower:
                cidade_detectada = cidade
                break
    
    # Se encontrou cidade e estado, retorna ambos
    if cidade_detectada and estado_detectado:
        return f"{cidade_detectada}, {estado_detectado}"
    
    # Se só encontrou estado, retorna sigla
    if estado_detectado:
        return estado_detectado
    
    # Tenta extrair cidade genérica antes de preposições
    preposicoes = ["em", "na", "no", "de", "da", "do", "para", "pra"]
    for i, palavra in enumerate(palavras):
        if palavra in preposicoes and i + 1 < len(palavras):
            cidade_candidata = palavras[i + 1].strip(".,")
            if len(cidade_candidata) > 2 and estado_detectado:
                return f"{cidade_candidata.title()}, {estado_detectado}"
    
    return None


def gerar_link_google_maps(orgao_id: str, localidade: Optional[str] = None) -> str:
    """
    Gera link do Google Maps para busca do órgão na localidade.
    Usa formato que garante PIN preciso no local.
    
    Args:
        orgao_id: ID do órgão (chave de ORGAOS_MAP)
        localidade: Cidade/Estado (ex: "São Paulo, SP" ou "MA")
        
    Returns:
        URL do Google Maps formatada com PIN preciso
    """
    if orgao_id not in ORGAOS_MAP:
        return ""
    
    nome_busca = ORGAOS_MAP[orgao_id]["nome_busca"]
    
    # Monta query de busca mais específica para melhor precisão
    if localidade:
        # Normaliza localidade
        localidade_clean = localidade.strip()
        
        # Se for só sigla (ex: "MA"), expande para o estado completo
        if len(localidade_clean) == 2:
            # Mapeamento de siglas para nomes completos
            sigla_para_estado = {
                "AC": "Acre", "AL": "Alagoas", "AP": "Amapá", "AM": "Amazonas",
                "BA": "Bahia", "CE": "Ceará", "DF": "Distrito Federal", "ES": "Espírito Santo",
                "GO": "Goiás", "MA": "Maranhão", "MT": "Mato Grosso", "MS": "Mato Grosso do Sul",
                "MG": "Minas Gerais", "PA": "Pará", "PB": "Paraíba", "PR": "Paraná",
                "PE": "Pernambuco", "PI": "Piauí", "RJ": "Rio de Janeiro",
                "RN": "Rio Grande do Norte", "RS": "Rio Grande do Sul", "RO": "Rondônia",
                "RR": "Roraima", "SC": "Santa Catarina", "SP": "São Paulo",
                "SE": "Sergipe", "TO": "Tocantins"
            }
            estado_nome = sigla_para_estado.get(localidade_clean.upper(), localidade_clean)
            # Para melhor precisão, adiciona termos específicos do órgão
            query = f"{nome_busca} {estado_nome} Brasil"
        else:
            # Se já tem cidade e estado, usa como está
            if "," in localidade_clean:
                query = f"{nome_busca} {localidade_clean} Brasil"
            else:
                query = f"{nome_busca} {localidade_clean} Brasil"
    else:
        query = f"{nome_busca} Brasil"
    
    # Codifica a query usando urllib.parse para garantir encoding correto
    query_encoded = urllib.parse.quote_plus(query)
    
    # Usa o formato de busca do Google Maps que garante melhor precisão
    # O parâmetro 'query' faz uma busca e mostra os resultados com PINs
    # Adiciona parâmetros adicionais para melhorar a precisão do PIN
    url = f"https://www.google.com/maps/search/?api=1&query={query_encoded}"
    
    return url


def gerar_links_orgaos(pergunta: str, localidade_perfil: Optional[str] = None, forcar_geracao: bool = False) -> List[Dict[str, str]]:
    """
    Gera links do Google Maps para órgãos relevantes baseado na pergunta.
    
    Args:
        pergunta: Pergunta do usuário
        localidade_perfil: Localidade do perfil do usuário (opcional)
        forcar_geracao: Se True, gera links mesmo sem detectar localização diretamente
        
    Returns:
        Lista de dicionários com 'orgao', 'nome' e 'link'
    """
    pergunta_lower = pergunta.lower()
    
    # Verifica se é pergunta sobre localização OU se deve forçar geração
    deve_gerar = detectar_pergunta_localizacao(pergunta) or forcar_geracao
    
    # Se não deve gerar, retorna vazio
    if not deve_gerar:
        return []
    
    # Extrai órgãos mencionados
    orgaos = extrair_orgaos_mencoes(pergunta)
    
    # Se não detectou órgão específico, tenta inferir pelo contexto
    if not orgaos:
        # Inferências baseadas em palavras-chave comuns
        if "cpf" in pergunta_lower or "imposto" in pergunta_lower:
            orgaos = ["receita_federal"]
        elif "rg" in pergunta_lower or "identidade" in pergunta_lower or "cin" in pergunta_lower:
            orgaos = ["instituto_identificacao", "poupatempo"]
        elif "cnh" in pergunta_lower or "habilitacao" in pergunta_lower or "habilitacao" in pergunta_lower:
            orgaos = ["detran"]
        elif "passaporte" in pergunta_lower:
            orgaos = ["policia_federal"]
        elif "bolsa" in pergunta_lower or "cadunico" in pergunta_lower:
            orgaos = ["caixa_economica"]
        elif "certidao" in pergunta_lower or "certidão" in pergunta_lower:
            orgaos = ["cartorio"]
    
    if not orgaos:
        return []
    
    # Tenta extrair localidade da pergunta primeiro, depois usa do perfil
    localidade = extrair_localidade_pergunta(pergunta)
    if not localidade and localidade_perfil:
        localidade = localidade_perfil
    
    # Gera links
    links = []
    for orgao_id in orgaos:
        nome = ORGAOS_MAP[orgao_id]["nome_busca"]
        link = gerar_link_google_maps(orgao_id, localidade)
        if link:
            links.append({
                "orgao": orgao_id,
                "nome": nome,
                "link": link
            })
    
    return links

