## Dokuprime AI/Chatbot Handler
### Requirement
```
python 3.12
```
### Installation
#### Clone Repository
```
git clone https://github.com/BKPMAI/dokuprime-ai.git
```
#### Create Virtual Environment
```
python -m venv .venv
```
#### Activate Virtual Environment
```
# Windows
.venv\Scripts\activate

#Linux
source .venv/bin/activate
```
#### Install the packages
```
pip install -R requirements.txt
```
#### !   ALTERNATIVELY, IF requirements.txt DOESN'T WORK...   !
```
pip install python-dotenv qdrant-client==1.15 requests fastapi uvicorn pandas ollama pymupdf pdfplumber httpx requests langchain langchain-text-splitters aiohttp langchain-community langchain-ollama langchain-core pydantic-settings pytz "psycopg[binary]" langchain-postgres asyncpg python-multipart
```

### Usage
#### Run App
```
uvicorn main:app --host 0.0.0.0 --port 8000
```