#!/bin/bash

# Colors for output
GREEN='\033[0;32m'
RED='\033[0;31m'
BLUE='\033[0;34m'
NC='\033[0m'

# Setup test environment
echo -e "${BLUE}Setting up test environment...${NC}"
python tests/setup_test_env.py

# Function to run tests and check result
run_test_suite() {
    local test_name=$1
    local test_path=$2
    local test_marks=$3
    
    echo -e "\n${BLUE}Running ${test_name}...${NC}"
    
    if [ -n "$test_marks" ]; then
        pytest $test_path -v -m "$test_marks" --cov=src/invoice_agent --cov-report=html:tests/coverage/$test_name
    else
        pytest $test_path -v --cov=src/invoice_agent --cov-report=html:tests/coverage/$test_name
    fi
    
    if [ $? -eq 0 ]; then
        echo -e "${GREEN}✓ ${test_name} passed successfully${NC}"
        return 0
    else
        echo -e "${RED}✗ ${test_name} failed${NC}"
        return 1
    fi
}

# 1. Run Unit Tests
echo -e "\n${BLUE}Step 1: Running Unit Tests${NC}"

# 1.1 Workflow Processor Tests
run_test_suite "Workflow Processor Tests" "tests/test_workflow_processor.py"

# 1.2 Notification Manager Tests
run_test_suite "Notification Manager Tests" "tests/test_notification_manager.py"

# 1.3 Metrics Tests
run_test_suite "Metrics Tests" "tests/test_metrics.py"

# 1.4 Audit Logger Tests
run_test_suite "Audit Logger Tests" "tests/test_audit_logger.py"

# 2. Run Integration Tests
echo -e "\n${BLUE}Step 2: Running Integration Tests${NC}"
run_test_suite "Integration Tests" "tests/integration/test_integration.py" "integration"

# 3. Run Performance Tests
echo -e "\n${BLUE}Step 3: Running Performance Tests${NC}"
run_test_suite "Performance Tests" "tests/performance/test_performance.py" "performance"

# 4. Run Load Tests
echo -e "\n${BLUE}Step 4: Running Load Tests${NC}"
run_test_suite "Load Tests" "tests/load/test_load.py" "load"

# Generate combined coverage report
echo -e "\n${BLUE}Generating combined coverage report...${NC}"
coverage combine tests/coverage/*/
coverage html -d tests/coverage/combined

# Open coverage report
python -m webbrowser "tests/coverage/combined/index.html"

echo -e "\n${BLUE}Test execution completed${NC}" 