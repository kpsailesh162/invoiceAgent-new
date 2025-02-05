"""Test configuration settings"""

PERFORMANCE_SETTINGS = {
    'max_processing_time': 2.0,  # seconds
    'max_memory_increase': 100 * 1024 * 1024,  # 100MB
    'max_cpu_usage': 80.0,  # percentage
}

LOAD_TEST_SETTINGS = {
    'concurrent_users': 50,
    'min_success_rate': 0.95,
    'max_time_variance': 1.0,
    'max_error_rate': 0.05,
    'sustained_load_duration': 300,  # seconds
}

INTEGRATION_SETTINGS = {
    'redis_url': 'redis://localhost',
    'erp_timeout': 30,  # seconds
    'max_retries': 3,
} 