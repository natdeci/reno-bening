import uuid, json
import time
from datetime import datetime
import pytz
from .entity.chat_request import ChatRequest
from .generate_answer import generate_answer
from .knowledge_retrieval import retrieve_knowledge
from .query_embedding_converter import convert_to_embedding
from .rewriter import rewrite_query
from .classify_collection import classify_collection
from .classify_user_query import classify_user_query
from .rerank_new import rerank_documents
from .repository import ChatflowRepository

class ChatflowHandler:
    def __init__(self):
        self.rewriter = rewrite_query
        self.classifier = classify_collection
        self.converter = convert_to_embedding
        self.retriever = retrieve_knowledge
        self.rerank_new = rerank_documents
        self.llm = generate_answer
        self.question_classifier = classify_user_query
        self.repository = ChatflowRepository()

        print("Chatflow handler initialized")

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
        # else:
        #     context = await self.context(ret_conversation_id)

        rewritten= await self.rewriter(user_query=req.query, history_context=context)
        embedded_query = await self.converter(rewritten)
        await self.repository.give_conversation_title(session_id=ret_conversation_id, rewritten=rewritten)

        # faq_result = await retrieve_faq(embedded_query, threshold=1)
        # if faq_result["matched"]:
        #     print(f"[INFO] FAQ matched with score {faq_result['score']}")
        #     citations = [faq_result["filename"]] if faq_result.get("filename") else []
        #     answer = await self.llm(req.query, [faq_result["answer"]], ret_conversation_id)

        #     category = await self.categorize(ret_conversation_id, req.query, "faq_collection")

        #     question_classify = await self.question_classifier(rewritten)
        #     q_category = await self.categorize_question(
        #         ret_conversation_id, 
        #         req.query,
        #         question_classify.get("category"),
        #         question_classify.get("sub_category")
        #     )
        #     is_answered = await flag_answered_validation(
        #         session_id=ret_conversation_id,
        #         user_question=req.query,
        #         threshold=0.85
        #     )

        #     return {
        #         "user": req.platform_unique_id,
        #         "conversation_id": ret_conversation_id,
        #         "query": req.query,
        #         "rewritten_query": rewritten,
        #         "category": category,
        #         "question_category": q_category,
        #         "answer": answer,
        #         "citations": citations,
        #         "is_helpdesk": False,
        #         "is_answered": True
        #     }

        collection_choice = await self.classifier(req.query, context)

        if collection_choice == "helpdesk":
            return {
            "user": req.platform_unique_id,
            "conversation_id": ret_conversation_id,
            "query": req.query,
            "rewritten_query": rewritten,
            "category": "",
            "answer": f"{initial_message}" + "Mohon maaf, untuk sekarang layanan agen helpdesk tidak tersedia.\nmohon kunjungi kantor Kementerian Investasi & Hilirisasi/BKPM terdekat atau email ke kontak@oss.go.id",
            "citations": "",
            "is_helpdesk": False
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
        start_time = time.perf_counter()
        docs = await self.retriever(embedded_query, collection_choice)
        end_time = time.perf_counter()
        elapsed_time = end_time - start_time
        print(f"Code block took {elapsed_time} seconds.")
        
        texts = []
        filenames = []
        for d in docs:
            if "page_content" in d:
                texts.append(d["page_content"])
                meta = d.get("metadata", {})
                filenames.append(meta.get("filename") or meta.get("file_id") or "unknown_source")

        reranked, reranked_files = await self.rerank_new(rewritten, texts, filenames)

        answer = await self.llm(req.query, reranked, ret_conversation_id)
        category = await self.repository.ingest_category(ret_conversation_id, req.query, collection_choice)

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
            "citations": reranked_files,
            "is_helpdesk": False,
            "is_answered": None
        }
