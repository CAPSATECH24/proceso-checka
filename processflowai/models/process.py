from typing import List, Optional, Dict
from pydantic import BaseModel, Field
from enum import Enum

class ProcessStatus(str, Enum):
    """Estado del proceso o subproceso"""
    NOT_STARTED = "No iniciado"
    IN_PROGRESS = "En progreso"
    COMPLETED = "Completado"
    BLOCKED = "Bloqueado"
    ON_HOLD = "En espera"

class RiskLevel(str, Enum):
    """Nivel de riesgo del proceso"""
    LOW = "Bajo"
    MEDIUM = "Medio"
    HIGH = "Alto"
    CRITICAL = "Crítico"

class ValidationCriteria(BaseModel):
    """Criterios de validación para un subproceso"""
    description: str = Field(..., description="Descripción del criterio")
    expected_result: str = Field(..., description="Resultado esperado")
    validation_method: Optional[str] = Field(None, description="Método de validación")

class Resource(BaseModel):
    """Recurso necesario para un subproceso"""
    name: str = Field(..., description="Nombre del recurso")
    type: str = Field(..., description="Tipo de recurso (humano, material, sistema, etc.)")
    quantity: Optional[str] = Field(None, description="Cantidad necesaria")
    availability: Optional[str] = Field(None, description="Disponibilidad del recurso")

class Phase(BaseModel):
    """Representa una fase dentro de un proceso"""
    id: str = Field(..., description="Identificador único de la fase")
    name: str = Field(..., description="Nombre de la fase")
    description: str = Field(..., description="Descripción detallada de la fase")
    order: int = Field(..., description="Orden de la fase en el proceso")
    objectives: List[str] = Field(default_factory=list, description="Objetivos de la fase")
    status: ProcessStatus = Field(default=ProcessStatus.NOT_STARTED, description="Estado actual de la fase")

class ProcessMetrics(BaseModel):
    """Métricas y KPIs del proceso"""
    total_duration: str = Field(..., description="Duración total estimada")
    critical_path: List[str] = Field(default_factory=list, description="IDs de los pasos en la ruta crítica")
    risk_level: RiskLevel = Field(default=RiskLevel.LOW, description="Nivel de riesgo del proceso")
    completion_percentage: Optional[float] = Field(None, description="Porcentaje de completitud")
    kpis: Dict[str, str] = Field(default_factory=dict, description="KPIs específicos del proceso")

class SubProcess(BaseModel):
    """Representa un subproceso dentro de un proceso principal"""
    id: str = Field(..., description="Identificador único del subproceso")
    phase_id: str = Field(..., description="ID de la fase a la que pertenece")
    name: str = Field(..., description="Nombre del subproceso")
    description: str = Field(..., description="Descripción detallada del subproceso")
    order: int = Field(..., description="Orden de ejecución dentro de la fase")
    estimated_duration: Optional[str] = Field(None, description="Duración estimada")
    dependencies: List[str] = Field(default_factory=list, description="IDs de subprocesos dependientes")
    owner: Optional[str] = Field(None, description="Responsable del subproceso")
    required_resources: List[Resource] = Field(default_factory=list, description="Recursos necesarios")
    validation_criteria: List[ValidationCriteria] = Field(default_factory=list, description="Criterios de validación")
    expected_output: Optional[str] = Field(None, description="Resultado esperado")
    notes: Optional[str] = Field(None, description="Notas adicionales")
    status: ProcessStatus = Field(default=ProcessStatus.NOT_STARTED, description="Estado actual")
    actual_duration: Optional[str] = Field(None, description="Duración real (si está completado)")
    issues: List[str] = Field(default_factory=list, description="Problemas o impedimentos")

class Process(BaseModel):
    """Representa un proceso principal extraído del documento"""
    id: str = Field(..., description="Identificador único del proceso")
    name: str = Field(..., description="Nombre del proceso")
    description: str = Field(..., description="Descripción detallada del proceso")
    category: Optional[str] = Field(None, description="Categoría o tipo de proceso")
    priority: Optional[int] = Field(None, description="Nivel de prioridad (1-5)")
    owner: Optional[str] = Field(None, description="Responsable del proceso")
    status: ProcessStatus = Field(default=ProcessStatus.NOT_STARTED, description="Estado actual")
    phases: List[Phase] = Field(default_factory=list, description="Fases del proceso")
    sub_processes: List[SubProcess] = Field(default_factory=list, description="Lista de subprocesos")
    metrics: Optional[ProcessMetrics] = Field(None, description="Métricas del proceso")
    start_date: Optional[str] = Field(None, description="Fecha de inicio planificada")
    end_date: Optional[str] = Field(None, description="Fecha de finalización planificada")
    stakeholders: List[str] = Field(default_factory=list, description="Interesados en el proceso")
    documentation: Dict[str, str] = Field(default_factory=dict, description="Enlaces a documentación relacionada")

class Document(BaseModel):
    """Representa un documento subido con procesos extraídos"""
    id: str = Field(..., description="Identificador único del documento")
    title: str = Field(..., description="Título del documento")
    content: str = Field(..., description="Contenido original del documento")
    processes: List[Process] = Field(default_factory=list, description="Procesos extraídos")
    created_at: Optional[str] = Field(None, description="Fecha de creación")
    updated_at: Optional[str] = Field(None, description="Última actualización")
    version: Optional[str] = Field(None, description="Versión del documento")
    tags: List[str] = Field(default_factory=list, description="Etiquetas o categorías")
