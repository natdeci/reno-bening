import os
import asyncio
import uuid, json
import time
from datetime import datetime
import pytz
from dotenv import load_dotenv
from util.qdrant_connection import vectordb_client
from .entity.chat_request import ChatRequest
from .generate_fallback_question import generate_helpdesk_confirmation_answer
from .generate_helpdesk_response import generate_helpdesk_response
from .generate_answer import generate_answer
from .knowledge_retrieval import retrieve_knowledge, retrieve_knowledge_faq
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

        self.llm_helpdesk = generate_helpdesk_confirmation_answer
        self.llm_helpdesk_response = generate_helpdesk_response
        self.rewriter = rewrite_query
        self.classifier = classify_collection
        self.converter = convert_to_embedding
        self.retriever_faq = retrieve_knowledge_faq
        self.retriever = retrieve_knowledge
        self.rerank_new = rerank_documents
        self.llm = generate_answer
        self.question_classifier = classify_user_query
        self.repository = ChatflowRepository()
        print("Chatflow handler initialized")

    async def retrieve_faq(self, query_vector: str):
        print("[INFO] Entering retrieve_faq method")
        limit = self.faq_limit

        results = await self.retriever_faq(query_vector, self.qdrant_faq_name, top_k=limit)
        if not results:
            print("[INFO] No FAQ results found")
            return {"matched": False, "answer": None, "score": 0.0}
        if results[0][1] < self.faq_threshold:
            print(f"FAQ confidence is too low! {results[0][1]}")
            return {"matched": False, "answer": None, "citations": []}
  
        faq_results = []
        file_ids = []
        file_names = []
        for d,s in results:
            score = s
            print(score)
            question_text = d.page_content
            metadata = d.metadata
            file_id = metadata.get("file_id")
            file_name = metadata.get("filename")
            answer = metadata.get("answer", None)
            if answer:
                print("answer from vector:" + answer)
                if file_id not in file_ids:
                    file_ids.append(file_id)
                    file_names.append(file_name)
            elif answer == None:
                print("Knowledge is from validation")
                chat_id = int(file_id.split("-", 1)[1].strip())
                answer = await self.repository.get_revision(chat_id)

            faq_results.append((score,question_text,answer))

        formatted = []
        for score, question_text, answer in faq_results:
            block = f"Q: {question_text}\nA: {answer}"
            formatted.append(block)

        citations = list(zip(file_ids, file_names))

        result_string = "\n---\n".join(formatted)
        print("FAQ Matched!")
        return {
            "matched": True,
            "faq_string": result_string,
            "citations": citations,
        }
            
    async def chatflow_call(self, req: ChatRequest):
        print("Entering chatflow_call method")
        if req.conversation_id != "":
            ask_helpdesk_status = await self.repository.check_is_ask_helpdesk(req.conversation_id)
            if ask_helpdesk_status:
                print("Ask for moving to helpdesk")
                is_helpdesk_conf = False
                is_ask_helpdesk_conf = True
                helpdesk_confirmation_answer =  await self.llm_helpdesk(req.query, req.conversation_id)
                if helpdesk_confirmation_answer != "Maaf, bapak/ibu dimohon untuk konfirmasi ya/tidak untuk pengalihan ke helpdesk agen layanan.":
                    await self.repository.change_is_ask_helpdesk_status(req.conversation_id)
                    if helpdesk_confirmation_answer == "Percakapan ini akan dihubungkan ke agen layanan.":
                        await self.repository.change_is_helpdesk(req.conversation_id)
                return {
                    "user": req.platform_unique_id,
                    "conversation_id": req.conversation_id,
                    "query": req.query,
                    "answer": helpdesk_confirmation_answer,
                    "citations": [],
                    "is_helpdesk": is_helpdesk_conf,
                    "is_answered": None,
                    "is_ask_helpdesk": is_ask_helpdesk_conf
                }
            helpdesk_status = await self.repository.check_is_helpdesk(req.conversation_id)
            if helpdesk_status:
                print("Already moved to helpdesk")
                return {
                    "user": req.platform_unique_id,
                    "conversation_id": req.conversation_id,
                    "query": req.query,
                    "answer": "Percakapan telah dipindahkan ke helpdesk.",
                    "citations": [],
                    "is_helpdesk": True,
                    "is_answered": None,
                    "is_ask_helpdesk": False
                }
            
        start_timestamp = req.start_timestamp
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
        await self.repository.give_conversation_title(session_id=ret_conversation_id, rewritten=rewritten)

        collection_choice = await self.classifier(req.query, context)

        if collection_choice == "uraian_collection":
            collection_choice = "peraturan_collection"
                    
        if collection_choice == "helpdesk":
            await self.repository.change_is_helpdesk(ret_conversation_id)
            helpdesk_response = await self.llm_helpdesk_response(req.query, ret_conversation_id)
            return {
                "user": req.platform_unique_id,
                "conversation_id": ret_conversation_id,
                "query": req.query,
                "rewritten_query": rewritten,
                "category": "",
                "answer": (initial_message or "") + helpdesk_response,
                "citations": "",
                "is_helpdesk": True
            }

        if collection_choice == "skip_collection_check" or collection_choice == "greeting_query" or collection_choice == "thank_you" or collection_choice == "classified_information":
            basic_return = ""
            if collection_choice == "skip_collection_check":
                basic_return = "Mohon maaf, pertanyaan tersebut berada di luar cakupan layanan kami. Silakan ajukan pertanyaan yang berkaitan dengan investasi, perizinan berusaha, atau layanan OSS agar saya dapat membantu dengan lebih tepat."
            elif collection_choice == "greeting_query":
                basic_return = "Halo! Selamat datang di layanan Kementerian Investasi & Hilirisasi/BKPM, apakah ada yang bisa saya bantu?"
            elif collection_choice == "thank_you":
                await self.repository.ingest_end_timestamp(ret_conversation_id)
                basic_return = "Terima kasih telah menghubungi layanan Kementerian Investasi & Hilirisasi/BKPM!"
            elif collection_choice == "classified_information":
                basic_return = "Mohon maaf, pertanyaan tersebut melibatkan informasi konfidensial/rahasia. Silakan tanyakan pertanyaan lain."

            await self.repository.ingest_skipped_question(ret_conversation_id, req.query, "Pertanyaan di luar OSS", "Pertanyaan di luar OSS")

            return {
            "user": req.platform_unique_id,
            "conversation_id": ret_conversation_id,
            "query": req.query,
            "rewritten_query": rewritten,
            "category": "",
            "answer": basic_return,
            "citations": "",
            "is_helpdesk": False,
            "is_faq": False
        }

        status = await self.repository.check_fail_history(ret_conversation_id)

        faq_response = await self.retrieve_faq(rewritten)
        if faq_response["matched"]:
            citations = faq_response["citations"]
            answer = await self.llm(req.query, faq_response["faq_string"], ret_conversation_id, req.platform, status)
            await self.repository.flag_message_is_answered(ret_conversation_id, req.query)
        else:
            docs = await self.retriever(rewritten, collection_choice)

            texts = []
            fileids = []
            filenames = []
            for d, s in docs:
                texts.append(d.page_content)
                meta = d.metadata
                fileids.append(meta.get("file_id") or "unknown_source")
                filenames.append(meta.get("filename") or "unknown_source")
            print(fileids)
            print(filenames)
            reranked, citation_id, citation_name = await self.rerank_new(rewritten, texts, fileids, filenames)
            print(citation_id)
            print(citation_name)
            citations = list(zip(citation_id, citation_name))
            unique_names = []
            for name in citation_name:
                if name not in unique_names:
                    unique_names.append(name)

            cleaned_names = [n.rsplit(".", 1)[0] for n in unique_names]

            citation_str = ", ".join(cleaned_names)
            answer = await self.llm(req.query, reranked, ret_conversation_id, req.platform, status, collection_choice, citation_str)

        await self.repository.ingest_start_timestamp(ret_conversation_id, start_timestamp)
        category = await self.repository.ingest_category(ret_conversation_id, req.query, collection_choice)
        question_classify = await self.question_classifier(rewritten)
        q_category = await self.repository.ingest_question_category(
            ret_conversation_id, 
            req.query,
            question_classify.get("category"),
            question_classify.get("sub_category")
        )
        question_id, answer_id = await self.repository.get_chat_history_id(ret_conversation_id, req.query)
        print("Exiting chatflow_call method")

        if(answer.startswith('Mohon maaf, saya hanya dapat membantu terkait informasi perizinan usaha, regulasi, dan investasi.')) or (answer.startswith('Mohon maaf, pertanyaan tersebut belum bisa kami jawab.')):
            await self.repository.flag_message_cannot_answer(ret_conversation_id, req.query)
            ask_helpdesk = False
            if (answer.startswith('Mohon maaf, pertanyaan tersebut belum bisa kami jawab.')):
                await self.repository.change_is_ask_helpdesk_status(ret_conversation_id)
                ask_helpdesk = True
            return {
                "user": req.platform_unique_id,
                "conversation_id": ret_conversation_id,
                "query": req.query,
                "rewritten_query": rewritten,
                "category": category,
                "question_category": q_category,
                "answer": (initial_message or "") + answer,
                "question_id": question_id,
                "answer_id": answer_id,
                "citations": [],
                "is_helpdesk": False,
                "is_answered": None,
                "is_ask_helpdesk": ask_helpdesk
            }
        
        await self.repository.ingest_citations(citations, ret_conversation_id, req.query)

        return {
            "user": req.platform_unique_id,
            "conversation_id": ret_conversation_id,
            "query": req.query,
            "rewritten_query": rewritten,
            "category": category,
            "question_category": q_category,
            "answer": (initial_message or "") + answer + "\n\n*Jawaban ini dibuat oleh AI dan mungkin tidak selalu akurat. Mohon gunakan sebagai referensi dan lakukan pengecekan tambahan bila diperlukan.*",
            "question_id": question_id,
            "answer_id": answer_id,
            "citations": citations,
            "is_helpdesk": False,
            "is_answered": None
        }
