from invoice_agent.security.auth import auth_manager
import logging

logging.basicConfig(level=logging.INFO)

def test_registration():
    try:
        # Register new user
        result = auth_manager.register_user('saileshkp', 'kpsailesh05@gmail.com', 'testpassword')
        print(f'Registration result: {result}')
        
        # Try authenticating
        auth_result = auth_manager.authenticate_user('saileshkp', 'testpassword')
        print(f'Authentication result: {auth_result}')
        
    except Exception as e:
        print(f'Error: {str(e)}')

if __name__ == "__main__":
    test_registration() 