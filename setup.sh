#!/bin/bash

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${GREEN}Starting Invoice Agent Setup...${NC}"

# Check if Python 3.8 or higher is installed
if ! command -v python3 &> /dev/null; then
    echo -e "${RED}Python 3 is not installed. Please install Python 3.8 or higher.${NC}"
    exit 1
fi

# Create virtual environment
echo -e "${YELLOW}Creating virtual environment...${NC}"
python3 -m venv venv

# Activate virtual environment
echo -e "${YELLOW}Activating virtual environment...${NC}"
source venv/bin/activate

# Upgrade pip
echo -e "${YELLOW}Upgrading pip...${NC}"
pip install --upgrade pip

# Install dependencies
echo -e "${YELLOW}Installing dependencies...${NC}"
pip install -r requirements.txt

# Create necessary directories
echo -e "${YELLOW}Creating necessary directories...${NC}"
mkdir -p logs
mkdir -p data
mkdir -p uploads
mkdir -p workflows
mkdir -p config
mkdir -p templates

# Create .env file if it doesn't exist
if [ ! -f .env ]; then
    echo -e "${YELLOW}Creating .env file...${NC}"
    cat > .env << EOL
# Database Configuration
DB_NAME=invoice_agent
DB_USER=sailesh
DB_PASSWORD=
DB_HOST=localhost
DB_PORT=5432

# Application Configuration
APP_SECRET_KEY=$(python3 -c 'import secrets; print(secrets.token_hex(32))')
APP_DEBUG=False
APP_PORT=8502

# Logging Configuration
LOG_LEVEL=ERROR
LOG_FILE=invoice_agent.log
EOL
fi

# Initialize database
echo -e "${YELLOW}Initializing database...${NC}"
python test_db.py

# Install pre-commit hooks
echo -e "${YELLOW}Installing pre-commit hooks...${NC}"
if ! command -v pre-commit &> /dev/null; then
    pip install pre-commit
fi
pre-commit install

echo -e "${GREEN}Setup completed successfully!${NC}"
echo -e "${YELLOW}To start the application, run:${NC}"
echo -e "source venv/bin/activate"
echo -e "python run_app.py" 