class RetrievalService:
    def retrieve(self, document_id: str, question: str) -> dict:
        return {
            "answer": "This is a placeholder answer. PageIndex integration will be added later.",
            "citations": [],
            "trace": "No trace available yet.",
        }
