import shutil
from pathlib import Path
import logging

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

def cleanup_test_data():
    """Clean up all generated test data directories"""
    # Main directories to clean
    directories_to_clean = [
        "src/invoice_agent/data/generated_invoices",
        "src/invoice_agent/erp/mock_data"
    ]
    
    for dir_path in directories_to_clean:
        path = Path(dir_path)
        if path.exists():
            try:
                # First clean format-specific subdirectories if they exist
                for format_dir in ["csv", "pdf", "xlsx"]:
                    format_path = path / format_dir
                    if format_path.exists():
                        shutil.rmtree(format_path)
                        logger.info(f"Successfully deleted subdirectory: {format_path}")
                
                # Then delete the main directory
                shutil.rmtree(path)
                logger.info(f"Successfully deleted directory: {dir_path}")
            except Exception as e:
                logger.error(f"Error deleting directory {dir_path}: {str(e)}")
        else:
            logger.info(f"Directory does not exist, skipping: {dir_path}")
    
    # Clean up log files
    log_files = [
        "data_generation.log",
        "invoice_generation.log"
    ]
    
    for log_file in log_files:
        path = Path(log_file)
        if path.exists():
            try:
                path.unlink()
                logger.info(f"Successfully deleted log file: {log_file}")
            except Exception as e:
                logger.error(f"Error deleting log file {log_file}: {str(e)}")

if __name__ == "__main__":
    cleanup_test_data() 