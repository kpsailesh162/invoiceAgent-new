# Invoice Agent

An intelligent invoice processing system with OCR capabilities and three-way matching.

## Prerequisites

- Python 3.8 or higher
- PostgreSQL database
- Tesseract OCR engine

### Installing Prerequisites

#### macOS
```bash
# Install Homebrew if not already installed
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"

# Install PostgreSQL
brew install postgresql

# Start PostgreSQL service
brew services start postgresql

# Install Tesseract
brew install tesseract
```

#### Linux (Ubuntu/Debian)
```bash
# Install PostgreSQL
sudo apt-get update
sudo apt-get install postgresql postgresql-contrib

# Start PostgreSQL service
sudo systemctl start postgresql
sudo systemctl enable postgresql

# Install Tesseract
sudo apt-get install tesseract-ocr
```

#### Windows
1. Download and install PostgreSQL from the [official website](https://www.postgresql.org/download/windows/)
2. Download and install Tesseract from the [UB Mannheim repository](https://github.com/UB-Mannheim/tesseract/wiki)

## Setup

1. Clone the repository:
```bash
git clone https://github.com/kpsailesh162/invoiceAgent-new.git
cd invoiceAgent-new
```

2. Make the setup script executable and run it:
```bash
chmod +x setup.sh
./setup.sh
```

The setup script will:
- Create a virtual environment
- Install all dependencies
- Set up the database
- Create necessary directories
- Configure environment variables
- Install pre-commit hooks

## Running the Application

1. Activate the virtual environment:
```bash
source venv/bin/activate  # On Unix/macOS
# OR
.\venv\Scripts\activate  # On Windows
```

2. Run the application:
```bash
python run_app.py
```

The application will be available at `http://localhost:8502`

## Project Structure

```
invoiceAgent/
├── src/
│   └── invoice_agent/
│       ├── core/           # Core processing logic
│       ├── security/       # Authentication and authorization
│       ├── template/       # Template management
│       ├── workflow/       # Workflow processing
│       ├── monitoring/     # Metrics and monitoring
│       └── ui/            # Streamlit UI components
├── config/                # Configuration files
├── data/                  # Data storage
├── logs/                  # Log files
├── templates/             # Invoice templates
├── uploads/               # Uploaded files
├── workflows/             # Workflow data
├── setup.sh              # Setup script
├── requirements.txt      # Python dependencies
└── README.md            # This file
```

## Configuration

The application can be configured through the `.env` file created during setup. Key configuration options include:

- Database settings
- Application port
- Logging level
- Secret keys

## Contributing

1. Fork the repository
2. Create a feature branch
3. Commit your changes
4. Push to the branch
5. Create a Pull Request

## License

This project is licensed under the MIT License - see the LICENSE file for details. 