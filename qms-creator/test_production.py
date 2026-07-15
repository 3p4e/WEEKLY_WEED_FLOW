#!/usr/bin/env python3
"""
Production Test Script for Cannabis EU GMP QMS Creator

This script tests the production instance by:
1. Starting the backend server (if not already running)
2. Testing API endpoints
3. Generating a sample SOP
4. Verifying the output files

Usage:
    python test_production.py [--api-mode] [--direct-mode] [--no-cleanup]

Options:
    --api-mode      Test via API (default, requires backend running)
    --direct-mode   Test workflow directly without API
    --no-cleanup    Keep generated files for inspection
"""

import argparse
import json
import logging
import os
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

import requests

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("ProductionTest")

# Project root
PROJECT_ROOT = Path(__file__).parent.absolute()

# Test configuration
TEST_SOP_NAME = "Equipment Qualification and Validation"
TEST_SOP_TYPE = "Quality Assurance"
TEST_DEPARTMENT = "Quality"
TEST_KEYWORDS = ["equipment", "qualification", "validation", "GMP"]
TEST_API_KEY = "test-api-key-12345"  # Default test key from conftest.py
TEST_API_URL = "http://localhost:8000"

# Sample questionnaire answers
SAMPLE_ANSWERS = {
    "facility_name": "Test Cannabis Facility",
    "facility_location": "Amsterdam, Netherlands",
    "facility_type": "Manufacturing",
    "contact_person": "Test Manager",
    "contact_email": "test@example.com",
    "sop_purpose": "To establish procedures for equipment qualification and validation",
    "scope": "All equipment used in manufacturing process",
    "responsible_person": "Quality Manager",
    "effective_date": "2026-01-26",
    "review_frequency": "Annual",
    "equipment_types": [
        "Manufacturing equipment",
        "Testing equipment",
        "Storage equipment",
    ],
    "qualification_stages": [
        "Design Qualification (DQ)",
        "Installation Qualification (IQ)",
        "Operational Qualification (OQ)",
        "Performance Qualification (PQ)",
    ],
    "documentation_requirements": [
        "Qualification protocols",
        "Test results",
        "Approval signatures",
        "Deviations report",
    ],
    "training_requirements": [
        "All operators",
        "Maintenance personnel",
        "Quality staff",
    ],
}


