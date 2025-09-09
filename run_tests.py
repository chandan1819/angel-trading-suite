#!/usr/bin/env python3
"""
Test runner script for the Bank Nifty Options Trading System.

This script provides a convenient way to run different categories of tests
with appropriate configuration and reporting.
"""

import os
import sys
import subprocess
import argparse
from pathlib import Path


def run_command(cmd, description=""):
    """Run a command and handle errors"""
    print(f"\n{'='*60}")
    if description:
        print(f"Running: {description}")
    print(f"Command: {' '.join(cmd)}")
    print(f"{'='*60}")
    
    try:
        result = subprocess.run(cmd, check=True, capture_output=True, text=True)
        print(result.stdout)
        if result.stderr:
            print("STDERR:", result.stderr)
        return True
    except subprocess.CalledProcessError as e:
        print(f"ERROR: Command failed with exit code {e.returncode}")
        print("STDOUT:", e.stdout)
        print("STDERR:", e.stderr)
        return False


def install_dependencies():
    """Install test dependencies"""
    print("Installing test dependencies...")
    
    dependencies = [
        "pytest>=7.0.0",
        "pytest-cov>=4.0.0",
        "pytest-mock>=3.10.0",
        "pytest-xdist>=3.0.0",  # For parallel test execution
        "pytest-html>=3.1.0",   # For HTML reports
        "pytest-benchmark>=4.0.0"  # For performance testing
    ]
    
    for dep in dependencies:
        cmd = [sys.executable, "-m", "pip", "install", dep]
        if not run_command(cmd, f"Installing {dep}"):
            print(f"Failed to install {dep}")
            return False
    
    return True


def run_unit_tests(coverage=False, verbose=False):
    """Run unit tests"""
    cmd = [sys.executable, "-m", "pytest"]
    
    # Test files for unit tests
    unit_test_files = [
        "tests/test_atm_strike_comprehensive.py",
        "tests/test_position_sizing_pnl.py", 
        "tests/test_risk_management_validation.py",
        "tests/test_data_manager.py",
        "tests/test_risk_manager.py",
        "tests/test_strategies.py",
        "tests/test_angel_api_client.py",
        "tests/test_config_manager.py"
    ]
    
    # Add existing test files
    for test_file in unit_test_files:
        if os.path.exists(test_file):
            cmd.append(test_file)
    
    # Add options
    if verbose:
        cmd.extend(["-v", "-s"])
    
    if coverage:
        cmd.extend([
            "--cov=src",
            "--cov-report=html:htmlcov",
            "--cov-report=term-missing",
            "--cov-fail-under=80"
        ])
    
    cmd.extend([
        "-m", "unit",  # Only run unit tests
        "--tb=short"
    ])
    
    return run_command(cmd, "Unit Tests")


def run_integration_tests(verbose=False):
    """Run integration tests"""
    cmd = [sys.executable, "-m", "pytest"]
    
    # Integration test files
    integration_test_files = [
        "tests/test_integration_paper_trading.py",
        "tests/test_integration_strategy_evaluation.py",
        "tests/test_integration_error_recovery.py",
        "tests/test_order_integration.py",
        "tests/test_emergency_integration.py"
    ]
    
    # Add existing test files
    for test_file in integration_test_files:
        if os.path.exists(test_file):
            cmd.append(test_file)
    
    # Add options
    if verbose:
        cmd.extend(["-v", "-s"])
    
    cmd.extend([
        "-m", "integration",  # Only run integration tests
        "--tb=short"
    ])
    
    return run_command(cmd, "Integration Tests")


def run_performance_tests(verbose=False):
    """Run performance tests"""
    cmd = [sys.executable, "-m", "pytest"]
    
    # Performance test patterns
    cmd.extend([
        "tests/",
        "-k", "performance or timing or speed",
        "--benchmark-only",
        "--benchmark-sort=mean"
    ])
    
    if verbose:
        cmd.extend(["-v", "-s"])
    
    return run_command(cmd, "Performance Tests")


