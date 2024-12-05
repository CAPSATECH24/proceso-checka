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
    page_icon="",
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
    st.markdown(f"## {process.name}")
    
    if process.phases:
        st.markdown("### Pasos Detallados:")
        
        for phase_index, phase in enumerate(sorted(process.phases, key=lambda x: x.order), 1):
            # Display sub-processes for this phase
            phase_steps = [sub for sub in process.sub_processes if sub.phase_id == phase.id]
            if phase_steps:
                for sub_index, sub in enumerate(sorted(phase_steps, key=lambda x: x.order), 1):
                    # Mostrar título del subproceso con numeración jerárquica
                    st.markdown(f"\n**{phase_index}.{sub_index}. {sub.name}**")
                    
                    if sub.description:
                        # Reiniciar contador para los pasos dentro de cada subproceso
                        step_counter = 1
                        for line in sub.description.split('\n'):
                            line = line.strip()
                            if line:
                                # Eliminar cualquier numeración existente
                                if line[0].isdigit():
                                    parts = line.split('.')
                                    if len(parts) > 1:
                                        line = '.'.join(parts[1:]).strip()
                                    else:
                                        space_index = line.find(' ')
                                        if space_index != -1:
                                            line = line[space_index:].strip()
                                
                                # Agregar nueva numeración para el paso
                                st.markdown(f"{step_counter}. {line}")
                                step_counter += 1

    # Export to Word
    if st.button(" Exportar a Word", key=f"export_word_{process.name}_{id(process)}"):
        try:
            subprocesses_data = []
            for subprocess in process.sub_processes:
                subprocesses_data.append({
                    'name': subprocess.name,
                    'description': subprocess.description,
                    'order': subprocess.order
                })
            
            filepath = generate_process_document(
                process.name,
                process.description,
                subprocesses_data
            )
            
            with open(filepath, 'rb') as f:
                bytes_data = f.read()
            
            st.download_button(
                label=" Descargar Documento Word",
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
    st.title("ProcessFlowAI ")
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
        
        if api_key and st.button("Update Configuration", key="update_config_button"):
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
            ["Text Input", "File Upload"],
            key="input_method_radio"
        )
        
        document_content = None
        document_title = None
        
        if input_method == "Text Input":
            document_title = st.text_input("Document Title (optional)", key="doc_title_input")
            document_content = st.text_area(
                "Enter your process description",
                height=300,
                key="doc_content_textarea"
            )
        else:
            uploaded_file = st.file_uploader("Upload a document", key="doc_file_uploader")
            if uploaded_file:
                document_title = uploaded_file.name
                document_content = uploaded_file.getvalue().decode()
        
        if st.button("Process Document", key="process_doc_button") and document_content:
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
                mime="application/json",
                key="download_json_button"
            )

if __name__ == "__main__":
    main()
