import uuid
import os
from fastapi.responses import FileResponse
from research_and_analyst.utils.model_loader import ModelLoader
from research_and_analyst.workflows.report_generator_workflow import AutonomousReportGenerator
from research_and_analyst.logger import GLOBAL_LOGGER
from research_and_analyst.exception.custom_exception import ResearchAnalystException
from research_and_analyst.security import get_redactor
from langgraph.checkpoint.memory import MemorySaver

_shared_memory = MemorySaver()

class ReportService:
    def __init__(self):
        loader = ModelLoader()
        self.llm = loader.load_llm()
        # Embeddings are optional (only needed for Pinecone section storage);
        # if the embedding provider isn't configured this stays None and
        # Pinecone storage is skipped rather than failing the whole service.
        try:
            self.embeddings = loader.load_embeddings()
        except Exception:
            self.embeddings = None
        self.reporter = AutonomousReportGenerator(self.llm, embeddings=self.embeddings)
        self.reporter.memory = _shared_memory 
        self.graph = self.reporter.build_graph()
        self.logger = GLOBAL_LOGGER.bind(module="ReportService")
        self.redactor = get_redactor()

    def start_report_generation(self, topic: str, max_analysts: int):
        """Trigger the autonomous report pipeline."""
        try:
            # Redact PII from the user-supplied topic before it enters any prompt
            topic, pii_hits = self.redactor.redact(topic)
            if pii_hits:
                self.logger.info("PII redacted from submitted topic", pii_entity_count=pii_hits)

            thread_id = str(uuid.uuid4())
            thread = {
                "configurable": {"thread_id": thread_id},
                "callbacks": self.reporter.tracing_callbacks,
            }
            self.logger.info("Starting report pipeline", topic=topic, thread_id=thread_id)

            for _ in self.graph.stream({"topic": topic, "max_analysts": max_analysts}, thread, stream_mode="values"):
                pass

            return {"thread_id": thread_id, "message": "Pipeline initiated successfully."}
        except Exception as e:
            self.logger.error("Error initiating report generation", error=str(e))
            raise ResearchAnalystException("Failed to start report generation", e)

    def submit_feedback(self, thread_id: str, feedback: str):
        """Update human feedback in graph state."""
        try:
            thread = {
                "configurable": {"thread_id": thread_id},
                "callbacks": self.reporter.tracing_callbacks,
            }
            self.graph.update_state(thread, {"human_analyst_feedback": feedback}, as_node="human_feedback")
            self.logger.info("Feedback updated", thread_id=thread_id)
            for _ in self.graph.stream(None, thread, stream_mode="values"):
                pass
            return {"message": "Feedback processed successfully"}
        except Exception as e:
            self.logger.error("Error updating feedback", error=str(e))
            raise ResearchAnalystException("Failed to update feedback", e)
        
    def get_report_status(self, thread_id: str):
        """Fetch latest state or final report."""
        try:
            thread = {"configurable": {"thread_id": thread_id}}
            state = self.graph.get_state(thread)
            final_report = state.values.get("final_report")
            topic = state.values.get("topic", "AI_Report") 

            if final_report:
                # now topic-based report folder name
                file_docx = self.reporter.save_report(final_report, topic, "docx")
                file_pdf = self.reporter.save_report(final_report, topic, "pdf")
                eval_scores = self.reporter.evaluate_report_quality()
                return {
                    "status": "completed",
                    "docx_path": file_docx,
                    "pdf_path": file_pdf,
                    "quality_scores": eval_scores,
                }
            return {"status": "in_progress"}
        except Exception as e:
            self.logger.error("Error fetching report status", error=str(e))
            raise ResearchAnalystException("Failed to fetch report status", e)

    @staticmethod
    def download_file(file_name: str):
        """Download generated report."""
        report_dir = os.path.join(os.getcwd(),"src", "generated_report")
        for root, _, files in os.walk(report_dir):
            if file_name in files:
                return FileResponse(
                    path=os.path.join(root, file_name),
                    filename=file_name,
                    media_type="application/octet-stream"
                )
        return {"error": f"File {file_name} not found"}