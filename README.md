# ProcessFlowAI

ProcessFlowAI is a mobile application that helps users break down text documents into structured processes and sub-processes using AI.

## Features

- Upload text documents describing processes or projects
- Automatic process decomposition using GPT-4
- Detailed process elaboration using Gemini
- Interactive UI for viewing and managing processes
- Export results in JSON format
- Rate-limited API calls for optimal performance

## Installation

1. Clone the repository:
```bash
git clone <repository-url>
cd processflowai
```

2. Install dependencies:
```bash
pip install -r requirements.txt
```

## Running the Application

To start the Streamlit interface:

```bash
streamlit run processflowai/streamlit_app.py
```

The application will be available at `http://localhost:8501` by default.

## Configuration

You can configure the following settings in the application:
- Decomposition Model (GPT-4 or GPT-3.5-turbo)
- API call rate limits
- Input method (text or file upload)

## Usage

1. Choose your input method (text input or file upload)
2. Enter or upload your process description
3. Click "Process Document" to start the analysis
4. View the structured breakdown of processes and sub-processes
5. Download results in JSON format if needed

## Output Format

The application generates a structured JSON output containing:
- Document metadata
- Extracted processes
- Sub-processes with dependencies
- Process categories and priorities
- Estimated durations

## License

[Your License]
