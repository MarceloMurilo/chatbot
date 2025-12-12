import os
from dotenv import load_dotenv

load_dotenv()

PASTA_DOCUMENTOS = "./documentos"
PASTA_BANCO_VETORIAL = "./banco_vetorial"

MODELO_IA = "openai/gpt-oss-120b"

GROQ_API_KEY = os.getenv("GROQ_API_KEY")
