import email
import imaplib
import os
from typing import List, Dict, Any, AsyncGenerator, Optional
from datetime import datetime
import aiofiles
from email.header import decode_header
import tempfile
from pathlib import Path
import re
import logging
from .base import (
    SourceIntegration,
    SourceIntegrationError,
    AuthenticationError
)

class EmailIntegration(SourceIntegration):
    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        self.host = config['host']
        self.username = config['username']
        self.password = config['password']
        self.folder = config.get('folder', 'INBOX')
        self.connection = None
        self.supported_extensions = {'.pdf', '.doc', '.docx', '.tiff', '.png', '.jpg', '.jpeg'}
        self.processed_folder = config.get('processed_folder', 'Processed')
        self.allowed_extensions = config.get(
            'allowed_extensions',
            ['.pdf', '.jpg', '.jpeg', '.png', '.tiff']
        )
        self.sender_whitelist = config.get('sender_whitelist', [])
        self.subject_patterns = config.get('subject_patterns', [r'invoice', r'bill'])
        self.imap_client = None
        
    async def connect(self):
        """Connect to email server"""
        try:
            self.imap_client = imaplib.IMAP4_SSL(self.host)
            self.imap_client.login(self.username, self.password)
            self.imap_client.select(self.folder)
            
            # Create processed folder if it doesn't exist
            folders = self.imap_client.list()[1][0].split()
            if self.processed_folder not in folders:
                self.imap_client.create(self.processed_folder)
                
        except Exception as e:
            raise AuthenticationError(f"Failed to connect to email server: {str(e)}")
    
    async def disconnect(self):
        """Disconnect from email server"""
        if self.imap_client:
            self.imap_client.logout()
            self.imap_client = None
    
    async def fetch_invoices(
        self,
        since: Optional[datetime] = None
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """Fetch invoices from email"""
        try:
            # Select inbox
            self.imap_client.select('INBOX')
            
            # Build search criteria
            search_criteria = ['UNSEEN']
            if since:
                date_str = since.strftime("%d-%b-%Y")
                search_criteria.extend(['SINCE', date_str])
            
            # Search for messages
            _, message_numbers = self.imap_client.search(None, *search_criteria)
            
            for num in message_numbers[0].split():
                # Fetch message
                _, msg_data = self.imap_client.fetch(num, '(RFC822)')
                email_body = msg_data[0][1]
                email_message = email.message_from_bytes(email_body)
                
                # Check sender
                sender = email_message['from']
                if self.sender_whitelist and not any(
                    allowed in sender for allowed in self.sender_whitelist
                ):
                    continue
                
                # Check subject
                subject = email_message['subject']
                if not any(
                    re.search(pattern, subject, re.IGNORECASE)
                    for pattern in self.subject_patterns
                ):
                    continue
                
                # Process attachments
                attachments = await self._process_attachments(email_message)
                if attachments:
                    yield {
                        'email_id': num.decode(),
                        'subject': subject,
                        'sender': sender,
                        'date': email_message['date'],
                        'attachments': attachments
                    }
                    
        except Exception as e:
            raise SourceIntegrationError(f"Failed to fetch emails: {str(e)}")
    
    async def _process_attachments(
        self,
        message: EmailMessage
    ) -> List[Dict[str, Any]]:
        """Process email attachments"""
        attachments = []
        
        for part in message.iter_attachments():
            filename = part.get_filename()
            if not filename:
                continue
                
            # Check file extension
            file_ext = Path(filename).suffix.lower()
            if file_ext not in self.allowed_extensions:
                continue
            
            # Save attachment
            content = part.get_payload(decode=True)
            temp_file = Path(self.config['temp_dir']) / filename
            temp_file.write_bytes(content)
            
            attachments.append({
                'filename': filename,
                'path': str(temp_file),
                'content_type': part.get_content_type()
            })
        
        return attachments
    
    def _decode_header(self, header: str) -> str:
        decoded_parts = decode_header(header)
        return ''.join(
            part.decode(encoding or 'utf-8') if isinstance(part, bytes) else part
            for part, encoding in decoded_parts
        )
    
    async def mark_as_processed(self, email_id: str):
        """Move processed email to processed folder"""
        try:
            self.imap_client.copy(email_id, self.processed_folder)
            self.imap_client.store(email_id, '+FLAGS', '(\Deleted)')
            self.imap_client.expunge()
        except Exception as e:
            raise SourceIntegrationError(
                f"Failed to mark email as processed: {str(e)}"
            ) 