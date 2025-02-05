from invoice_agent.security.auth import auth_manager

def test_registration():
    try:
        result = auth_manager.register_user('saileshkp', 'kpsailesh05@gmail.com', 'testpassword')
        print(f'Registration result: {result}')
    except Exception as e:
        print(f'Error: {str(e)}')

if __name__ == "__main__":
    test_registration() 