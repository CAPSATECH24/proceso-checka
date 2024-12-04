from typing import Dict, List
import google.generativeai as genai
import logging
from ..models.process import Process, SubProcess, ProcessStatus
from ratelimit import limits, sleep_and_retry
import time
from datetime import datetime, timedelta
import json

# Configure logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

# Define rate limits as a global constant
CALLS_PER_MINUTE = 15
CALLS_PER_DAY = 1500
TOKENS_PER_MINUTE = 1_000_000

class ProcessElaborationAgent:
    def __init__(self, api_key: str):
        genai.configure(api_key=api_key)
        self.model = genai.GenerativeModel('gemini-1.5-flash')
    
    def _elaborate_process_description(self, process: Process) -> str:
        """Elaborate on the main process description"""
        prompt = f"""
        Basándote en esta información del proceso, genera una descripción clara y detallada:
        Nombre del Proceso: {process.name}
        Descripción Actual: {process.description}
        Categoría: {process.category if process.category else 'No especificada'}
        
        Por favor:
        1. Mantén el mismo significado y alcance
        2. Usa un lenguaje claro y profesional
        3. Organiza la información de manera lógica
        4. Incluye el objetivo principal del proceso
        5. Menciona los resultados esperados
        6. Destaca cualquier requisito importante
        """
        
        try:
            response = self.call_api(prompt)
            return response.text.strip()
        except Exception as e:
            logger.error(f"Error elaborating process description: {str(e)}")
            return process.description

    def _elaborate_subprocess(self, sub_process: SubProcess, process_context: str) -> str:
        """Elaborate on a sub-process with detailed step-by-step instructions"""
        prompt = f"""
        Basándote en esta información del subproceso:

        Contexto del Proceso Principal:
        {process_context}

        Subproceso: {sub_process.name}
        Descripción Base: {sub_process.description}
        Orden: {sub_process.order}

        Genera una descripción secuencial del proceso siguiendo este formato:

        1. ALCANCE DEL PROCESO
        [Describir brevemente el alcance específico mencionado en el input]

        2. DESARROLLO DEL PROCESO
        2.1. [Acción específica con verbo en infinitivo]
             "Describir la acción exacta a realizar"

        2.2. [Siguiente acción con verbo en infinitivo]
             "Describir la siguiente acción exacta"
             
        2.3. [Continuar con la secuencia de acciones]
             "Mantener el mismo nivel de detalle"
        ...

        3. CRITERIOS DE CONTROL
        [Solo si se mencionan específicamente puntos de verificación]
        - Qué se debe verificar exactamente
        - Cuál es el resultado esperado

        REGLAS:
        1. Usar verbos en infinitivo al inicio de cada acción
        2. Mantener la secuencia exacta mencionada
        3. Ser específico y directo en cada paso
        4. NO agregar información no mencionada
        5. NO asumir pasos intermedios
        """
        
        try:
            response = self.call_api(prompt)
            description = response.text.strip()
            
            # Validar que la respuesta contenga las secciones requeridas
            required_sections = [
                "1. ALCANCE DEL PROCESO",
                "2. DESARROLLO DEL PROCESO",
                "3. CRITERIOS DE CONTROL"
            ]
            
            missing_sections = [section for section in required_sections if section not in description]
            if missing_sections:
                logger.warning(f"Descripción incompleta. Faltan secciones: {missing_sections}")
                # Intentar regenerar la descripción si faltan secciones
                return self._elaborate_subprocess(sub_process, process_context)
            
            return description
        except Exception as e:
            logger.error(f"Error elaborating subprocess: {str(e)}")
            return sub_process.description

    def _estimate_duration(self, description: str) -> str:
        """Estimate duration based on the step description"""
        prompt = f"""
        Based on this step description, estimate a realistic duration:
        {description}
        
        Consider:
        1. Complexity of the task
        2. Required system interactions
        3. Manual vs automated steps
        4. Potential waiting times
        
        Respond with ONLY the estimated duration in a clear format (e.g., "15 minutes", "1 hour", "2-3 days").
        """
        
        try:
            response = self.call_api(prompt)
            return response.text.strip()
        except Exception as e:
            logger.error(f"Error estimating duration: {str(e)}")
            return "Duration not specified"

    @sleep_and_retry
    @limits(calls=15, period=60)
    def call_api(self, *args, **kwargs):
        """Call the API with rate limiting"""
        try:
            current_time = datetime.now()
            if not hasattr(self, 'last_call_time') or current_time.minute != self.last_call_time.minute:
                self.calls_this_minute = 1
                self.last_call_time = current_time
            else:
                self.calls_this_minute += 1
            
            if not hasattr(self, 'today') or current_time.date() != self.today:
                self.today = current_time.date()
                self.calls_today = 1
            else:
                self.calls_today += 1
            
            if self.calls_today > CALLS_PER_DAY:
                logger.error("Daily rate limit exceeded. Please try again tomorrow.")
                raise Exception("Daily rate limit exceeded")
            
            return self.model.generate_content(*args, **kwargs)
        except Exception as e:
            if "429" in str(e) or "Resource has been exhausted" in str(e):
                logger.warning("Rate limit exceeded. Implementing exponential backoff...")
                wait_time = min(300, 2 ** (self.calls_this_minute / CALLS_PER_MINUTE * 10))
                logger.info(f"Waiting {wait_time:.2f} seconds before retrying...")
                time.sleep(wait_time)
                raise Exception(f"Rate limit exceeded. Retry after {wait_time:.2f} seconds") from e
            raise

    async def elaborate_process(self, process: Process) -> Process:
        """Elaborate on a process and its sub-processes using Gemini."""
        try:
            process.description = self._elaborate_process_description(process)
            
            process_context = f"""
            Proceso Principal: {process.name}
            Descripción: {process.description}
            Categoría: {process.category if process.category else 'No especificada'}
            """
            
            for sub_process in process.sub_processes:
                sub_process.description = self._elaborate_subprocess(sub_process, process_context)
                
                if not sub_process.estimated_duration:
                    sub_process.estimated_duration = self._estimate_duration(sub_process.description)
            
            return process
        except Exception as e:
            logger.error(f"Error in elaborate_process: {str(e)}")
            return process

    def elaborate_process_sync(self, process: Process) -> Process:
        """Synchronous version of elaborate_process"""
        try:
            process.description = self._elaborate_process_description(process)
            
            process_context = f"""
            Proceso Principal: {process.name}
            Descripción: {process.description}
            Categoría: {process.category if process.category else 'No especificada'}
            """
            
            for sub_process in process.sub_processes:
                sub_process.description = self._elaborate_subprocess(sub_process, process_context)
                
                if not sub_process.estimated_duration:
                    sub_process.estimated_duration = self._estimate_duration(sub_process.description)
            
            return process
        except Exception as e:
            logger.error(f"Error in elaborate_process_sync: {str(e)}")
            return process
