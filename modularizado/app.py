from ingesta import processar_arquivos
from rag import responder

EXEMPLOS = {
    "1": "Como tirar o novo RG?",
    "2": "Quais documentos preciso para Bolsa Família?",
    "3": "Onde faço meu CPF?",
    "4": "Precisa agendar para tirar passaporte?",
    "5": "O que levar para vacinar uma criança?"
}

def mostrar_intro():
    print("""
====================================================
ASSISTENTE DE DOCUMENTOS E SERVIÇOS PÚBLICOS
====================================================

Eu ajudo você a entender:
- Quais documentos levar
- Onde ir
- Se precisa agendar
- Erros comuns que fazem perder viagem

Escolha um exemplo digitando o número (1 a 5) ou escreva sua própria pergunta:
""")

    for k, v in EXEMPLOS.items():
        print(f"{k}. {v}")

    print("""
Digite 'sair' para voltar ao menu.
====================================================
""")

def iniciar_chat():
    mostrar_intro()

    while True:
        entrada = input("\nVocê: ").strip()

        if entrada.lower() in ["sair", "exit"]:
            break

        # Se o usuário digitou um número de exemplo, converte em pergunta completa
        if entrada in EXEMPLOS:
            pergunta = EXEMPLOS[entrada]
            print(f"(Exemplo selecionado: {pergunta})")
        else:
            pergunta = entrada

        responder(pergunta)

def menu():
    while True:
        print("\n=== SISTEMA RAG ===")
        print("1. Atualizar base")
        print("2. Conversar")
        print("3. Sair")

        opcao = input("Escolha: ").strip()

        if opcao == "1":
            processar_arquivos()
        elif opcao == "2":
            iniciar_chat()
        elif opcao == "3":
            print("Encerrando...")
            break
        else:
            print("Opção inválida.")

if __name__ == "__main__":
    menu()
