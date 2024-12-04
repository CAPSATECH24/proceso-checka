from setuptools import setup, find_packages

setup(
    name="processflowai",
    version="0.1.0",
    packages=find_packages(),
    install_requires=[
        "streamlit>=1.31.0",
        "google-generativeai>=0.3.0",
        "pydantic>=2.0.0",
    ],
)
