#!/bin/bash

# PostgreSQL Matrix Encryption Persistence Test Runner
# This script sets up and runs comprehensive tests for PostgreSQL persistence

set -e

echo "🧪 PostgreSQL Matrix Encryption Persistence Test Runner"
echo "======================================================="

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Function to print colored output
print_status() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

print_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Default values
DOCKER_MODE=false
CLEANUP=true
VERBOSE=false

# Parse command line arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --docker)
            DOCKER_MODE=true
            shift
            ;;
        --no-cleanup)
            CLEANUP=false
            shift
            ;;
        --verbose)
            VERBOSE=true
            shift
            ;;
        --help)
            echo "Usage: $0 [OPTIONS]"
            echo ""
            echo "Options:"
            echo "  --docker      Use Docker for PostgreSQL (recommended)"
            echo "  --no-cleanup  Don't cleanup containers after tests"
            echo "  --verbose     Enable verbose output"
            echo "  --help        Show this help message"
            echo ""
            echo "Examples:"
            echo "  $0                    # Run with local PostgreSQL"
            echo "  $0 --docker          # Run with Docker PostgreSQL"
            echo "  $0 --docker --verbose # Run with Docker and verbose output"
            exit 0
            ;;
        *)
            print_error "Unknown option: $1"
            echo "Use --help for usage information"
            exit 1
            ;;
    esac
done

# Check if running in project directory
if [[ ! -f "src/test_postgres_persistence.py" ]]; then
    print_error "Please run this script from the project root directory"
    exit 1
fi

# Function to test PostgreSQL connection
test_postgres_connection() {
    local host=${1:-localhost}
    local port=${2:-5432}
    local user=${3:-matrix_user}
    local db=${4:-matrix_store_test}

    print_status "Testing PostgreSQL connection to $host:$port..."

    if command -v psql >/dev/null 2>&1; then
        if PGPASSWORD="${POSTGRES_PASSWORD:-test_password_2024}" psql -h "$host" -p "$port" -U "$user" -d "$db" -c '\q' 2>/dev/null; then
            print_success "PostgreSQL connection successful"
            return 0
        else
            print_warning "PostgreSQL connection failed"
            return 1
        fi
    else
        print_warning "psql not available, skipping connection test"
        return 0
    fi
}

# Function to run tests with Docker
run_docker_tests() {
    print_status "Running tests with Docker..."

    # Check if Docker is available
    if ! command -v docker >/dev/null 2>&1; then
        print_error "Docker is not installed or not available"
        exit 1
    fi

    if ! command -v docker-compose >/dev/null 2>&1; then
        print_error "Docker Compose is not installed or not available"
        exit 1
    fi

    # Start PostgreSQL container
    print_status "Starting PostgreSQL test container..."
    docker-compose -f docker-compose.test.yml up -d postgres-test

    # Wait for PostgreSQL to be ready
    print_status "Waiting for PostgreSQL to be ready..."
    timeout=60
    count=0
    while ! docker-compose -f docker-compose.test.yml exec -T postgres-test pg_isready -U matrix_user -d matrix_store_test >/dev/null 2>&1; do
        if [[ $count -ge $timeout ]]; then
            print_error "PostgreSQL failed to start within $timeout seconds"
            if [[ "$CLEANUP" == "true" ]]; then
                docker-compose -f docker-compose.test.yml down
            fi
            exit 1
        fi
        sleep 1
        ((count++))
    done

    print_success "PostgreSQL is ready"

    # Set environment variables for tests
    export POSTGRES_HOST=localhost
    export POSTGRES_PORT=5432
    export POSTGRES_USER=matrix_user
    export POSTGRES_PASSWORD=test_password_2024
    export POSTGRES_DB=matrix_store_test
    export USE_POSTGRES_STORE=true

    # Test connection
    if ! test_postgres_connection; then
        print_error "Could not connect to PostgreSQL container"
        if [[ "$CLEANUP" == "true" ]]; then
            docker-compose -f docker-compose.test.yml down
        fi
        exit 1
    fi

    # Run tests
    print_status "Running PostgreSQL persistence tests..."

    if [[ "$VERBOSE" == "true" ]]; then
        python src/test_postgres_persistence.py
    else
        python src/test_postgres_persistence.py 2>&1 | grep -E "(✅|❌|🎉|📊|===)"
    fi

    test_result=$?

    # Cleanup if requested
    if [[ "$CLEANUP" == "true" ]]; then
        print_status "Cleaning up Docker containers..."
        docker-compose -f docker-compose.test.yml down
        print_success "Cleanup completed"
    else
        print_status "Containers left running (use --cleanup to remove)"
        print_status "To manually cleanup: docker-compose -f docker-compose.test.yml down"
    fi

    return $test_result
}

