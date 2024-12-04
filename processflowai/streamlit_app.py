import streamlit as st
import asyncio
from typing import Optional
import json
from pathlib import Path
import sys
import os
from utils.word_generator import generate_process_document

# Add parent directory to Python path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from processflowai.app import ProcessFlowAI
from processflowai.models.process import Document, Process, SubProcess

# Configure Streamlit page
st.set_page_config(
    page_title="ProcessFlowAI",
    page_icon="🔄",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Initialize session state
if 'app' not in st.session_state:
    st.session_state.app = None
if 'current_document' not in st.session_state:
    st.session_state.current_document = None

def display_process(process: Process):
    """Display a process and its sub-processes in the UI"""
    st.markdown(f"## 📋 {process.name}")
    
    # Process Header
    col1, col2, col3 = st.columns(3)
    with col1:
        st.markdown(f"**Categoría:** {process.category or 'No especificada'}")
        st.markdown(f"**Prioridad:** {'🔴' * process.priority if process.priority else 'No especificada'}")
    with col2:
        st.markdown(f"**Responsable:** {process.owner or 'No asignado'}")
        st.markdown(f"**Estado:** {process.status.value}")
    with col3:
        if process.metrics:
            st.markdown(f"**Nivel de Riesgo:** {process.metrics.risk_level.value}")
            st.markdown(f"**Duración Total:** {process.metrics.total_duration}")
    
    # Process Description
    st.markdown("### Descripción")
    st.markdown(process.description)
    
    # Process Details
    if process.start_date or process.end_date:
        st.markdown("### Fechas")
        cols = st.columns(2)
        with cols[0]:
            st.markdown(f"**Inicio:** {process.start_date or 'No definido'}")
        with cols[1]:
            st.markdown(f"**Fin:** {process.end_date or 'No definido'}")
    
    # Stakeholders
    if process.stakeholders:
        st.markdown("### Interesados")
        for stakeholder in process.stakeholders:
            st.markdown(f"- {stakeholder}")
    
    # Phases and Sub-processes
    if process.phases:
        st.markdown("### Fases y Pasos")
        tabs = st.tabs([f"📑 {phase.name}" for phase in sorted(process.phases, key=lambda x: x.order)])
        
        for i, phase in enumerate(sorted(process.phases, key=lambda x: x.order)):
            with tabs[i]:
                st.markdown(f"**Descripción:** {phase.description}")
                if phase.objectives:
                    st.markdown("**Objetivos:**")
                    for obj in phase.objectives:
                        st.markdown(f"- {obj}")
                
                # Display sub-processes for this phase
                phase_steps = [sub for sub in process.sub_processes if sub.phase_id == phase.id]
                if phase_steps:
                    st.markdown("#### Pasos de esta fase:")
                    for sub in sorted(phase_steps, key=lambda x: x.order):
                        with st.container():
                            st.markdown(f"##### 🔹 {sub.order}. {sub.name} ({sub.status.value})")
                            
                            # Basic Info
                            st.markdown(f"**Descripción:** {sub.description}")
                            
                            # Details in columns
                            col1, col2 = st.columns(2)
                            with col1:
                                st.markdown(f"**Responsable:** {sub.owner or 'No asignado'}")
                                st.markdown(f"**Duración Estimada:** {sub.estimated_duration or 'No especificada'}")
                                if sub.actual_duration:
                                    st.markdown(f"**Duración Real:** {sub.actual_duration}")
                            with col2:
                                st.markdown(f"**Estado:** {sub.status.value}")
                            
                            # Resources
                            if sub.required_resources:
                                st.markdown("**Recursos Necesarios:**")
                                for resource in sub.required_resources:
                                    st.markdown(f"- {resource.name} ({resource.type})")
                                    if resource.quantity:
                                        st.markdown(f"  - Cantidad: {resource.quantity}")
                                    if resource.availability:
                                        st.markdown(f"  - Disponibilidad: {resource.availability}")
                            
                            # Validation Criteria
                            if sub.validation_criteria:
                                st.markdown("**Criterios de Validación:**")
                                for criteria in sub.validation_criteria:
                                    st.markdown(f"- {criteria.description}")
                                    st.markdown(f"  - Resultado esperado: {criteria.expected_result}")
                                    if criteria.validation_method:
                                        st.markdown(f"  - Método: {criteria.validation_method}")
                            
                            # Dependencies
                            if sub.dependencies:
                                st.markdown("**Dependencias:**")
                                for dep_id in sub.dependencies:
                                    dep_name = next((s.name for s in process.sub_processes if s.id == dep_id), dep_id)
                                    st.markdown(f"- {dep_name}")
                            
                            # Expected Output
                            if sub.expected_output:
                                st.markdown(f"**Resultado Esperado:** {sub.expected_output}")
                            
                            # Issues
                            if sub.issues:
                                st.markdown("**Problemas/Impedimentos:**")
                                for issue in sub.issues:
                                    st.markdown(f"- {issue}")
                            
                            # Notes
                            if sub.notes:
                                st.markdown(f"**Notas:** {sub.notes}")
                            
                            st.markdown("---")
    
    # Process Metrics
    if process.metrics:
        st.markdown("### Métricas del Proceso")
        cols = st.columns(2)
        with cols[0]:
            st.markdown(f"**Duración Total:** {process.metrics.total_duration}")
            st.markdown(f"**Nivel de Riesgo:** {process.metrics.risk_level.value}")
            if process.metrics.completion_percentage is not None:
                st.progress(process.metrics.completion_percentage / 100)
                st.markdown(f"**Progreso:** {process.metrics.completion_percentage}%")
        
        with cols[1]:
            if process.metrics.critical_path:
                st.markdown("**Ruta Crítica:**")
                for step_id in process.metrics.critical_path:
                    step_name = next((s.name for s in process.sub_processes if s.id == step_id), step_id)
                    st.markdown(f"- {step_name}")
            
            if process.metrics.kpis:
                st.markdown("**KPIs:**")
                for kpi, value in process.metrics.kpis.items():
                    st.markdown(f"- {kpi}: {value}")
    
    # Documentation
    if process.documentation:
        st.markdown("### Documentación")
        for doc_name, doc_url in process.documentation.items():
            st.markdown(f"- [{doc_name}]({doc_url})")

    # Export to Word
    subprocesses_data = []
    for subprocess in process.sub_processes:
        subprocesses_data.append({
            'name': subprocess.name,
            'description': subprocess.description,
            'order': subprocess.order
        })
    
    if st.button("📄 Exportar a Word"):
        try:
            filepath = generate_process_document(
                process.name,
                process.description,
                subprocesses_data
            )
            
            # Leer el archivo generado
            with open(filepath, 'rb') as f:
                bytes_data = f.read()
            
            # Ofrecer el archivo para descarga
            st.download_button(
                label="⬇️ Descargar Documento Word",
                data=bytes_data,
                file_name=f"{process.name.replace(' ', '_')}.docx",
                mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document"
            )
            
            st.success(f"Documento generado exitosamente!")
            
        except Exception as e:
            st.error(f"Error al generar el documento: {str(e)}")

def save_document(doc: Document):
    """Save document to JSON file"""
    output_dir = Path("output")
    output_dir.mkdir(exist_ok=True)
    
    file_path = output_dir / f"{doc.id}.json"
    with open(file_path, 'w') as f:
        json.dump(doc.model_dump(), f, indent=2)
    
    return file_path

def main():
    st.title("ProcessFlowAI 🔄")
    st.markdown("""
    Upload a document describing a process or project, and I'll help break it down 
    into structured processes and sub-processes using Google's Gemini AI.
    """)
    
    # Sidebar configuration
    with st.sidebar:
        st.header("Configuration")
        api_key = st.text_input(
            "Enter your Gemini API Key",
            type="password",
            help="Get your API key from https://makersuite.google.com/app/apikey"
        )
        
        calls_per_min = st.slider(
            "API Calls per Minute",
            min_value=10,
            max_value=100,
            value=60
        )
        
        if api_key and st.button("Update Configuration"):
            try:
                st.session_state.app = ProcessFlowAI(
                    api_key=api_key,
                    calls_per_minute=calls_per_min
                )
                st.success("Configuration updated successfully!")
            except Exception as e:
                st.error(f"Failed to initialize app: {str(e)}")
    
    # Main content area
    if st.session_state.app is None:
        st.warning("Please enter your Gemini API key in the sidebar to continue.")
        return
    
    col1, col2 = st.columns([2, 1])
    
    with col1:
        # Document input
        st.header("Document Input")
        input_method = st.radio(
            "Choose input method:",
            ["Text Input", "File Upload"]
        )
        
        document_content = None
        document_title = None
        
        if input_method == "Text Input":
            document_title = st.text_input("Document Title (optional)")
            document_content = st.text_area(
                "Enter your process description",
                height=300,
                placeholder="Describe your process or project here..."
            )
        else:
            uploaded_file = st.file_uploader(
                "Upload a text document",
                type=["txt"]
            )
            if uploaded_file:
                document_title = uploaded_file.name
                document_content = uploaded_file.getvalue().decode()
        
        if st.button("Process Document") and document_content:
            with st.spinner("Processing document with Gemini AI..."):
                try:
                    # Process the document
                    doc = st.session_state.app.process_document_sync(
                        content=document_content,
                        title=document_title
                    )
                    st.session_state.current_document = doc
                    
                    # Save document
                    file_path = save_document(doc)
                    st.success(f"Document processed and saved to {file_path}")
                except Exception as e:
                    st.error(f"Error processing document: {str(e)}")
    
    with col2:
        # Results display
        st.header("Results")
        if st.session_state.current_document:
            doc = st.session_state.current_document
            st.markdown(f"### {doc.title}")
            
            # Display processes
            for process in doc.processes:
                display_process(process)
            
            # Export options
            st.download_button(
                "Download JSON",
                data=json.dumps(doc.model_dump(), indent=2),
                file_name=f"{doc.id}.json",
                mime="application/json"
            )

if __name__ == "__main__":
    main()
