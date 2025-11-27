from util.db_connection import get_pool

class ExtractRepository:
    def __init__(self):
        self.history_limit=6
        print("ChatflowRepository Initiated")

    async def update_document_status(self, status: str, id: int):
        print("Entring update_document_status method")

        query = """
        UPDATE bkpm.document_details
        SET ingest_status = $1
        WHERE document_id = $2;
        """

        try:
            pool = await get_pool()
            async with pool.acquire() as conn:
                await conn.execute(query, status, id)

        except Exception as e:
            print(f"[WARNING] update_document_status ignored error: {e}")

        print("Exiting update_document_status method")
