from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    # --- Ollama/LLM Settings ---
    ollama_base_url: str
    ollama_temperature: float
    ollama_timeout: float
    embed_model: str
    llm_model: str
    llm_eval: str
    llm_api_key: str # Likely "ollama" in your case

    # --- VLM Settings ---
    vlm_model: str
    vlm_temperature: float
    
    # --- Qdrant/VectorDB Settings ---
    collection_name: str
    qdrant_url: str
    top_k: int
    rerank_model: str
    qna_collection: str 
    
    # --- PostgreSQL Settings ---
    dbname: str
    dbuser: str
    dbpassword: str
    dbhost: str
    dbport: int

    api_key_secret: str
    rerank_url: str
    bm25_url: str

    class Config:
        env_file = ".env"

settings = Settings()
