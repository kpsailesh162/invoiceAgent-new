import os
import shutil
from pathlib import Path
import psycopg2
from dotenv import load_dotenv

def cleanup_generated_files():
    """Clean up generated invoice files"""
    base_path = Path("src/invoice_agent/data/generated_invoices")
    
    # Create directories if they don't exist (for future use)
    for folder in ["pdf", "csv", "xlsx"]:
        (base_path / folder).mkdir(parents=True, exist_ok=True)
    
    try:
        # Remove all files from each directory
        for folder in ["pdf", "csv", "xlsx"]:
            folder_path = base_path / folder
            if folder_path.exists():
                for file in folder_path.glob("*"):
                    if file.is_file():
                        file.unlink()
                print(f"Cleaned up {folder} directory")
    except Exception as e:
        print(f"Error cleaning up files: {str(e)}")

def cleanup_database():
    """Clean up database tables"""
    load_dotenv()
    
    # Get database configuration from environment variables
    db_config = {
        'dbname': os.getenv('POSTGRES_DB', 'invoice_agent'),
        'user': os.getenv('POSTGRES_USER', 'postgres'),
        'password': os.getenv('POSTGRES_PASSWORD', 'postgres'),
        'host': os.getenv('POSTGRES_HOST', 'localhost'),
        'port': os.getenv('POSTGRES_PORT', '5432')
    }
    
    try:
        # Connect to database
        conn = psycopg2.connect(**db_config)
        cur = conn.cursor()
        
        # List of tables to clean up
        tables = ['goods_receipts', 'purchase_orders', 'vendors']
        
        # Drop and recreate each table
        for table in tables:
            try:
                # Create table if it doesn't exist before dropping
                if table == 'vendors':
                    cur.execute(f"""
                        CREATE TABLE IF NOT EXISTS {table} (
                            id VARCHAR(10) PRIMARY KEY,
                            name VARCHAR(255) NOT NULL,
                            tax_id VARCHAR(20),
                            payment_terms VARCHAR(50),
                            currency VARCHAR(3),
                            status VARCHAR(20),
                            contact_email VARCHAR(255),
                            contact_phone VARCHAR(20),
                            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                        )
                    """)
                elif table == 'purchase_orders':
                    cur.execute(f"""
                        CREATE TABLE IF NOT EXISTS {table} (
                            po_number VARCHAR(20) PRIMARY KEY,
                            vendor_id VARCHAR(10) REFERENCES vendors(id),
                            order_date DATE,
                            subtotal DECIMAL(15, 2),
                            tax_amount DECIMAL(15, 2),
                            total_amount DECIMAL(15, 2),
                            currency VARCHAR(3),
                            status VARCHAR(20),
                            payment_terms VARCHAR(50),
                            items JSONB,
                            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                        )
                    """)
                elif table == 'goods_receipts':
                    cur.execute(f"""
                        CREATE TABLE IF NOT EXISTS {table} (
                            gr_number VARCHAR(20) PRIMARY KEY,
                            po_number VARCHAR(20) REFERENCES purchase_orders(po_number),
                            vendor_id VARCHAR(10) REFERENCES vendors(id),
                            receipt_date DATE,
                            items JSONB,
                            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                        )
                    """)
                
                # Truncate the table
                cur.execute(f"TRUNCATE TABLE {table} CASCADE")
                print(f"Cleaned up table: {table}")
                
            except Exception as e:
                print(f"Error cleaning up table {table}: {str(e)}")
                conn.rollback()
                continue
        
        conn.commit()
        print("Database cleanup completed successfully")
        
    except Exception as e:
        print(f"Database connection error: {str(e)}")
    finally:
        if 'cur' in locals():
            cur.close()
        if 'conn' in locals():
            conn.close()

def main():
    print("Starting cleanup process...")
    
    # Clean up generated files
    cleanup_generated_files()
    
    # Clean up database
    cleanup_database()
    
    print("Cleanup process completed")

if __name__ == "__main__":
    main() 