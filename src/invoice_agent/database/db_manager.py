from datetime import datetime
import json
import uuid
from .db_config import get_db_connection


class DatabaseManager:
    def __init__(self):
        self.conn = None

    def _get_connection(self):
        """Get database connection"""
        if not self.conn:
            self.conn = get_db_connection()
        return self.conn

    def save_invoice(self, invoice_data, file_path):
        """Save invoice data to database"""
        conn = self._get_connection()
        cur = conn.cursor()

        try:
            # Generate workflow ID
            workflow_id = str(uuid.uuid4())

            # Insert into invoices table
            cur.execute(
                """
                INSERT INTO invoices (
                    workflow_id, invoice_number, vendor_name, invoice_date, due_date,
                    total_amount, tax_amount, currency, status, po_number, file_path
                ) VALUES (
                    %(workflow_id)s, %(invoice_number)s, %(vendor_name)s, %(invoice_date)s, %(due_date)s,
                    %(total_amount)s, %(tax_amount)s, %(currency)s, %(status)s,
                    %(po_number)s, %(file_path)s
                ) RETURNING id, workflow_id
            """,
                {
                    "workflow_id": workflow_id,
                    "invoice_number": invoice_data.get("invoice_number"),
                    "vendor_name": invoice_data.get("vendor_name"),
                    "invoice_date": invoice_data.get("invoice_date"),
                    "due_date": invoice_data.get("due_date"),
                    "total_amount": invoice_data.get("total_amount"),
                    "tax_amount": invoice_data.get("tax_amount"),
                    "currency": invoice_data.get("currency"),
                    "status": "pending",
                    "po_number": invoice_data.get("po_number"),
                    "file_path": file_path,
                },
            )

            result = cur.fetchone()
            invoice_id = result["id"]
            workflow_id = result["workflow_id"]

            # Save extracted data
            for field, value in invoice_data.items():
                if field not in ["id", "created_at", "updated_at"]:
                    cur.execute(
                        """
                        INSERT INTO extracted_data (
                            invoice_id, field_name, field_value, confidence_score
                        ) VALUES (%s, %s, %s, %s)
                    """,
                        (
                            invoice_id,
                            field,
                            str(value),
                            invoice_data.get(f"{field}_confidence", 1.0),
                        ),
                    )

            conn.commit()
            return invoice_id, workflow_id

        except Exception as e:
            conn.rollback()
            raise Exception(f"Error saving invoice: {str(e)}")

    def update_workflow_status(self, invoice_id, status, message=None):
        """Update workflow status"""
        conn = self._get_connection()
        cur = conn.cursor()

        try:
            # Update invoice status
            cur.execute(
                """
                UPDATE invoices
                SET status = %s, updated_at = CURRENT_TIMESTAMP
                WHERE id = %s
            """,
                (status, invoice_id),
            )

            # Insert workflow status
            cur.execute(
                """
                INSERT INTO workflow_status (invoice_id, status, message)
                VALUES (%s, %s, %s)
            """,
                (invoice_id, status, message),
            )

            conn.commit()

        except Exception as e:
            conn.rollback()
            raise Exception(f"Error updating workflow status: {str(e)}")

    def save_matching_results(self, invoice_id, matching_results):
        """Save matching results"""
        conn = self._get_connection()
        cur = conn.cursor()

        try:
            # Ensure discrepancies is a list before converting to JSON
            discrepancies = matching_results.get("discrepancies", [])
            if not isinstance(discrepancies, list):
                discrepancies = [str(discrepancies)]

            cur.execute(
                """
                INSERT INTO matching_results (
                    invoice_id, po_match_status, gr_match_status, discrepancies
                ) VALUES (%s, %s, %s, %s)
            """,
                (
                    invoice_id,
                    matching_results.get("po_match_status", False),
                    matching_results.get("gr_match_status", False),
                    json.dumps(discrepancies),
                ),
            )

            # Update invoice status based on matching results
            status = (
                "matched" if matching_results.get("match_successful") else "discrepancy"
            )
            cur.execute(
                """
                UPDATE invoices
                SET status = %s, updated_at = CURRENT_TIMESTAMP
                WHERE id = %s
            """,
                (status, invoice_id),
            )

            conn.commit()

        except Exception as e:
            conn.rollback()
            raise Exception(f"Error saving matching results: {str(e)}")

    def get_invoice(self, invoice_id):
        """Get invoice details"""
        conn = self._get_connection()
        cur = conn.cursor()

        try:
            # Get invoice data
            cur.execute(
                """
                SELECT * FROM invoices WHERE id = %s
            """,
                (invoice_id,),
            )
            invoice = cur.fetchone()

            if not invoice:
                return None

            # Get extracted data
            cur.execute(
                """
                SELECT field_name, field_value, confidence_score
                FROM extracted_data
                WHERE invoice_id = %s
            """,
                (invoice_id,),
            )
            extracted_data = cur.fetchall()

            # Get workflow status
            cur.execute(
                """
                SELECT status, message, created_at
                FROM workflow_status
                WHERE invoice_id = %s
                ORDER BY created_at DESC
            """,
                (invoice_id,),
            )
            workflow_status = cur.fetchall()

            # Get matching results
            cur.execute(
                """
                SELECT po_match_status, gr_match_status, discrepancies, match_date
                FROM matching_results
                WHERE invoice_id = %s
                ORDER BY match_date DESC
                LIMIT 1
            """,
                (invoice_id,),
            )
            matching_result = cur.fetchone()

            return {
                "invoice": dict(invoice),
                "extracted_data": [dict(data) for data in extracted_data],
                "workflow_status": [dict(status) for status in workflow_status],
                "matching_result": dict(matching_result) if matching_result else None,
            }

        except Exception as e:
            raise Exception(f"Error retrieving invoice: {str(e)}")

    def get_all_invoices(self, status=None, date_from=None, date_to=None):
        """Get all invoices with optional filters"""
        conn = self._get_connection()
        cur = conn.cursor()

        try:
            query = "SELECT * FROM invoices WHERE 1=1"
            params = []

            if status:
                query += " AND status = %s"
                params.append(status)

            if date_from:
                query += " AND created_at >= %s"
                params.append(date_from)

            if date_to:
                query += " AND created_at <= %s"
                params.append(date_to)

            query += " ORDER BY created_at DESC"

            cur.execute(query, params)
            invoices = cur.fetchall()

            return [dict(invoice) for invoice in invoices]

        except Exception as e:
            raise Exception(f"Error retrieving invoices: {str(e)}")

    def get_invoice_by_workflow_id(self, workflow_id):
        """Get invoice details by workflow ID"""
        conn = self._get_connection()
        cur = conn.cursor()

        try:
            # Get invoice data
            cur.execute(
                """
                SELECT id FROM invoices WHERE workflow_id = %s
            """,
                (workflow_id,),
            )
            result = cur.fetchone()

            if not result:
                return None

            return self.get_invoice(result["id"])

        except Exception as e:
            raise Exception(f"Error retrieving invoice by workflow ID: {str(e)}")

    def close(self):
        """Close database connection"""
        if self.conn:
            self.conn.close()
            self.conn = None

    def check_invoice_number(self, invoice_number: str) -> bool:
        """Check if an invoice number already exists in the database"""
        conn = self._get_connection()
        cur = conn.cursor()

        try:
            cur.execute(
                """
                SELECT EXISTS(
                    SELECT 1 FROM invoices WHERE invoice_number = %s
                )
            """,
                (invoice_number,),
            )

            exists = cur.fetchone()["exists"]
            if exists:
                raise ValueError(f"Invoice number {invoice_number} already exists")
            return True

        except Exception as e:
            if "duplicate key value violates unique constraint" in str(e):
                raise ValueError(f"Invoice number {invoice_number} already exists")
            raise e
