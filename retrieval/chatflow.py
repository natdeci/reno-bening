import os
import uuid, json
import time
from datetime import datetime
import pytz
from dotenv import load_dotenv
from util.qdrant_connection import vectordb_client
from .entity.chat_request import ChatRequest
from .generate_answer import generate_answer
from .knowledge_retrieval import retrieve_knowledge
from .query_embedding_converter import convert_to_embedding
from .rewriter import rewrite_query
from .classify_collection import classify_collection
from .classify_user_query import classify_user_query
from .rerank_new import rerank_documents
from .repository import ChatflowRepository

load_dotenv()
class ChatflowHandler:
    def __init__(self):
        self.qdrant_faq_name = os.getenv("QNA_COLLECTION")
        self.faq_limit = 3
        self.faq_threshold = 1.0

        self.rewriter = rewrite_query
        self.classifier = classify_collection
        self.converter = convert_to_embedding
        self.retriever = retrieve_knowledge
        self.rerank_new = rerank_documents
        self.llm = generate_answer
        self.question_classifier = classify_user_query
        self.repository = ChatflowRepository()
        print("Chatflow handler initialized")

    async def retrieve_faq(self, query_vector: list[float]):
        print("[INFO] Entering retrieve_faq method")
        limit = self.faq_limit

        results = await vectordb_client.search(
            collection_name=self.qdrant_faq_name,
            query_vector=query_vector,
            limit=limit
        )

        if not results:
            print("[INFO] No FAQ results found")
            return {"matched": False, "answer": None, "score": 0.0}
        print(f"Score: {results[0].score}")
        if results[0].score < self.faq_threshold:
            print(f"FAQ confidence is too low! {results[0].score}")
            return {"matched": False, "answer": None, "citations": []}
        
        faq_results = []
        file_ids = []
        for result in results:
            score = result.score
            question_text = result.payload.get("page_content")
            metadata = result.payload.get("metadata")
            file_id = metadata.get("file_id")
            answer = metadata.get("answer", None)
            if answer:
                print(answer)
                if file_id not in file_ids:
                    file_ids.append(file_id)
            elif answer == None:
                print("Knowledge is from validation")
                chat_id = int(file_id.split("-", 1)[1].strip())
                answer = await self.repository.get_revision(chat_id)

            faq_results.append((score,question_text,answer))

        formatted = []
        for score, question_text, answer in faq_results:
            block = f"Q: {question_text}\nA: {answer}"
            formatted.append(block)

        result_string = "\n---\n".join(formatted)
        print("FAQ Matched!")
        return {
            "matched": True,
            "faq_string": result_string,
            "file_ids": file_ids,
        }
            

    async def chatflow_call(self, req: ChatRequest):
        print("Entering chatflow_call method")
        ret_conversation_id = req.conversation_id
        initial_message = ""
        context = await self.repository.get_context(ret_conversation_id)

        if context == "Conversation History:":
            if ret_conversation_id == "":
                ret_conversation_id = str(uuid.uuid4())
            await self.repository.create_new_conversation(ret_conversation_id, req.platform, req.platform_unique_id)
            tz = pytz.timezone("Asia/Jakarta")
            now = datetime.now(tz)
            hour = now.hour
            if 4 <= hour < 11:
                greetings_id=1
            elif 11 <= hour < 15:
                greetings_id=2
            elif 15 <= hour < 18:
                greetings_id=3
            else:
                greetings_id=4
            initial_message = await self.repository.get_greetings(greetings_id)

        rewritten= await self.rewriter(user_query=req.query, history_context=context)
        embedded_query = await self.converter(rewritten)
        await self.repository.give_conversation_title(session_id=ret_conversation_id, rewritten=rewritten)

        collection_choice = await self.classifier(req.query, context)

        if collection_choice == "helpdesk":
            await self.repository.increment_helpdesk_count(ret_conversation_id)
            return {
                "user": req.platform_unique_id,
                "conversation_id": ret_conversation_id,
                "query": req.query,
                "rewritten_query": rewritten,
                "category": "",
                "answer": f"{initial_message}" + "Mohon konfirmasi apabila anda ingin dihubungkan ke helpdesk",
                "citations": "",
                "is_helpdesk": True
            }

        if collection_choice == "skip_collection_check" or collection_choice == "greeting_query" or collection_choice == "thank_you":
            basic_return = ""
            if collection_choice == "skip_collection_check":
                basic_return = "Mohon maaf, pertanyaan tersebut berada di luar cakupan layanan kami. Silakan ajukan pertanyaan yang berkaitan dengan investasi, perizinan berusaha, atau layanan OSS agar saya dapat membantu dengan lebih tepat."
            elif collection_choice == "greeting_query":
                basic_return = "Halo! Selamat datang di layanan Kementerian Investasi & Hilirisasi/BKPM, apakah ada yang bisa saya bantu?"
            elif collection_choice == "thank_you":
                basic_return = "Terima kasih! Silakan chat lagi jika ada yang ingin ditanyakan"
            return {
            "user": req.platform_unique_id,
            "conversation_id": ret_conversation_id,
            "query": req.query,
            "rewritten_query": rewritten,
            "category": "",
            "answer": basic_return,
            "citations": "",
            "is_helpdesk": False
        }

        category = await self.repository.ingest_category(ret_conversation_id, req.query, collection_choice)

        faq_response = await self.retrieve_faq(embedded_query)
        if faq_response["matched"]:
            citations = faq_response["file_ids"]
            answer = await self.llm(req.query, faq_response["faq_string"], ret_conversation_id, req.platform)
            await self.repository.flag_message_is_answered(ret_conversation_id, req.query)
        else:
            docs = await self.retriever(embedded_query, collection_choice)

            texts = []
            fileids = []
            filenames = []
            for d in docs:
                if "page_content" in d:
                    texts.append(d["page_content"])
                    meta = d.get("metadata", {})
                    fileids.append(meta.get("file_id") or "unknown_source")
                    filenames.append(meta.get("filename") or "unknown_source")
            reranked, citation_id, citation_name = await self.rerank_new(rewritten, texts, fileids, filenames)

            citations = list(zip(citation_id, citation_name))
            answer = await self.llm(req.query, reranked, ret_conversation_id, req.platform)

        question_classify = await self.question_classifier(rewritten)
        q_category = await self.repository.ingest_question_category(
            ret_conversation_id, 
            req.query,
            question_classify.get("category"),
            question_classify.get("sub_category")
        )

        print("Exiting chatflow_call method")

        if(answer.startswith('Mohon maaf, saya hanya dapat membantu terkait informasi perizinan usaha, regulasi, dan investasi.')):
            await self.repository.flag_message_cannot_answer(ret_conversation_id, req.query)
            status = await self.repository.check_fail_history(ret_conversation_id)
            if status:
                suffix_message = "Mohon maaf, pertanyaan tersebut belum bisa kami jawab. Silakan ajukan pertanyaan lain.\n\nUntuk bantuan lebih lanjut, anda bisa kunjungi kantor BKPM terdekat atau email ke kontak@oss.go.id"
                fail_answer = initial_message + suffix_message
            else:
                fail_answer = initial_message + answer
            return {
                "user": req.platform_unique_id,
                "conversation_id": ret_conversation_id,
                "query": req.query,
                "rewritten_query": rewritten,
                "category": category,
                "question_category": q_category,
                "answer": fail_answer,
                "citations": [],
                "is_helpdesk": False,
                "is_answered": None 
            }

        return {
            "user": req.platform_unique_id,
            "conversation_id": ret_conversation_id,
            "query": req.query,
            "rewritten_query": rewritten,
            "category": category,
            "question_category": q_category,
            "answer": f"{initial_message}" + answer + "\n\n*Jawaban ini dibuat oleh AI dan mungkin tidak selalu akurat. Mohon gunakan sebagai referensi dan lakukan pengecekan tambahan bila diperlukan.*",
            "citations": citations,
            "is_helpdesk": False,
            "is_answered": None
        }
