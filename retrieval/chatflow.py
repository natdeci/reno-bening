import os
import re
import uuid
from datetime import datetime
import pytz
from dotenv import load_dotenv
from typing import Tuple
from .entity.chat_request import ChatRequest
from .entity.final_answer import FinalResponse
from .generate_fallback_question import generate_helpdesk_confirmation_answer
from .evaluate_llm_answer import evaluate_llm_answer
from .generate_answer import generate_answer
from .classify_kbli import classify_kbli
from .classify_specific import classify_specific
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
        self.faq_threshold = 0.75
        self.tz = pytz.timezone("Asia/Jakarta")
        self.llm_helpdesk = generate_helpdesk_confirmation_answer
        self.rewriter = rewrite_query
        self.classifier = classify_collection
        self.classify_kbli = classify_kbli
        self.classify_specific = classify_specific
        self.converter = convert_to_embedding
        self.retriever_faq = retrieve_knowledge_faq
        self.retriever = retrieve_knowledge
        self.rerank_new = rerank_documents
        self.llm = generate_answer
        self.evaluate = evaluate_llm_answer
        self.question_classifier = classify_user_query
        self.repository = ChatflowRepository()
        print("Chatflow handler initialized")

    def _build_final_response(self, 
        req: ChatRequest, 
        data: FinalResponse) -> dict:

        return {
            "user": req.platform_unique_id,
            "query": req.query,
            **data.model_dump()
        }
    
    async def handle_helpdesk_confirmation_answer(self, req: ChatRequest):
        print("Entering handle_helpdesk_confirmation_answer method")
        is_ask_helpdesk_conf = True
        helpdesk_confirmation_answer = self.llm_helpdesk(req.query, req.conversation_id)
        question_id, _ = await self.repository.get_chat_history_id(req.conversation_id, req.query)
        if helpdesk_confirmation_answer != "Maaf, bapak/ibu dimohon untuk konfirmasi ya/tidak untuk pengalihan ke helpdesk agen layanan.":
            await self.repository.change_is_ask_helpdesk_status(req.conversation_id)
            is_ask_helpdesk_conf = False
            if helpdesk_confirmation_answer == "Percakapan ini akan dihubungkan ke agen layanan.":
                await self.repository.change_is_helpdesk(req.conversation_id)
        print("Exiting handle_helpdesk_confirmation_answer method")
        return FinalResponse(
            conversation_id=req.conversation_id,
            answer=helpdesk_confirmation_answer,
            question_id=question_id,
            is_helpdesk=True,
            is_ask_helpdesk=is_ask_helpdesk_conf
        )
    
    async def get_greetings_message(self):
        print("Entering get_greetings_message method")
        now=datetime.now(self.tz)
        hour=now.hour
        if 4 <= hour < 11:
            greetings_id=1
        elif 11 <= hour < 15:
            greetings_id=2
        elif 15 <= hour < 18:
            greetings_id=3
        else:
            greetings_id=4
        initial_message = await self.repository.get_greetings(greetings_id)

        print("Exiting get_greetings_message method")
        return initial_message
    
    async def generate_helpdesk_routing_response(self, req: ChatRequest, ret_conversation_id: str, helpdesk_active_status: bool):
        print("Entering generate_helpdesk_routing_response method")

        helpdesk_response = "Mohon maaf, untuk saat ini helpdesk agen layanan kami sedang tidak tersedia.\nBapak/Ibu bisa ajukan pertanyaan dengan mengirim email ke kontak@oss.go.id"
        if helpdesk_active_status:
            helpdesk_response = "Percakapan ini akan dihubungkan ke agen layanan."

        await self.repository.insert_skip_chat(session_id=ret_conversation_id, human_message=req.query, ai_message=helpdesk_response)

        print("Exiting generate_helpdesk_routing_response method")
        return helpdesk_response
    
    async def handle_helpdesk_response(self, helpdesk_active_status: bool, req: ChatRequest, ret_conversation_id: str, initial_message: str, rewritten: str):
        print("Entering handle_helpdesk_response method")

        if helpdesk_active_status:
            await self.repository.change_is_helpdesk(ret_conversation_id)
        helpdesk_response = await self.generate_helpdesk_routing_response(req=req, ret_conversation_id=ret_conversation_id, helpdesk_active_status=helpdesk_active_status)
        question_id, answer_id = await self.repository.get_chat_history_id(ret_conversation_id, req.query)

        print("Exiting handle_helpdesk_response method")
        return_data = FinalResponse(
            conversation_id=ret_conversation_id,
            rewritten_query=rewritten,
            answer=(initial_message or "") + helpdesk_response,
            question_id=question_id,
            answer_id=answer_id,
            is_helpdesk=True
        )
        return self._build_final_response(
            req=req,
            data=return_data)
    
    async def handle_skip_collection_answer(self, req: ChatRequest, ret_conversation_id: str, rewritten: str, message: str, is_ask_helpdesk: bool):
        print("Entering handle_skip_collection_answer method")

        await self.repository.insert_skip_chat(session_id=ret_conversation_id, human_message=req.query, ai_message=message)
        question_id, answer_id = await self.repository.get_chat_history_id(ret_conversation_id, req.query)
        await self.repository.flag_message_cannot_answer_by_id(question_id)

        print("Exiting handle_skip_collection_answer method")
        return_data = FinalResponse(
            conversation_id=ret_conversation_id,
            rewritten_query=rewritten,
            answer=message,
            question_id=question_id,
            answer_id=answer_id,
            is_ask_helpdesk=is_ask_helpdesk
        )
        return self._build_final_response(
            req=req,
            data=return_data)
    
    async def handle_default_answering(self, req: ChatRequest, ret_conversation_id: str, rewritten: str, collection_choice: str):
        print("Entering handle_default_answering method")

        basic_return = ""
        if collection_choice == "skip_collection_check":
            status = await self.repository.check_fail_history(ret_conversation_id)
            helpdesk_active_status = await self.repository.check_helpdesk_activation()
            is_ask_helpdesk = False
            if status:
                if helpdesk_active_status:
                    await self.repository.change_is_ask_helpdesk_status(ret_conversation_id)
                    is_ask_helpdesk = True
                    basic_return = "Mohon maaf, pertanyaan tersebut berada di luar cakupan layanan kami. Apakah anda ingin dihubungkan ke helpdesk?"
                else:
                    basic_return = "Mohon maaf, pertanyaan tersebut berada di luar cakupan layanan kami. \nBapak/Ibu bisa ajukan pertanyaan dengan mengirim email ke kontak@oss.go.id"
            else:
                basic_return = "Mohon maaf, pertanyaan tersebut berada di luar cakupan layanan kami. Silakan ajukan pertanyaan yang berkaitan dengan investasi, perizinan berusaha, atau layanan OSS agar saya dapat membantu dengan lebih tepat."
            return await self.handle_skip_collection_answer(req=req, ret_conversation_id=ret_conversation_id, rewritten=rewritten, message=basic_return, is_ask_helpdesk=is_ask_helpdesk)
        elif collection_choice == "greeting_query":
            basic_return = "Halo! Selamat datang di layanan Kementerian Investasi & Hilirisasi/BKPM, apakah ada yang bisa saya bantu?"
        elif collection_choice == "thank_you":
            await self.repository.ingest_end_timestamp(ret_conversation_id)
            basic_return = "Terima kasih telah menghubungi layanan Kementerian Investasi & Hilirisasi/BKPM!"
        elif collection_choice == "classified_information":
            basic_return = "Mohon maaf, pertanyaan tersebut melibatkan informasi konfidensial/rahasia. Silakan tanyakan pertanyaan lain."
        
        print("Exiting handle_default_answering method")
        return_data = FinalResponse(
            conversation_id=ret_conversation_id,
            rewritten_query=rewritten,
            answer=basic_return,
            is_feedback=False
        )
        return self._build_final_response(
            req=req,
            data=return_data)

    async def retrieve_faq(self, query_vector: str):
        print("[INFO] Entering retrieve_faq method")

        results = await self.retriever_faq(query_vector, self.qdrant_faq_name, top_k=self.faq_limit)
        if not results:
            print("[INFO] No FAQ results found")
            return {"matched": False, "answer": None, "score": 0.0}
        if results[0][1] < self.faq_threshold:
            print(f"FAQ confidence is too low! Score: {results[0][1]}")
            return {"matched": False, "answer": None, "citations": []}
  
        faq_results = []
        file_ids = []
        file_names = []
        for d,s in results:
            score = s
            question_text = d.page_content
            metadata = d.metadata
            file_id = metadata.get("file_id")
            file_name = metadata.get("filename")
            answer = metadata.get("answer", None)
            if not file_id.startswith("faq-"):
                if file_id not in file_ids:
                    file_ids.append(file_id)
                    file_names.append(file_name)
            elif file_id.startswith("faq-"):
                chat_id = int(file_id.split("-", 1)[1].strip())
                answer = await self.repository.get_revision(chat_id)
            print(f"{score}\n{question_text}\n{answer}")
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
    
    async def get_filtered_chunks(self, rewritten: str, context: str, texts: list[str], fileids: list[str], filenames: list[str]):
        print("Entering get_filtered_chunks method")
        kbli_status = await self.classify_kbli(rewritten, context)
        print("kbli status: " + kbli_status)
        if kbli_status == "kbli":
            specific_status = await self.classify_specific(rewritten, context)
            print("specific status: " + specific_status)
            if specific_status == "general":
                kbli_pattern = re.compile(r"kode[:\s]*kbli[:\s]*(\d{1,5})", re.IGNORECASE)

                filtered_texts = []
                filtered_fileids = []
                filtered_filenames = []

                seen_kbli = set()

                for txt, fid, fname in zip(texts, fileids, filenames):
                    match = kbli_pattern.search(txt)
                    if not match:
                        filtered_texts.append(txt)
                        filtered_fileids.append(fid)
                        filtered_filenames.append(fname)
                        continue

                    kbli = match.group(1)

                    if kbli in seen_kbli:
                        continue

                    seen_kbli.add(kbli)
                    filtered_texts.append(txt)
                    filtered_fileids.append(fid)
                    filtered_filenames.append(fname)

                print(f"KBLIs: {seen_kbli}")
                print("Exiting get_filtered_chunks method with no removal")
                return filtered_texts, filtered_fileids, filtered_filenames

        print("Exiting get_filtered_chunks method with no removal")
        return texts, fileids, filenames
    
    async def handle_full_retrieval(self, req:ChatRequest, ret_conversation_id: str, status: bool, helpdesk_active_status: bool, context: str, rewritten: str, collection_choice: str):
        print("Entering handle_full_retrieval method")

        docs = await self.retriever(rewritten, collection_choice)

        texts = []
        fileids = []
        filenames = []
        for d, s in docs:
            texts.append(d.page_content)
            meta = d.metadata
            fileids.append(meta.get("file_id") or "unknown_source")
            filenames.append(meta.get("filename") or "unknown_source")

        texts, fileids, filenames = await self.get_filtered_chunks(rewritten=rewritten, context=context, texts=texts, fileids=fileids, filenames=filenames)

        print(fileids)
        print(filenames)
        reranked, citation_id, citation_name = await self.rerank_new(rewritten, texts, fileids, filenames)

        print("===RERANKED===")
        for r in reranked:
            print(r)
        print("==============")

        citations = list(zip(citation_id, citation_name))
        unique_names = []
        for name in citation_name:
            if name not in unique_names:
                unique_names.append(name)

        cleaned_names = [n.rsplit(".", 1)[0] for n in unique_names]

        citation_str = ", ".join(cleaned_names)
        answer = self.llm(req.query, reranked, ret_conversation_id, req.platform, status, helpdesk_active_status, collection_choice, citation_str)
        # score = await self.evaluate(req.query, context, answer)

        print("Exiting handle_full_retrieval method")
        return answer, citations
    
    async def handle_failed_answer_from_llm(self, req: ChatRequest, helpdesk_active_status: bool, ret_conversation_id: str, rewritten:str, initial_message: str, category: str, q_category: Tuple, answer: str, question_id: str, answer_id: str):
        print("Entering handle_failed_answer_from_llm method")
        await self.repository.flag_message_cannot_answer_by_id(question_id)
        ask_helpdesk = False
        if (answer.startswith('Mohon maaf, pertanyaan tersebut belum bisa kami jawab.')) and helpdesk_active_status:
            await self.repository.change_is_ask_helpdesk_status(ret_conversation_id)
            ask_helpdesk = True
        print("Exiting handle_failed_answer_from_llm method")
        return_data = FinalResponse(
            conversation_id=ret_conversation_id,
            rewritten_query=rewritten,
            category=category,
            question_category=q_category,
            answer=(initial_message or "") + answer,
            question_id=question_id,
            answer_id=answer_id,
            is_ask_helpdesk=ask_helpdesk
        )
        return self._build_final_response(
            req=req,
            data=return_data)
    
    async def check_existing_helpdesk_flow(self, req: ChatRequest):
        print("Entering check_existing_helpdesk_flow method")
        if req.conversation_id == "":
            return None

        ask_status = await self.repository.check_is_ask_helpdesk(req.conversation_id)
        if ask_status:
            return await self.handle_helpdesk_confirmation_answer(req=req)

        helpdesk_status = await self.repository.check_is_helpdesk(req.conversation_id)
        if helpdesk_status:
            return FinalResponse(
                conversation_id=req.conversation_id,
                answer="Percakapan telah dipindahkan ke helpdesk.",
                is_helpdesk=True
            )
        
        print("Exiting check_existing_helpdesk_flow method")
        return None
    
    async def chatflow_call(self, req: ChatRequest):
        print("Entering chatflow_call method")
        helpdesk_active_status = await self.repository.check_helpdesk_activation()
        helpdesk_result = await self.check_existing_helpdesk_flow(req)
        if helpdesk_result:
            return self._build_final_response(req=req, data=helpdesk_result)
            
        start_timestamp = req.start_timestamp
        ret_conversation_id = req.conversation_id
        initial_message = ""
        context = await self.repository.get_context(ret_conversation_id)

        if context == "Conversation History:":
            if ret_conversation_id == "":
                ret_conversation_id = str(uuid.uuid4())
            await self.repository.create_new_conversation(ret_conversation_id, req.platform, req.platform_unique_id)
            initial_message = await self.get_greetings_message()

        rewritten= await self.rewriter(user_query=req.query, history_context=context)
        await self.repository.give_conversation_title(session_id=ret_conversation_id, rewritten=rewritten)

        collection_choice = await self.classifier(req.query, context)

        if collection_choice == "uraian_collection":
            collection_choice = "peraturan_collection"

        if collection_choice == "helpdesk":
            return await self.handle_helpdesk_response(helpdesk_active_status=helpdesk_active_status, req=req, ret_conversation_id=ret_conversation_id, initial_message=initial_message, rewritten=rewritten)
        
        if collection_choice == "skip_collection_check" or collection_choice == "greeting_query" or collection_choice == "thank_you" or collection_choice == "classified_information":
            return await self.handle_default_answering(req=req, ret_conversation_id=ret_conversation_id, rewritten=rewritten, collection_choice=collection_choice)
        
        status = await self.repository.check_fail_history(ret_conversation_id)
        is_faq=False
        faq_response = await self.retrieve_faq(rewritten)

        if faq_response["matched"]:
            citations = faq_response["citations"]
            answer = self.llm(req.query, faq_response["faq_string"], ret_conversation_id, req.platform, status, helpdesk_active_status)
            await self.repository.flag_message_is_answered(ret_conversation_id, req.query)
            # score = await self.evaluate(req.query, context, answer)
            is_faq=True
        else:
            answer, citations = await self.handle_full_retrieval(req=req, ret_conversation_id=ret_conversation_id, status=status, helpdesk_active_status=helpdesk_active_status, context=context, rewritten=rewritten, collection_choice=collection_choice)

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
            return await self.handle_failed_answer_from_llm(req=req, helpdesk_active_status=helpdesk_active_status, ret_conversation_id=ret_conversation_id, rewritten=rewritten, initial_message=initial_message, category=category, q_category=q_category, answer=answer, question_id=question_id, answer_id=answer_id)
        
        await self.repository.ingest_citations(citations, ret_conversation_id, req.query)

        return_data = FinalResponse(
            conversation_id=ret_conversation_id,
            rewritten_query=rewritten,
            category=category,
            question_category=q_category,
            answer=(initial_message or "") + answer + "\n\n*Jawaban ini dibuat oleh AI dan mungkin tidak selalu akurat. Mohon gunakan sebagai referensi dan lakukan pengecekan tambahan bila diperlukan.*",
            question_id=question_id,
            answer_id=answer_id,
            citations=citations,
            is_answered=is_faq,
            is_faq=is_faq
        )
        return self._build_final_response(
            req=req,
            data=return_data)
