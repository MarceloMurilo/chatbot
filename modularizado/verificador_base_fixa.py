from base_fixa import BASE_FIXA

def normalizar(texto):
    return texto.lower().strip()

def buscar_resposta_fixa(pergunta):
    pergunta_norm = normalizar(pergunta)

    for item in BASE_FIXA.values():
        for p in item["perguntas"]:
            if p in pergunta_norm:
                return item["resposta"]

    return None
