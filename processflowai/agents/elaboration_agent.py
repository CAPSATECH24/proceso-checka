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
        Basándote ÚNICAMENTE en esta información del proceso, genera una descripción clara y detallada:
        Nombre del Proceso: {process.name}
        Descripción Actual: {process.description}
        Categoría: {process.category if process.category else 'No especificada'}
        
        REGLAS ESTRICTAS:
        1. SOLO incluir información que esté EXPLÍCITAMENTE mencionada en el input
        2. NO agregar pasos, requisitos o detalles que no estén en el texto original
        3. NO hacer suposiciones sobre el proceso
        4. NO incluir información de conocimiento general o experiencia previa
        5. Mantener el mismo significado y alcance del texto original
        6. Usar un lenguaje claro y profesional
        7. Si algo no está claro o falta información, NO intentar completarla
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
        Basándote ÚNICAMENTE en esta información del subproceso:

        Contexto del Proceso Principal:
        {process_context}

        Subproceso: {sub_process.name}
        Descripción Base: {sub_process.description}
        Orden: {sub_process.order}

        Genera instrucciones paso a paso detalladas siguiendo estas reglas ESTRICTAS:

        REGLAS CRÍTICAS DE CONTENIDO:
        1. SOLO incluir pasos que estén EXPLÍCITAMENTE mencionados en el input
        2. NO agregar pasos intermedios que no estén mencionados
        3. NO asumir acciones basadas en experiencia o conocimiento previo
        4. NO completar información faltante con suposiciones
        5. Si un paso no está claro, mantenerlo exactamente como está en el input
        6. NO agregar detalles técnicos o explicaciones no mencionadas
        7. Si falta información sobre cómo realizar un paso, NO intentar explicarlo

        REGLAS DE FORMATO:
        1. Usar SOLO números simples para cada paso (1, 2, 3, etc.)
        2. NO usar números compuestos o subniveles (NO usar 1.1, 2.1, etc.)
        3. NO repetir números
        4. Cada paso debe comenzar con un verbo en infinitivo
        5. Mantener el texto EXACTAMENTE como aparece en el input

        EJEMPLO CORRECTO (si el input dice exactamente esto):
        Input: "Abrir inventario, hacer clic en nuevo, escribir proveedor"
        1. Abrir inventario
        2. Hacer clic en nuevo
        3. Escribir proveedor

        EJEMPLO INCORRECTO:
        Input: "Abrir inventario"
        1. Abrir el sistema
        2. Ingresar credenciales  <-- MAL: No mencionado en el input
        3. Navegar al módulo de inventario  <-- MAL: No mencionado en el input
        4. Abrir inventario
        """
        
        try:
            response = self.call_api(prompt)
            description = response.text.strip()
            
            # Procesar la respuesta para asegurar formato correcto
            lines = description.split('\n')
            processed_lines = []
            
            for line in lines:
                line = line.strip()
                if not line:  # Ignorar líneas vacías
                    continue
                
                # Limpiar cualquier numeración existente
                if line[0].isdigit():
                    # Si la línea comienza con un número, eliminar la numeración
                    parts = line.split('.')
                    if len(parts) > 1:
                        line = '.'.join(parts[1:]).strip()
                    else:
                        # Buscar el primer espacio después del número
                        space_index = line.find(' ')
                        if space_index != -1:
                            line = line[space_index:].strip()
                
                # Agregar la línea sin numeración
                if line:
                    processed_lines.append(line)
            
            return '\n'.join(processed_lines)
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
