# GovGlossary - Backend

Backend do chatbot GovGlossary para orientação sobre serviços públicos brasileiros.

## 🚀 Tecnologias

- **FastAPI** - Framework web
- **Groq** - LLM para geração de respostas
- **ChromaDB** - Banco vetorial para RAG
- **Python 3.10+**

## 📋 Requisitos

- Python 3.10 ou superior
- pip

## 🔧 Instalação

```bash
# Instalar dependências
pip install -r modularizado/requirements.txt
```

## ⚙️ Configuração

Crie um arquivo `.env` na raiz do projeto:

```env
GROQ_API_KEY=sua_chave_groq
GOOGLE_API_KEY=sua_chave_google (opcional)
GOOGLE_APPLICATION_CREDENTIALS=caminho_para_credenciais.json (opcional)
```

## 🏃 Executar

```bash
cd modularizado
uvicorn api:app --host 0.0.0.0 --port 8000
```

O servidor estará disponível em `http://localhost:8000`

## 📚 Endpoints

- `GET /health` - Health check
- `POST /chat` - Chat com o bot
- `POST /transcribe` - Transcrição de áudio
- `POST /ingest` - Processar documentos
- `POST /session` - Gerenciar sessão

## 📝 Estrutura

```
modularizado/
├── api.py              # Endpoints FastAPI
├── resposta_ia.py      # Geração de respostas
├── rag.py              # Retrieval Augmented Generation
├── banco_dados.py      # Gerenciamento do banco vetorial
├── google_maps.py      # Geração de links do Google Maps
├── contexto_conversa.py # Gerenciamento de histórico
└── documentos/         # Documentos para ingestão
```

## 🔒 Segurança

⚠️ **Nunca commite arquivos com chaves de API!**
- Use variáveis de ambiente
- Adicione `.env` ao `.gitignore`
- Não commite `chave.json` ou arquivos sensíveis