# Function to run tests with local PostgreSQL
run_local_tests() {
    print_status "Running tests with local PostgreSQL..."

    # Check if required environment variables are set
    if [[ -z "${POSTGRES_PASSWORD}" ]]; then
        print_warning "POSTGRES_PASSWORD not set, using default"
        export POSTGRES_PASSWORD="test_password_2024"
    fi

    # Set default environment variables
    export POSTGRES_HOST=${POSTGRES_HOST:-localhost}
    export POSTGRES_PORT=${POSTGRES_PORT:-5432}
    export POSTGRES_USER=${POSTGRES_USER:-matrix_user}
    export POSTGRES_DB=${POSTGRES_DB:-matrix_store_test}
    export USE_POSTGRES_STORE=true

    # Test PostgreSQL connection
    if ! test_postgres_connection; then
        print_error "Cannot connect to PostgreSQL. Please ensure:"
        print_error "  1. PostgreSQL is running"
        print_error "  2. Database 'matrix_store_test' exists"
        print_error "  3. User 'matrix_user' has proper permissions"
        print_error "  4. Environment variables are set correctly"
        print_error ""
        print_error "You can use --docker to run with a containerized PostgreSQL"
        exit 1
    fi

    # Run tests
    print_status "Running PostgreSQL persistence tests..."

    if [[ "$VERBOSE" == "true" ]]; then
        python src/test_postgres_persistence.py
    else
        python src/test_postgres_persistence.py 2>&1 | grep -E "(✅|❌|🎉|📊|===)"
    fi

    return $?
}

# Function to check Python dependencies
check_dependencies() {
    print_status "Checking Python dependencies..."

    required_packages=("psycopg2" "pytest" "matrix-nio" "loguru")
    missing_packages=()

    for package in "${required_packages[@]}"; do
        if ! python -c "import $package" >/dev/null 2>&1; then
            missing_packages+=("$package")
        fi
    done

    if [[ ${#missing_packages[@]} -gt 0 ]]; then
        print_warning "Missing Python packages: ${missing_packages[*]}"
        print_status "Installing missing dependencies..."
        pip install -r requirements.txt
    else
        print_success "All Python dependencies are available"
    fi
}

# Main execution
main() {
    print_status "Starting PostgreSQL Matrix encryption persistence tests"
    print_status "Mode: $(if [[ "$DOCKER_MODE" == "true" ]]; then echo "Docker"; else echo "Local PostgreSQL"; fi)"

    # Check Python dependencies
    check_dependencies

    # Run tests based on mode
    if [[ "$DOCKER_MODE" == "true" ]]; then
        run_docker_tests
    else
        run_local_tests
    fi

    test_result=$?

    echo ""
    echo "======================================================="
    if [[ $test_result -eq 0 ]]; then
        print_success "All tests completed successfully! 🎉"
        print_success "PostgreSQL persistence is working correctly."
    else
        print_error "Some tests failed. Please review the output above."
        print_error "Check the troubleshooting section in README_postgres_tests.md"
    fi
    echo "======================================================="

    exit $test_result
}

# Run main function
main