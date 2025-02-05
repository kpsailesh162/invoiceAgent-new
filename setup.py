from setuptools import setup, find_packages

setup(
    name="invoice_agent",
    version="0.1.0",
    packages=find_packages(where="src"),
    package_dir={"": "src"},
    install_requires=[
        "streamlit>=1.29.0",
        "python-dotenv>=1.0.0",
        "pyyaml>=6.0.1",
        "cryptography>=41.0.7",
        "prometheus-client>=0.19.0",
        "aiofiles>=23.2.1",
        "aiohttp>=3.9.1",
        "aioredis>=2.0.1",
        "slack-sdk>=3.27.0",
        "aiosmtplib>=3.0.1",
        "redis>=5.0.1",
    ],
    extras_require={
        "test": [
            "pytest>=7.4.3",
            "pytest-cov>=4.1.0",
            "pytest-mock>=3.12.0",
            "pytest-asyncio>=0.21.1",
            "pytest-timeout>=2.2.0",
            "pytest-xdist>=3.3.1",
        ],
    },
    python_requires=">=3.8",
) 