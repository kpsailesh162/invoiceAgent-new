import os
import psycopg2
from dotenv import load_dotenv

def create_erp_tables():
    """Create ERP tables if they don't exist"""
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
        
        # Create vendors table
        cur.execute("""
            CREATE TABLE IF NOT EXISTS vendors (
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
        print("✅ Vendors table created/verified")
        
        # Create purchase_orders table
        cur.execute("""
            CREATE TABLE IF NOT EXISTS purchase_orders (
                po_number VARCHAR(20) PRIMARY KEY,
                vendor_id VARCHAR(10) REFERENCES vendors(id),
                order_date DATE,
                items JSONB,
                subtotal DECIMAL(15, 2),
                tax_amount DECIMAL(15, 2),
                total_amount DECIMAL(15, 2),
                currency VARCHAR(3),
                status VARCHAR(20),
                payment_terms VARCHAR(50),
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        print("✅ Purchase Orders table created/verified")
        
        # Create goods_receipts table
        cur.execute("""
            CREATE TABLE IF NOT EXISTS goods_receipts (
                gr_number VARCHAR(20) PRIMARY KEY,
                po_number VARCHAR(20) REFERENCES purchase_orders(po_number),
                vendor_id VARCHAR(10) REFERENCES vendors(id),
                receipt_date DATE,
                items JSONB,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        print("✅ Goods Receipts table created/verified")
        
        # Create indexes for better performance
        cur.execute("""
            CREATE INDEX IF NOT EXISTS idx_po_vendor_id ON purchase_orders(vendor_id);
            CREATE INDEX IF NOT EXISTS idx_po_status ON purchase_orders(status);
            CREATE INDEX IF NOT EXISTS idx_gr_po_number ON goods_receipts(po_number);
            CREATE INDEX IF NOT EXISTS idx_gr_vendor_id ON goods_receipts(vendor_id);
        """)
        print("✅ Indexes created/verified")
        
        conn.commit()
        print("\n✅ All ERP tables and indexes created successfully!")
        
    except Exception as e:
        conn.rollback()
        print(f"\n❌ Error creating tables: {str(e)}")
    finally:
        if 'cur' in locals():
            cur.close()
        if 'conn' in locals():
            conn.close()

if __name__ == "__main__":
    create_erp_tables() 