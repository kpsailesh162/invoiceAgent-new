import os
import psycopg2
from psycopg2.extras import RealDictCursor
from dotenv import load_dotenv

def check_tables():
    """Check if ERP tables exist and display their structure"""
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
        cur = conn.cursor(cursor_factory=RealDictCursor)
        
        # List of ERP tables to check
        erp_tables = ['vendors', 'purchase_orders', 'goods_receipts']
        
        print("\nChecking ERP tables...\n")
        print("=" * 50)
        
        # Check each table
        for table in erp_tables:
            # Check if table exists
            cur.execute("""
                SELECT EXISTS (
                    SELECT FROM information_schema.tables 
                    WHERE table_schema = 'public' 
                    AND table_name = %s
                );
            """, (table,))
            
            exists = cur.fetchone()['exists']
            
            if exists:
                print(f"\n✅ Table '{table}' exists")
                
                # Get column information
                cur.execute("""
                    SELECT column_name, data_type, character_maximum_length, 
                           is_nullable, column_default
                    FROM information_schema.columns
                    WHERE table_schema = 'public' 
                    AND table_name = %s
                    ORDER BY ordinal_position;
                """, (table,))
                
                columns = cur.fetchall()
                
                print("\nColumns:")
                print("-" * 40)
                for col in columns:
                    nullable = "NULL" if col['is_nullable'] == "YES" else "NOT NULL"
                    data_type = col['data_type']
                    if col['character_maximum_length']:
                        data_type += f"({col['character_maximum_length']})"
                    
                    print(f"{col['column_name']}: {data_type} {nullable}")
                    if col['column_default']:
                        print(f"  Default: {col['column_default']}")
                
                # Get number of records
                cur.execute(f"SELECT COUNT(*) as count FROM {table}")
                count = cur.fetchone()['count']
                print(f"\nNumber of records: {count}")
                
                # Get primary key
                cur.execute("""
                    SELECT c.column_name
                    FROM information_schema.table_constraints tc
                    JOIN information_schema.constraint_column_usage AS ccu USING (constraint_schema, constraint_name)
                    JOIN information_schema.columns AS c ON c.table_schema = tc.constraint_schema
                        AND tc.table_name = c.table_name AND ccu.column_name = c.column_name
                    WHERE constraint_type = 'PRIMARY KEY' AND tc.table_name = %s;
                """, (table,))
                
                pk = cur.fetchone()
                if pk:
                    print(f"Primary Key: {pk['column_name']}")
                
                print("=" * 50)
            else:
                print(f"\n❌ Table '{table}' does not exist!")
                print("=" * 50)
        
        # Check foreign key relationships
        print("\nChecking Foreign Key Relationships:")
        print("-" * 50)
        
        cur.execute("""
            SELECT
                tc.table_name as table_name,
                kcu.column_name as column_name,
                ccu.table_name AS foreign_table_name,
                ccu.column_name AS foreign_column_name
            FROM information_schema.table_constraints AS tc
            JOIN information_schema.key_column_usage AS kcu
                ON tc.constraint_name = kcu.constraint_name
                AND tc.table_schema = kcu.table_schema
            JOIN information_schema.constraint_column_usage AS ccu
                ON ccu.constraint_name = tc.constraint_name
                AND ccu.table_schema = tc.table_schema
            WHERE tc.constraint_type = 'FOREIGN KEY'
            AND tc.table_name IN %s;
        """, (tuple(erp_tables),))
        
        fks = cur.fetchall()
        if fks:
            for fk in fks:
                print(f"\n{fk['table_name']}.{fk['column_name']} -> "
                      f"{fk['foreign_table_name']}.{fk['foreign_column_name']}")
        else:
            print("\nNo foreign key relationships found!")
        
    except Exception as e:
        print(f"\n❌ Error checking tables: {str(e)}")
    finally:
        if 'cur' in locals():
            cur.close()
        if 'conn' in locals():
            conn.close()

if __name__ == "__main__":
    check_tables() 