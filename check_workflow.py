from src.invoice_agent.database.db_manager import DatabaseManager

def check_workflow(workflow_id):
    db = DatabaseManager()
    try:
        invoice_data = db.get_invoice_by_workflow_id(workflow_id)
        if not invoice_data:
            print(f"No workflow found with ID: {workflow_id}")
            return
            
        print("\nWorkflow Details:")
        print("-" * 50)
        
        # Print invoice details
        invoice = invoice_data['invoice']
        print(f"Invoice Number: {invoice.get('invoice_number')}")
        print(f"Vendor: {invoice.get('vendor_name')}")
        print(f"Status: {invoice.get('status')}")
        print(f"Created At: {invoice.get('created_at')}")
        print(f"Updated At: {invoice.get('updated_at')}")
        
        # Print workflow status history
        print("\nWorkflow Status History:")
        print("-" * 50)
        for status in invoice_data['workflow_status']:
            print(f"Status: {status['status']}")
            print(f"Time: {status['created_at']}")
            if status['message']:
                print(f"Message: {status['message']}")
            print("-" * 30)
        
        # Print matching results if available
        if invoice_data['matching_result']:
            print("\nMatching Results:")
            print("-" * 50)
            match = invoice_data['matching_result']
            print(f"PO Match: {'✅' if match['po_match_status'] else '❌'}")
            print(f"GR Match: {'✅' if match['gr_match_status'] else '❌'}")
            if match['discrepancies']:
                print("\nDiscrepancies:")
                for disc in match['discrepancies']:
                    print(f"- {disc}")
        
        # Print extracted data
        print("\nExtracted Data:")
        print("-" * 50)
        for data in invoice_data['extracted_data']:
            print(f"{data['field_name']}: {data['field_value']} (confidence: {data['confidence_score']})")
            
    finally:
        db.close()

if __name__ == "__main__":
    workflow_id = "443a82c5-4bb5-47cf-9bf6-c02bfe4d5ec4"
    check_workflow(workflow_id) 