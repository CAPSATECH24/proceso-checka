from typing import List, Optional
from uuid import uuid4
from .models.process import Document, Process
from .agents.decomposition_agent import ProcessDecompositionAgent
from .agents.elaboration_agent import ProcessElaborationAgent
from .utils.api_manager import APIRateLimiter

class ProcessFlowAI:
    def __init__(self, 
                 api_key: str,
                 calls_per_minute: int = 60):
        """
        Initialize ProcessFlowAI application.
        
        Args:
            api_key: Gemini API key
            calls_per_minute: Rate limit for API calls
        """
        self.decomposition_agent = ProcessDecompositionAgent(api_key)
        self.elaboration_agent = ProcessElaborationAgent(api_key)
        self.rate_limiter = APIRateLimiter(calls_per_minute)
        
    async def process_document(self, 
                             content: str, 
                             title: Optional[str] = None) -> Document:
        """
        Process a document to extract and elaborate on processes.
        
        Args:
            content: Document content to process
            title: Optional document title
            
        Returns:
            Document object with extracted and elaborated processes
        """
        # Create document
        doc = Document(
            id=str(uuid4()),
            title=title or "Untitled Document",
            content=content,
            processes=[]
        )
        
        # Extract processes
        processes = await self.rate_limiter.execute(
            self.decomposition_agent.analyze_document,
            doc
        )
        
        # Elaborate on each process
        elaborated_processes = []
        for process in processes:
            elaborated_process = await self.rate_limiter.execute(
                self.elaboration_agent.elaborate_process,
                process
            )
            elaborated_processes.append(elaborated_process)
        
        doc.processes = elaborated_processes
        return doc
    
    def process_document_sync(self,
                            content: str,
                            title: Optional[str] = None) -> Document:
        """Synchronous version of process_document"""
        # Create document
        doc = Document(
            id=str(uuid4()),
            title=title or "Untitled Document",
            content=content,
            processes=[]
        )
        
        # Extract processes
        processes = self.decomposition_agent.analyze_document_sync(doc)
        
        # Elaborate on each process
        elaborated_processes = []
        for process in processes:
            elaborated_process = self.elaboration_agent.elaborate_process_sync(process)
            elaborated_processes.append(elaborated_process)
        
        doc.processes = elaborated_processes
        return doc
