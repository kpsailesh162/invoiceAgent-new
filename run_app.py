import os
import sys
from pathlib import Path

# Add the src directory to Python path
src_path = Path(__file__).resolve().parent / 'src'
sys.path.insert(0, str(src_path))

# Set Streamlit port
os.environ['STREAMLIT_SERVER_PORT'] = '8502'

# Import and run the Streamlit app
from invoice_agent.ui.app import main

if __name__ == "__main__":
    main() 