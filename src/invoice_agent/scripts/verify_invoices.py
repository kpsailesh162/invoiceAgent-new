import os
import psycopg2
from psycopg2.extras import RealDictCursor
from dotenv import load_dotenv
from pathlib import Path

def verify_invoice_files():
    """Verify relationship between database records and generated invoice files"""
    load_dotenv()
    
    # Get database configuration
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
        cur = conn.cursor(cursor_factory=RealDictCursor)
        
        # Get all completed POs with vendor info
        cur.execute("""
            SELECT 
                po.po_number,
                po.order_date,
                po.subtotal,
                po.tax_amount,
                po.total_amount,
                v.name as vendor_name
            FROM purchase_orders po
            JOIN vendors v ON po.vendor_id = v.id
            WHERE po.status = 'completed'
            ORDER BY po.po_number
        """)
        completed_pos = cur.fetchall()
        
        print("\nVerifying Invoice Files...")
        print("=" * 50)
        
        # Base path for generated files
        base_path = Path("src/invoice_agent/data/generated_invoices")
        
        # Check each completed PO
        for po in completed_pos:
            po_number = po['po_number']
            invoice_number = f"INV{po_number[2:]}"
            
            print(f"\nChecking PO: {po_number}")
            print(f"Expected Invoice: {invoice_number}")
            print("-" * 30)
            
            # Check PDF file
            pdf_path = base_path / "pdf" / f"{invoice_number}.pdf"
            print(f"PDF File: {'✅ Found' if pdf_path.exists() else '❌ Missing'}")
            
            # Check CSV file
            csv_path = base_path / "csv" / f"{invoice_number}.csv"
            print(f"CSV File: {'✅ Found' if csv_path.exists() else '❌ Missing'}")
            
            # Check XLSX file
            xlsx_path = base_path / "xlsx" / f"{invoice_number}.xlsx"
            print(f"XLSX File: {'✅ Found' if xlsx_path.exists() else '❌ Missing'}")
            
            # Print PO details
            print("\nPO Details:")
            print(f"Date: {po['order_date']}")
            print(f"Vendor: {po['vendor_name']}")
            print(f"Subtotal: ${po['subtotal']:.2f}")
            print(f"Tax: ${po['tax_amount']:.2f}")
            print(f"Total: ${po['total_amount']:.2f}")
        
        print("\nSummary:")
        print("=" * 50)
        print(f"Total Completed POs: {len(completed_pos)}")
        
        # Count existing files
        pdf_count = len(list(base_path.glob("pdf/*.pdf")))
        csv_count = len(list(base_path.glob("csv/*.csv")))
        xlsx_count = len(list(base_path.glob("xlsx/*.xlsx")))
        
        print(f"PDF Files: {pdf_count}")
        print(f"CSV Files: {csv_count}")
        print(f"XLSX Files: {xlsx_count}")
        
        # Verify counts match
        if pdf_count == csv_count == xlsx_count == len(completed_pos):
            print("\n✅ All invoice files are present and match database records")
        else:
            print("\n❌ Mismatch between database records and generated files")
            print("Please regenerate invoice files")
        
    except Exception as e:
        print(f"\n❌ Error verifying invoice files: {str(e)}")
    finally:
        if 'cur' in locals():
            cur.close()
        if 'conn' in locals():
            conn.close()

if __name__ == "__main__":
    verify_invoice_files() 