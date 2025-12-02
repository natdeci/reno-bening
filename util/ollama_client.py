import os
import ollama
from dotenv import load_dotenv

load_dotenv()

ollama_client = ollama.Client(host=os.getenv("OLLAMA_BASE_URL"))