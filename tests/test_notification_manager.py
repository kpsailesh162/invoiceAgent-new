import pytest
from unittest.mock import Mock, patch, AsyncMock, call
from invoice_agent.notifications.manager import NotificationManager
import json
from email.mime.multipart import MIMEMultipart
import asyncio
import time

@pytest.fixture
def test_config():
    return {
        'email': {
            'sender': 'test@example.com',
            'smtp_host': 'smtp.test.com',
            'smtp_port': 587,
            'username': 'test',
            'password': 'test123'
        },
        'slack': {
            'token': 'xoxb-test-token',
            'channel': '#test'
        },
        'notifications': {
            'invoice_exception': {
                'email': True,
                'slack': True
            }
        }
    }

@pytest.fixture
def notification_manager(test_config):
    return NotificationManager(test_config)

@pytest.fixture
def notification_data():
    return {
        'simple': {
            'invoice_number': 'INV-2024-001',
            'vendor_name': 'CompuWorld',
            'amount': '50000.00',
            'currency': 'USD',
            'description': ['Amount mismatch detected']
        },
        'complex': {
            'invoice_number': 'INV-2024-002',
            'vendor_name': 'TechCorp',
            'amount': '75000.00',
            'currency': 'EUR',
            'description': ['Multiple discrepancies found'],
            'details': {
                'line_items': ['Item 1 quantity mismatch', 'Item 3 price mismatch'],
                'tax_issues': ['Invalid VAT rate']
            }
        }
    }

@pytest.mark.asyncio
async def test_email_notification(notification_manager):
    with patch('aiosmtplib.send', new_callable=AsyncMock) as mock_send:
        data = {
            'invoice_number': 'INV-2024-001',
            'vendor_name': 'CompuWorld',
            'amount': '50000.00',
            'currency': 'USD',
            'description': ['Amount mismatch detected']
        }
        
        await notification_manager._send_email(
            'invoice_exception',
            data,
            ['test@example.com']
        )
        
        mock_send.assert_called_once()
        call_args = mock_send.call_args[1]
        assert call_args['hostname'] == 'smtp.test.com'
        assert call_args['port'] == 587

@pytest.mark.asyncio
async def test_email_notification_content(notification_manager, notification_data):
    """Test email content formatting"""
    with patch('aiosmtplib.send', new_callable=AsyncMock) as mock_send:
        await notification_manager._send_email(
            'invoice_exception',
            notification_data['complex'],
            ['test@example.com']
        )
        
        # Verify email content
        call_args = mock_send.call_args[0][0]
        assert isinstance(call_args, MIMEMultipart)
        
        # Check email parts
        email_parts = call_args.get_payload()
        html_content = email_parts[0].get_payload()
        
        # Verify content includes all necessary information
        assert notification_data['complex']['invoice_number'] in html_content
        assert notification_data['complex']['vendor_name'] in html_content
        for item in notification_data['complex']['details']['line_items']:
            assert item in html_content

@pytest.mark.asyncio
async def test_notification_retry_logic(notification_manager, notification_data):
    """Test notification retry mechanism"""
    with patch('aiosmtplib.send', new_callable=AsyncMock) as mock_send:
        # Simulate temporary failure
        mock_send.side_effect = [
            Exception("Temporary failure"),
            Exception("Temporary failure"),
            None  # Success on third try
        ]
        
        await notification_manager._send_email(
            'invoice_exception',
            notification_data['simple'],
            ['test@example.com']
        )
        
        assert mock_send.call_count == 3

@pytest.mark.asyncio
async def test_slack_notification(notification_manager):
    with patch('slack_sdk.WebClient.chat_postMessage', new_callable=AsyncMock) as mock_post:
        data = {
            'invoice_number': 'INV-2024-001',
            'vendor_name': 'CompuWorld',
            'description': ['Amount mismatch detected']
        }
        
        await notification_manager._send_slack('invoice_exception', data)
        
        mock_post.assert_called_once()
        assert mock_post.call_args[1]['channel'] == '#test'

@pytest.mark.asyncio
async def test_slack_message_formatting(notification_manager, notification_data):
    """Test Slack message formatting"""
    with patch('slack_sdk.WebClient.chat_postMessage', new_callable=AsyncMock) as mock_post:
        await notification_manager._send_slack(
            'invoice_exception',
            notification_data['complex']
        )
        
        # Verify Slack message structure
        call_args = mock_post.call_args[1]
        blocks = json.loads(call_args['blocks'])
        
        # Check block structure
        assert blocks[0]['type'] == 'header'
        assert any(
            block['type'] == 'section' and 
            notification_data['complex']['invoice_number'] in str(block)
            for block in blocks
        )

@pytest.mark.asyncio
async def test_notification_priority(notification_manager):
    """Test notification priority handling"""
    with patch.multiple(
        notification_manager,
        _send_email=AsyncMock(),
        _send_slack=AsyncMock()
    ):
        # Test high priority notification
        await notification_manager.send_notification(
            'invoice_exception',
            {'priority': 'high', 'invoice_number': 'INV-2024-001'},
            ['test@example.com']
        )
        
        # Verify both email and Slack were called
        notification_manager._send_email.assert_called_once()
        notification_manager._send_slack.assert_called_once()

@pytest.mark.asyncio
async def test_template_rendering_edge_cases(notification_manager):
    """Test template rendering with edge cases"""
    edge_cases = [
        # Empty description
        {'invoice_number': 'INV-2024-001', 'description': []},
        # Very long description
        {'invoice_number': 'INV-2024-002', 'description': ['x' * 1000]},
        # Special characters
        {'invoice_number': 'INV-2024-003', 'description': ['<script>alert("test")</script>']},
        # Unicode characters
        {'invoice_number': 'INV-2024-004', 'description': ['测试', '🚀']}
    ]
    
    for case in edge_cases:
        with patch('aiosmtplib.send', new_callable=AsyncMock) as mock_send:
            await notification_manager._send_email(
                'invoice_exception',
                case,
                ['test@example.com']
            )
            
            # Verify email was sent successfully
            mock_send.assert_called_once()

@pytest.mark.asyncio
async def test_notification_rate_limiting(notification_manager):
    """Test notification rate limiting"""
    current_time = [time.time()]
    
    def mock_time():
        return current_time[0]
    
    async def mock_sleep(duration):
        current_time[0] += duration
    
    with patch('time.time', side_effect=mock_time):
        with patch('asyncio.sleep', side_effect=mock_sleep):
            with patch('aiosmtplib.send', new_callable=AsyncMock) as mock_send:
                # Send multiple notifications quickly
                tasks = []
                for i in range(10):
                    tasks.append(
                        notification_manager._send_email(
                            'invoice_exception',
                            {'invoice_number': f'INV-2024-{i}'},
                            ['test@example.com']
                        )
                    )
                
                await asyncio.gather(*tasks)
                
                # Verify number of calls
                assert mock_send.call_count == 10
                
                # Verify rate limiting by checking timestamps
                timestamps = [call[1]['timestamp'] for call in mock_send.call_args_list]
                for i in range(1, len(timestamps)):
                    time_diff = timestamps[i] - timestamps[i-1]
                    # Allow for small floating-point differences
                    assert abs(time_diff - notification_manager.rate_limit_interval) < 0.0001 