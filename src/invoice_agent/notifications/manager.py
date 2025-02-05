from typing import Dict, Any, List, Optional
import aiosmtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import slack_sdk
import logging
from jinja2 import Environment, FileSystemLoader
from pathlib import Path
import asyncio
import time
from ..config.settings import config

class NotificationManager:
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.env = Environment(
            loader=FileSystemLoader(config.BASE_DIR / "templates/notifications")
        )
        self.slack_client = self._init_slack() if config.get('slack') else None
        self.rate_limit_interval = 0.1  # 100ms between notifications
        self.max_retries = 3
        self._last_email_time = 0
        self._email_lock = asyncio.Lock()
        
    async def send_notification(
        self,
        notification_type: str,
        data: Dict[str, Any],
        recipients: List[str]
    ):
        """Send notification through configured channels"""
        try:
            # Get notification config
            notification_config = config.notifications[notification_type]
            
            # Send through each configured channel
            tasks = []
            if notification_config.get('email', True):
                tasks.append(self._send_email(notification_type, data, recipients))
            
            if notification_config.get('slack', False):
                tasks.append(self._send_slack(notification_type, data))
            
            await asyncio.gather(*tasks)
            
        except Exception as e:
            self.logger.error(f"Failed to send notification: {str(e)}")
    
    async def _send_email(
        self,
        notification_type: str,
        data: Dict[str, Any],
        recipients: List[str]
    ):
        """Send email notification"""
        async with self._email_lock:
            for attempt in range(self.max_retries):
                try:
                    # Rate limiting
                    now = time.time()
                    if now - self._last_email_time < self.rate_limit_interval:
                        await asyncio.sleep(self.rate_limit_interval - (now - self._last_email_time))
                    
                    # Get template
                    template = self.env.get_template(f"{notification_type}.html")
                    
                    # Render email content
                    html_content = template.render(**data)
                    
                    # Create message
                    message = MIMEMultipart()
                    message["From"] = config.email['sender']
                    message["To"] = ", ".join(recipients)
                    message["Subject"] = self._get_subject(notification_type, data)
                    
                    message.attach(MIMEText(html_content, "html"))
                    
                    # Send email
                    await aiosmtplib.send(
                        message,
                        hostname=config.email['smtp_host'],
                        port=config.email['smtp_port'],
                        username=config.email['username'],
                        password=config.email['password'],
                        use_tls=True,
                        timestamp=time.time()
                    )
                    
                    self._last_email_time = time.time()
                    return
                    
                except Exception as e:
                    self.logger.error(f"Failed to send email: {str(e)}")
                    if attempt < self.max_retries - 1:
                        await asyncio.sleep(1)  # Wait before retrying
                    else:
                        raise
    
    async def _send_slack(
        self,
        notification_type: str,
        data: Dict[str, Any]
    ):
        """Send Slack notification"""
        try:
            if not self.slack_client:
                return
                
            # Get template
            template = self.env.get_template(f"{notification_type}.slack")
            
            # Render message blocks
            blocks = template.render(**data)
            
            # Send message
            await self.slack_client.chat_postMessage(
                channel=config.slack['channel'],
                blocks=blocks
            )
            
        except Exception as e:
            self.logger.error(f"Failed to send Slack notification: {str(e)}")
    
    def _init_slack(self) -> Optional[slack_sdk.WebClient]:
        """Initialize Slack client"""
        try:
            return slack_sdk.WebClient(
                token=config.slack['token']
            )
        except Exception as e:
            self.logger.error(f"Failed to initialize Slack client: {str(e)}")
            return None
    
    def _get_subject(
        self,
        notification_type: str,
        data: Dict[str, Any]
    ) -> str:
        """Get email subject based on notification type"""
        subjects = {
            'invoice_approved': f"Invoice {data['invoice_number']} Approved",
            'invoice_exception': f"Invoice {data['invoice_number']} Exception",
            'payment_scheduled': f"Payment Scheduled for Invoice {data['invoice_number']}",
            'vendor_communication': f"Action Required: Invoice {data['invoice_number']}"
        }
        return subjects.get(notification_type, "Invoice Processing Notification") 