import os
import sys
import subprocess

def setup_test_environment():
    """Set up the test environment"""
    print("Setting up test environment...")
    
    # Install required dependencies
    requirements = [
        'pytest',
        'pytest-asyncio',
        'pytest-cov',
        'pytest-xdist',
        'psutil',
        'aiohttp',
        'aioredis',
        'slack-sdk',
        'aiosmtplib'
    ]
    
    for req in requirements:
        subprocess.run([sys.executable, '-m', 'pip', 'install', req])
    
    # Create necessary directories
    os.makedirs('tests/reports', exist_ok=True)
    os.makedirs('tests/coverage', exist_ok=True)

if __name__ == '__main__':
    setup_test_environment() 