class ProductionTester:
    """Test the production instance of the Cannabis EU GMP QMS Creator."""

    def __init__(self, api_mode: bool = True, cleanup: bool = True):
        self.api_mode = api_mode
        self.cleanup = cleanup
        self.backend_process = None
        self.test_output_dir = PROJECT_ROOT / "test_production_output"
        self.test_output_dir.mkdir(exist_ok=True)

        # Set environment variables for testing
        os.environ["ENVIRONMENT"] = "testing"
        os.environ["API_KEY"] = TEST_API_KEY
        os.environ["LOG_LEVEL"] = "INFO"

        # Use SQLite for testing to avoid PostgreSQL dependency
        os.environ["DATABASE_URL"] = f"sqlite:///{self.test_output_dir}/test.db"
        os.environ["USE_POSTGRESQL"] = "false"  # Use JSON backend for simplicity

    def setup_environment(self):
        """Set up the testing environment."""
        logger.info("Setting up test environment...")

        # Create necessary directories
        (PROJECT_ROOT / "output").mkdir(exist_ok=True)
        (PROJECT_ROOT / "sops_created").mkdir(exist_ok=True)
        (PROJECT_ROOT / "data").mkdir(exist_ok=True)

        # Copy test data if needed
        test_data_file = PROJECT_ROOT / "data" / "document_status.json"
        if not test_data_file.exists():
            test_data_file.parent.mkdir(exist_ok=True, parents=True)
            test_data_file.write_text(
                json.dumps(
                    {
                        "documents": [],
                        "last_updated": time.strftime("%Y-%m-%dT%H:%M:%S"),
                        "registry_version": "1.0",
                    },
                    indent=2,
                )
            )

        logger.info(f"Test environment ready. Output directory: {self.test_output_dir}")

    def start_backend(self):
        """Start the backend server."""
        if self.is_backend_running():
            logger.info("Backend is already running")
            return True

        logger.info("Starting backend server...")

        try:
            # Start backend using uvicorn for testing
            backend_cmd = [
                "uvicorn",
                "CONTENT_CREATOR_FRAMEWORK.main_api:app",
                "--host",
                "0.0.0.0",
                "--port",
                "8000",
                "--log-level",
                "info",
            ]

            # Set environment for the subprocess
            env = os.environ.copy()
            env["PYTHONPATH"] = str(PROJECT_ROOT)
            # Pass required environment variables
            env["DATABASE_URL"] = os.environ.get(
                "DATABASE_URL", f"sqlite:///{self.test_output_dir}/test.db"
            )
            env["USE_POSTGRESQL"] = os.environ.get("USE_POSTGRESQL", "false")
            env["ENVIRONMENT"] = os.environ.get("ENVIRONMENT", "testing")
            env["API_KEY"] = os.environ.get("API_KEY", TEST_API_KEY)
            env["LOG_LEVEL"] = os.environ.get("LOG_LEVEL", "INFO")

            self.backend_process = subprocess.Popen(
                backend_cmd,
                cwd=str(PROJECT_ROOT),
                env=env,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )

            # Wait for backend to start
            logger.info("Waiting for backend to start...")
            time.sleep(5)

            # Check if backend is responsive
            max_retries = 10
            for i in range(max_retries):
                if self.is_backend_running():
                    logger.info("Backend started successfully")
                    return True
                time.sleep(2)

            logger.error("Backend failed to start within timeout")
            return False

        except Exception as e:
            logger.error(f"Failed to start backend: {e}")
            return False

    def is_backend_running(self) -> bool:
        """Check if backend is running and responsive."""
        try:
            response = requests.get(f"{TEST_API_URL}/health", timeout=5)
            return response.status_code == 200
        except requests.exceptions.RequestException:
            return False

    def stop_backend(self):
        """Stop the backend server if we started it."""
        if self.backend_process:
            logger.info("Stopping backend server...")
            self.backend_process.terminate()
            try:
                self.backend_process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                self.backend_process.kill()
            self.backend_process = None
            logger.info("Backend stopped")

    def test_health_endpoint(self):
        """Test the health endpoint."""
        logger.info("Testing health endpoint...")

        try:
            response = requests.get(f"{TEST_API_URL}/health", timeout=10)
            if response.status_code == 200:
                health_data = response.json()
                logger.info(f"Health check passed: {health_data}")
                return True
            else:
                logger.error(f"Health check failed with status: {response.status_code}")
                return False
        except Exception as e:
            logger.error(f"Health check error: {e}")
            return False

    def test_questionnaire_schema(self):
        """Test getting questionnaire schema."""
        logger.info("Testing questionnaire schema endpoint...")

        try:
            response = requests.get(f"{TEST_API_URL}/questionnaire-schema", timeout=10)

            if response.status_code == 200:
                schema = response.json()
                logger.info(
                    f"Got questionnaire schema with {len(schema.get('questions', []))} questions"
                )
                return True
            else:
                logger.error(f"Failed to get schema: {response.status_code}")
                return False
        except Exception as e:
            logger.error(f"Questionnaire schema error: {e}")
            return False

    def test_generate_sop_via_api(self):
        """Test SOP generation via API."""
        logger.info("Testing SOP generation via API...")

        # Prepare SOP request
        sop_request = {
            "sop_name": TEST_SOP_NAME,
            "sop_type": TEST_SOP_TYPE,
            "keywords": TEST_KEYWORDS,
            "department": TEST_DEPARTMENT,
            "target_audience": ["All Personnel", "Quality Staff", "Operators"],
        }

        try:
            response = requests.post(
                f"{TEST_API_URL}/generate",
                json=sop_request,
                headers={"X-API-Key": TEST_API_KEY},
                timeout=30,
            )

            if response.status_code == 200:
                result = response.json()
                logger.info(f"SOP generation successful: {result['status']}")

                # Check for output files
                output_files = result.get("output_files", [])
                if output_files:
                    logger.info(f"Generated files: {output_files}")

                    # Verify files exist
                    for file_path in output_files:
                        full_path = PROJECT_ROOT / file_path
                        if full_path.exists():
                            logger.info(f"✓ File exists: {file_path}")
                            file_size = full_path.stat().st_size
                            logger.info(f"  File size: {file_size} bytes")
                        else:
                            logger.warning(f"✗ File missing: {file_path}")

                # Check audit report
                audit_report = result.get("audit_report", {})
                if audit_report:
                    logger.info(f"Audit report: {json.dumps(audit_report, indent=2)}")

                return True, result
            else:
                logger.error(
                    f"SOP generation failed: {response.status_code} - {response.text}"
                )
                return False, None

        except Exception as e:
            logger.error(f"SOP generation error: {e}")
            return False, None

    def test_submit_questionnaire_via_api(self):
        """Test submitting questionnaire via API."""
        logger.info("Testing questionnaire submission via API...")

        # Prepare submission
        submission = {
            "sop_request": {
                "sop_name": "Cleaning and Sanitization",
                "sop_type": "Sanitation",
                "keywords": ["cleaning", "sanitization", "hygiene", "GMP"],
                "department": "Quality",
                "target_audience": ["Cleaning Staff", "Operators", "Quality Control"],
            },
            "answers": SAMPLE_ANSWERS,
        }

        try:
            response = requests.post(
                f"{TEST_API_URL}/submit-questionnaire",
                json=submission,
                headers={"X-API-Key": TEST_API_KEY},
                timeout=60,  # Longer timeout for full workflow
            )

            if response.status_code == 200:
                result = response.json()
                logger.info(f"Questionnaire submission successful: {result['status']}")

                output_files = result.get("output_files", [])
                if output_files:
                    logger.info(f"Generated {len(output_files)} files")

                return True, result
            else:
                logger.error(
                    f"Questionnaire submission failed: {response.status_code} - {response.text}"
                )
                return False, None

        except Exception as e:
            logger.error(f"Questionnaire submission error: {e}")
            return False, None

    def test_direct_workflow(self):
        """Test the workflow directly without API."""
        logger.info("Testing workflow directly...")

        try:
            # Import the workflow module
            sys.path.insert(0, str(PROJECT_ROOT))
            from CONTENT_CREATOR_FRAMEWORK.integrated_sop_generator_workflow import (
                IntegratedSOPWorkflow,
            )

            # Initialize workflow
            workflow = IntegratedSOPWorkflow(str(PROJECT_ROOT))

            # Prepare request
            sop_request = {
                "sop_name": TEST_SOP_NAME,
                "sop_type": TEST_SOP_TYPE,
                "keywords": TEST_KEYWORDS,
                "department": TEST_DEPARTMENT,
                "target_audience": ["All Personnel"],
            }

            # Execute workflow
            logger.info("Executing workflow...")
            result = workflow.execute_workflow(sop_request)

            logger.info(f"Workflow result: {result['status']}")

            # Check output
            if result.get("output_files"):
                for file_path in result["output_files"]:
                    full_path = PROJECT_ROOT / file_path
                    if full_path.exists():
                        logger.info(f"✓ Generated: {file_path}")

            # Check stages
            stages = result.get("stages", {})
            for stage_name, stage_result in stages.items():
                logger.info(
                    f"Stage '{stage_name}': {stage_result.get('status', 'unknown')}"
                )

            return True, result

        except Exception as e:
            logger.error(f"Direct workflow test failed: {e}")
            import traceback

            logger.error(traceback.format_exc())
            return False, None

    def cleanup_test_files(self):
        """Clean up test-generated files."""
        if not self.cleanup:
            logger.info("Skipping cleanup (--no-cleanup flag used)")
            return

        logger.info("Cleaning up test files...")

        # Clean test output directory
        if self.test_output_dir.exists():
            import shutil

            try:
                shutil.rmtree(self.test_output_dir)
                logger.info(f"Cleaned up: {self.test_output_dir}")
            except Exception as e:
                logger.warning(f"Could not clean up {self.test_output_dir}: {e}")

        # Clean generated files in output directories
        output_dirs = ["output", "sops_created"]
        for dir_name in output_dirs:
            dir_path = PROJECT_ROOT / dir_name
            if dir_path.exists():
                # Remove files created during this test session
                # (we could be more selective, but for test we'll clean)
                for file_path in dir_path.glob("*test*"):
                    try:
                        file_path.unlink()
                        logger.info(f"Cleaned up: {file_path}")
                    except Exception as e:
                        logger.warning(f"Could not clean up {file_path}: {e}")

    def run_tests(self) -> bool:
        """Run all tests."""
        logger.info("=" * 60)
        logger.info("Starting Production Test for Cannabis EU GMP QMS Creator")
        logger.info("=" * 60)

        all_passed = True

        try:
            # Setup environment
            self.setup_environment()

            if self.api_mode:
                # API mode tests
                logger.info("\n" + "=" * 40)
                logger.info("API MODE TESTS")
                logger.info("=" * 40)

                # Start backend
                if not self.start_backend():
                    logger.error("Failed to start backend, cannot run API tests")
                    all_passed = False
                    # Fall back to direct mode
                    logger.info("Falling back to direct mode...")
                    self.api_mode = False

                if self.api_mode:
                    # Run API tests
                    if not self.test_health_endpoint():
                        all_passed = False

                    if not self.test_questionnaire_schema():
                        all_passed = False

                    success, result = self.test_generate_sop_via_api()
                    if not success:
                        all_passed = False

                    # Optional: test questionnaire submission (takes longer)
                    logger.info(
                        "\nTesting questionnaire submission (optional, may take time)..."
                    )
                    success, _ = self.test_submit_questionnaire_via_api()
                    if success:
                        logger.info("Questionnaire submission test passed")
                    else:
                        logger.warning(
                            "Questionnaire submission test failed or skipped"
                        )

                    # Stop backend if we started it
                    self.stop_backend()

            if not self.api_mode or not all_passed:
                # Direct mode tests
                logger.info("\n" + "=" * 40)
                logger.info("DIRECT WORKFLOW TESTS")
                logger.info("=" * 40)

                success, result = self.test_direct_workflow()
                if not success:
                    all_passed = False
                else:
                    # Save result for inspection
                    result_file = self.test_output_dir / "workflow_result.json"
                    with open(result_file, "w") as f:
                        json.dump(result, f, indent=2)
                    logger.info(f"Workflow result saved to: {result_file}")

            # Summary
            logger.info("\n" + "=" * 60)
            logger.info("TEST SUMMARY")
            logger.info("=" * 60)

            if all_passed:
                logger.info("✅ All tests passed!")
            else:
                logger.error("❌ Some tests failed")

            # List generated files
            logger.info("\nGenerated files:")
            output_dirs = ["output", "sops_created", "test_production_output"]
            for dir_name in output_dirs:
                dir_path = PROJECT_ROOT / dir_name
                if dir_path.exists():
                    files = list(dir_path.glob("*"))
                    if files:
                        logger.info(f"\n{dir_name}/:")
                        for file_path in files:
                            if file_path.is_file():
                                file_size = file_path.stat().st_size
                                logger.info(f"  {file_path.name} ({file_size} bytes)")

            return all_passed

        except Exception as e:
            logger.error(f"Test execution failed with exception: {e}")
            import traceback

            logger.error(traceback.format_exc())
            return False

        finally:
            # Cleanup
            if self.cleanup and all_passed:
                self.cleanup_test_files()
            else:
                logger.info(f"Test files preserved in: {self.test_output_dir}")
                logger.info("Run with --cleanup to remove test files")


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Test production instance of Cannabis EU GMP QMS Creator"
    )
    parser.add_argument(
        "--api-mode",
        action="store_true",
        default=True,
        help="Test via API (requires backend running)",
    )
    parser.add_argument(
        "--direct-mode", action="store_true", help="Test workflow directly without API"
    )
    parser.add_argument(
        "--no-cleanup", action="store_true", help="Keep generated files for inspection"
    )

    args = parser.parse_args()

    # Determine mode
    if args.direct_mode:
        api_mode = False
    else:
        api_mode = args.api_mode

    # Create tester
    tester = ProductionTester(api_mode=api_mode, cleanup=not args.no_cleanup)

    # Run tests
    success = tester.run_tests()

    # Exit with appropriate code
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
