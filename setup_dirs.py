import os

dirs = [
    'processflowai',
    'processflowai/agents',
    'processflowai/utils',
    'processflowai/models'
]

for dir in dirs:
    os.makedirs(dir, exist_ok=True)