def run_all_tests(coverage=False, verbose=False, parallel=False):
    """Run all tests"""
    cmd = [sys.executable, "-m", "pytest", "tests/"]
    
    if verbose:
        cmd.extend(["-v", "-s"])
    
    if coverage:
        cmd.extend([
            "--cov=src",
            "--cov-report=html:htmlcov",
            "--cov-report=term-missing",
            "--cov-report=xml:coverage.xml",
            "--cov-fail-under=80"
        ])
    
    if parallel:
        cmd.extend(["-n", "auto"])  # Use all available CPUs
    
    cmd.extend([
        "--tb=short",
        "--html=test_report.html",
        "--self-contained-html"
    ])
    
    return run_command(cmd, "All Tests")


def run_specific_tests(test_pattern, verbose=False):
    """Run tests matching a specific pattern"""
    cmd = [sys.executable, "-m", "pytest", "tests/", "-k", test_pattern]
    
    if verbose:
        cmd.extend(["-v", "-s"])
    
    cmd.extend(["--tb=short"])
    
    return run_command(cmd, f"Tests matching: {test_pattern}")


def check_test_coverage():
    """Check test coverage and generate report"""
    if not os.path.exists("htmlcov/index.html"):
        print("No coverage report found. Run tests with --coverage first.")
        return False
    
    print("\nCoverage report generated at: htmlcov/index.html")
    
    # Try to open coverage report in browser
    try:
        import webbrowser
        webbrowser.open(f"file://{os.path.abspath('htmlcov/index.html')}")
        print("Coverage report opened in browser.")
    except:
        print("Could not open browser. Please open htmlcov/index.html manually.")
    
    return True


def lint_code():
    """Run code linting"""
    print("Running code linting...")
    
    # Check if flake8 is available
    try:
        cmd = [sys.executable, "-m", "flake8", "src/", "tests/", "--max-line-length=100"]
        return run_command(cmd, "Code Linting (flake8)")
    except FileNotFoundError:
        print("flake8 not found. Install with: pip install flake8")
        return False


def main():
    """Main test runner function"""
    parser = argparse.ArgumentParser(description="Bank Nifty Options Trading System Test Runner")
    
    parser.add_argument("--install-deps", action="store_true", 
                       help="Install test dependencies")
    parser.add_argument("--unit", action="store_true", 
                       help="Run unit tests only")
    parser.add_argument("--integration", action="store_true", 
                       help="Run integration tests only")
    parser.add_argument("--performance", action="store_true", 
                       help="Run performance tests only")
    parser.add_argument("--all", action="store_true", 
                       help="Run all tests")
    parser.add_argument("--coverage", action="store_true", 
                       help="Generate coverage report")
    parser.add_argument("--verbose", "-v", action="store_true", 
                       help="Verbose output")
    parser.add_argument("--parallel", "-p", action="store_true", 
                       help="Run tests in parallel")
    parser.add_argument("--pattern", "-k", type=str, 
                       help="Run tests matching pattern")
    parser.add_argument("--lint", action="store_true", 
                       help="Run code linting")
    parser.add_argument("--check-coverage", action="store_true", 
                       help="Open coverage report")
    
    args = parser.parse_args()
    
    # Change to project root directory
    project_root = Path(__file__).parent
    os.chdir(project_root)
    
    success = True
    
    if args.install_deps:
        success &= install_dependencies()
    
    if args.lint:
        success &= lint_code()
    
    if args.unit:
        success &= run_unit_tests(coverage=args.coverage, verbose=args.verbose)
    elif args.integration:
        success &= run_integration_tests(verbose=args.verbose)
    elif args.performance:
        success &= run_performance_tests(verbose=args.verbose)
    elif args.all:
        success &= run_all_tests(coverage=args.coverage, verbose=args.verbose, parallel=args.parallel)
    elif args.pattern:
        success &= run_specific_tests(args.pattern, verbose=args.verbose)
    elif not any([args.install_deps, args.lint, args.check_coverage]):
        # Default: run all tests
        success &= run_all_tests(coverage=args.coverage, verbose=args.verbose, parallel=args.parallel)
    
    if args.check_coverage:
        check_test_coverage()
    
    if success:
        print("\n" + "="*60)
        print("✅ All tests completed successfully!")
        print("="*60)
        
        if args.coverage:
            print("\n📊 Coverage report: htmlcov/index.html")
        
        print("\n📋 Test report: test_report.html")
        
    else:
        print("\n" + "="*60)
        print("❌ Some tests failed!")
        print("="*60)
        sys.exit(1)


if __name__ == "__main__":
    main()