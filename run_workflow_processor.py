import os
import sys
import asyncio

# Add src directory to Python path
src_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "src")
sys.path.insert(0, src_dir)

# Import and run the workflow processor
from invoice_agent.workflow.processor import main

if __name__ == "__main__":
    asyncio.run(main()) 