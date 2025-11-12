import uuid, json
import time
from .entity.chat_request import ChatRequest
from .generate_answer import generate_answer
from .knowledge_retrieval import retrieve_knowledge
from .query_embedding_converter import convert_to_embedding
from .rewriter import rewrite_query
# from .rerank import rerank_documents_with_flag
from .classify_collection import classify_collection
from .flag_message import flag_message
from .ingest_category import ingest_category
from .get_context import get_context
from .check_fail_history import check_fail_history
from .create_new_conversation import create_new_conversation
from .flag_answered_validation import flag_answered_validation   
from .retrieve_faq import retrieve_faq
from .classify_user_query import classify_user_query
from .ingest_question_category import ingest_question_category
from .rerank_new import rerank_documents

class ChatflowHandler:
    def __init__(self):
        self.new_conv = create_new_conversation
        self.context = get_context
        self.rewriter = rewrite_query
        self.classifier = classify_collection
        self.converter = convert_to_embedding
        self.retriever = retrieve_knowledge
        # self.rerank = rerank_documents_with_flag
        self.rerank_new = rerank_documents
        self.llm = generate_answer
        self.flag = flag_message
        self.categorize = ingest_category
        self.checker = check_fail_history

        self.question_classifier = classify_user_query
        self.categorize_question = ingest_question_category

        print("Chatflow handler initialized")

    async def chatflow_call(self, req: ChatRequest):
        print("Entering chatflow_call method")
        ret_conversation_id = req.conversation_id
        context = ""

        if(ret_conversation_id == ""):
            ret_conversation_id = str(uuid.uuid4())
            await self.new_conv(ret_conversation_id, req.platform, req.platform_unique_id)
        else:
            context = await self.context(ret_conversation_id)

        rewritten= await self.rewriter(user_query=req.query, history_context=context)
        embedded_query = await self.converter(rewritten)

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
            "answer": "Percakapan ini akan dialihkan ke agent.",
            "citations": "",
            "is_helpdesk": True
        }

        if collection_choice == "skip_collection_check":
            return {
            "user": req.platform_unique_id,
            "conversation_id": ret_conversation_id,
            "query": req.query,
            "rewritten_query": rewritten,
            "category": "",
            "answer": "Mohon maaf, pertanyaan tersebut berada di luar cakupan layanan BKPM. Silakan ajukan pertanyaan yang berkaitan dengan investasi, perizinan berusaha, atau layanan OSS agar saya dapat membantu dengan lebih tepat.",
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
        category = await self.categorize(ret_conversation_id, req.query, collection_choice)

        question_classify = await self.question_classifier(rewritten)
        q_category = await self.categorize_question(
            ret_conversation_id, 
            req.query,
            question_classify.get("category"),
            question_classify.get("sub_category")
        )

        print("Exiting chatflow_call method")

        if(answer.startswith('[!]') or answer.endswith('Apakah Anda ingin saya hubungkan dengan Agen Layanan?')):
            await self.flag(ret_conversation_id, req.query)
            status = await self.checker(ret_conversation_id)
            if status and answer.startswith('[!]'):
                return {
                    "user": req.platform_unique_id,
                    "conversation_id": ret_conversation_id,
                    "query": req.query,
                    "rewritten_query": rewritten,
                    "category": category,
                    "question_category": q_category,
                    "answer": answer + "\n\nApakah Anda ingin saya hubungkan dengan Agen Layanan?",
                    "citations": reranked_files,
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
            "answer": answer,
            "citations": reranked_files,
            "is_helpdesk": False,
            "is_answered": None
        }
