from typing import List
import google.generativeai as genai
import json
import logging
from ..models.process import Process, Document

# Configure logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

class ContentValidator:
    pass

class ProcessDecompositionAgent:
    def __init__(self, api_key: str):
        genai.configure(api_key=api_key)
        self.model = genai.GenerativeModel('gemini-1.5-flash')
        self.content_validator = ContentValidator()
        
    def _clean_json_string(self, text: str) -> str:
        """Clean and extract JSON from text"""
        # Remove any markdown code blocks
        if "```" in text:
            # Extract content between code blocks
            parts = text.split("```")
            if len(parts) >= 3:  # Has opening and closing ```
                text = parts[1]
                # Remove language identifier if present
                if text.startswith("json"):
                    text = text[4:].strip()
            else:
                text = parts[-1].strip()
        
        # Ensure we have valid JSON array brackets
        text = text.strip()
        if not text.startswith("["):
            text = "[" + text
        if not text.endswith("]"):
            text = text + "]"
            
        return text.strip()
        
    def _parse_processes(self, json_str: str) -> List[Process]:
        """Parse JSON string into Process objects with error handling"""
        logger.debug(f"Attempting to parse JSON: {json_str}")
        
        try:
            processes_data = json.loads(json_str)
            if not isinstance(processes_data, list):
                raise ValueError(f"Expected JSON array, got {type(processes_data)}")
            
            processes = []
            for p in processes_data:
                if not isinstance(p, dict):
                    raise ValueError(f"Expected dict for process, got {type(p)}")
                # Ensure required fields
                p["id"] = p.get("id", str(len(processes)))
                p["name"] = p.get("name", f"Process {len(processes) + 1}")
                p["description"] = p.get("description", "No description provided")
                p["sub_processes"] = p.get("sub_processes", [])
                
                # Create phases if they don't exist
                if "phases" not in p:
                    p["phases"] = []
                    phase_map = {}
                    
                    # Extract phase information from sub-process IDs
                    for sub in p["sub_processes"]:
                        sub_id = sub.get("id", "")
                        if "_phase" in sub_id:
                            phase_num = sub_id.split("_phase")[1].split("_")[0]
                            phase_id = f"{p['id']}_phase{phase_num}"
                            
                            if phase_id not in phase_map:
                                phase_map[phase_id] = {
                                    "id": phase_id,
                                    "name": f"Fase {phase_num}",
                                    "description": f"Fase {phase_num} del proceso",
                                    "order": int(phase_num),
                                    "objectives": []
                                }
                    
                    # Add phases in order
                    p["phases"] = sorted(phase_map.values(), key=lambda x: x["order"])
                
                # Ensure each sub-process has required fields
                for idx, sub in enumerate(p["sub_processes"]):
                    sub["id"] = sub.get("id", f"{p['id']}_sub_{idx}")
                    sub["name"] = sub.get("name", f"Step {idx + 1}")
                    sub["description"] = sub.get("description", "No description provided")
                    sub["order"] = sub.get("order", idx + 1)
                    
                    # Assign phase_id based on sub-process ID pattern
                    if "_phase" in sub["id"]:
                        phase_num = sub["id"].split("_phase")[1].split("_")[0]
                        sub["phase_id"] = f"{p['id']}_phase{phase_num}"
                    else:
                        # If no phase in ID, assign to first phase or create one
                        if not p["phases"]:
                            default_phase = {
                                "id": f"{p['id']}_phase1",
                                "name": "Fase 1",
                                "description": "Fase principal del proceso",
                                "order": 1,
                                "objectives": []
                            }
                            p["phases"].append(default_phase)
                        sub["phase_id"] = p["phases"][0]["id"]
                
                processes.append(Process.parse_obj(p))
            
            return processes
            
        except json.JSONDecodeError as e:
            logger.error(f"JSON decode error: {e}")
            logger.error(f"Problematic JSON: {json_str}")
            raise ValueError(f"Invalid JSON format: {e}")
        except Exception as e:
            logger.error(f"Error parsing processes: {e}")
            logger.error(f"Input data: {json_str}")
            raise ValueError(f"Error creating processes: {e}")

    def _validate_extraction(self, original_text: str, extracted_info: dict) -> bool:
        """Validate that extracted information exists in original text"""
        original_text = original_text.lower()
        
        # Check each piece of extracted information
        for key, value in extracted_info.items():
            if isinstance(value, str) and value.lower() not in original_text:
                if value != "No description provided":  # Skip default values
                    logger.warning(f"Potentially hallucinated content in {key}: {value}")
                    return False
        return True

    def call_api(self, *args, **kwargs):
        """Call the Gemini API"""
        try:
            return self.model.generate_content(*args, **kwargs)
        except Exception as e:
            logger.error(f"API call failed: {str(e)}")
            raise

    async def analyze_document(self, document: Document) -> List[Process]:
        """
        Analyze the document content and extract processes with strict validation.
        """
        prompt = f"""
        Analiza este documento y extrae SOLO los procesos y la información que está EXPLÍCITAMENTE mencionada en el texto.
        
        REGLAS ESTRICTAS:
        1. SOLO extrae procesos y pasos que estén EXPLÍCITAMENTE mencionados
        2. NO inventes ni asumas información que no esté presente
        3. Si un dato no está mencionado, déjalo vacío o usa 'No especificado'
        4. Usa EXACTAMENTE la misma terminología que aparece en el texto
        5. Mantén el mismo nivel de detalle que el texto original
        6. Si algo es ambiguo, déjalo tal cual - no intentes clarificarlo
        
        Documento a analizar:
        {document.content}
        
        Extrae la información en este formato JSON:
        [
            {{{{
                "id": "process_1",
                "name": "EXACTAMENTE como aparece en el texto",
                "description": "SOLO información explícitamente mencionada",
                "category": "SOLO si está explícitamente mencionado",
                "sub_processes": [
                    {{{{
                        "id": "sub_1",
                        "name": "EXACTAMENTE como aparece en el texto",
                        "description": "SOLO información explícitamente mencionada",
                        "order": "Número basado en el orden en el texto"
                    }}}}
                ]
            }}}}
        ]
        
        """
        
        max_attempts = 3
        for attempt in range(max_attempts):
            response = self.call_api(prompt)
            json_str = self._clean_json_string(response.text)
            
            try:
                processes_data = json.loads(json_str)
                
                # Validate each process against original text
                valid_processes = []
                for process_data in processes_data:
                    if self._validate_extraction(document.content, process_data):
                        valid_processes.append(process_data)
                    else:
                        logger.warning(f"Removing invalid process: {process_data['name']}")
                
                if valid_processes:
                    return [Process.parse_obj(p) for p in valid_processes]
                
            except (json.JSONDecodeError, ValueError) as e:
                logger.error(f"Attempt {attempt + 1}: Error processing response - {str(e)}")
        
        # If all attempts fail, return an empty list
        logger.error("Failed to extract valid processes after all attempts")
        return []

    def analyze_document_sync(self, document: Document) -> List[Process]:
        """Synchronous version of analyze_document"""
        prompt = f"""
        Analyze this document and extract all processes as a JSON array. Format the output similar to this example:
        [
            {{{{
                "id": "process_1",
                "name": "Implementación y Configuración del Sistema ODU",
                "description": "Este proceso describe la implementación y configuración del sistema ODU para la gestión de la fabricación...",
                "category": "Administrativo",
                "priority": 1,
                "sub_processes": [
                    {{{{
                        "id": "p1_phase1_step1",
                        "name": "Acceso al producto",
                        "description": "Ingresar a la sección de 'Productos' dentro del sistema ODU.",
                        "order": 1,
                        "estimated_duration": "15 minutos",
                        "dependencies": []
                    }}}},
                    {{{{
                        "id": "p1_phase1_step2",
                        "name": "Seleccionar producto terminado",
                        "description": "Elegir un producto terminado que requiera fabricación (ej: Gtrack Pro).",
                        "order": 2,
                        "estimated_duration": "5 minutos",
                        "dependencies": ["p1_phase1_step1"]
                    }}}}
                ]
            }}}}
        ]

        Important guidelines:
        1. Break down each process into detailed, actionable steps
        2. Include clear descriptions for each step
        3. Organize steps into logical phases when applicable
        4. Specify dependencies between steps when relevant
        5. Provide estimated durations when possible
        6. Include any specific roles or responsibilities mentioned
        7. Maintain proper sequencing of steps

        Document content to analyze:
        {document.content}

        Respond only with the JSON array following the exact format shown above.
        """
        
        response = self.call_api(prompt)
        json_str = self._clean_json_string(response.text)
        return self._parse_processes(json_str)
