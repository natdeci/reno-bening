from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import uvicorn
from contextlib import asynccontextmanager
from retrieval.routes import ChatflowRoutes
from extraction.routes import PDFRoutes
from deletion.routes import DeleteRoutes
from util.db_connection import init_db, close_db

class DokuprimeAIAPI:
    def __init__(self):
        self.app = FastAPI(lifespan=self._lifespan)

        self.app.add_middleware(
            CORSMiddleware,
            allow_origins=["*"],
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )

        self.include_routers()
        self.app.mount("/api", self.app)

    async def _lifespan(self, app: FastAPI):
        print(">>> Starting up: Initializing DB pool...")
        await init_db()
        print(">>> DB pool initialized")

        yield

        print(">>> Shutting down: Closing DB pool...")
        await close_db()
        print(">>> DB pool closed")

    def include_routers(self):
        chatflow_routes = ChatflowRoutes()
        self.app.include_router(chatflow_routes.router, prefix="/chat")

        pdf_routes = PDFRoutes()
        self.app.include_router(pdf_routes.router, prefix="/extract")

        delete_routes = DeleteRoutes()
        self.app.include_router(delete_routes.router, prefix="/delete")

    def run(self):
        uvicorn.run(self.app,port=9534)

dokuprime_ai_api = DokuprimeAIAPI()
app = dokuprime_ai_api.app

if __name__ == "__main__":
    dokuprime_ai_api.run()