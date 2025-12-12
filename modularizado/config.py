import os
from dotenv import load_dotenv

load_dotenv()

# Caminhos relativos ao diretório do módulo (funciona local e no Render)
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PASTA_DOCUMENTOS = os.path.join(BASE_DIR, "documentos")
PASTA_BANCO_VETORIAL = os.path.join(BASE_DIR, "banco_vetorial")

MODELO_IA = "openai/gpt-oss-120b"

GROQ_API_KEY = os.getenv("GROQ_API_KEY")
