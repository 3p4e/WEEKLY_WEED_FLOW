#!/usr/bin/env python3
"""
Simple Dependency Checker for Cannabis EU GMP QMS Creator

This script provides a quick check for essential dependencies and configuration.
It's designed to be lightweight and fast for regular use.

Usage:
    python check_deps.py
"""

import json
import os
import sys
from pathlib import Path


def check_python_deps():
    """Check Python dependencies."""
    print("🔍 Checking Python dependencies...")

    # Check requirements.txt exists
    req_file = Path("requirements.txt")
    if not req_file.exists():
        print("❌ requirements.txt not found")
        return False

    # Try to import key modules
    key_modules = [
        ("fastapi", "FastAPI framework"),
        ("pydantic", "Data validation"),
        ("sqlalchemy", "Database ORM"),
        ("uvicorn", "ASGI server"),
        ("yaml", "YAML parsing"),
        ("CONTENT_CREATOR_FRAMEWORK.main_api", "Main application"),
    ]

    all_ok = True
    for module, description in key_modules:
        try:
            if "." in module:
                # Handle module.attribute imports
                mod_name, attr_name = module.split(".", 1)
                __import__(mod_name)
            else:
                __import__(module)
            print(f"  ✅ {module} - {description}")
        except ImportError as e:
            print(f"  ❌ {module} - {description}: {e}")
            all_ok = False

    return all_ok


def check_config_files():
    """Check essential configuration files."""
    print("\n🔍 Checking configuration files...")

    configs = [
        ("config/document_registry.yaml", "Document registry"),
        ("CONTENT_CREATOR_FRAMEWORK/templates/sop_templates.yaml", "SOP templates"),
        (".env", "Environment variables"),
    ]

    all_ok = True
    for path, description in configs:
        config_path = Path(path)
        if config_path.exists():
            print(f"  ✅ {path} - {description}")
        else:
            print(f"  ❌ {path} - {description} (not found)")
            all_ok = False

    return all_ok


def check_directory_structure():
    """Check essential directories."""
    print("\n🔍 Checking directory structure...")

    dirs = [
        "CONTENT_CREATOR_FRAMEWORK",
        "output",
        "sops_created",
        "01_QUALITY_ASSURANCE",
        "config",
        "qms-ui/dist",
    ]

    all_ok = True
    for dir_path in dirs:
        if Path(dir_path).exists():
            print(f"  ✅ {dir_path}/")
        else:
            print(f"  ❌ {dir_path}/ (not found)")
            all_ok = False

    return all_ok


def check_frontend():
    """Check frontend build."""
    print("\n🔍 Checking frontend...")

    # Check if dist directory exists
    dist_dir = Path("qms-ui/dist")
    if dist_dir.exists():
        print("  ✅ Frontend build exists (dist/)")
        return True
    else:
        print("  ⚠️  Frontend not built (dist/ not found)")
        print("     Run: cd qms-ui && npm run build")
        return False


def run_health_check():
    """Run a quick health check on the API."""
    print("\n🔍 Running health check...")

    try:
        # Add current directory to path
        sys.path.insert(0, str(Path.cwd()))

        from fastapi.testclient import TestClient

        from CONTENT_CREATOR_FRAMEWORK.main_api import app

        client = TestClient(app)
        response = client.get("/health")

        if response.status_code == 200:
            print(f"  ✅ Health check passed (HTTP {response.status_code})")
            return True
        else:
            print(f"  ❌ Health check failed (HTTP {response.status_code})")
            return False

    except Exception as e:
        print(f"  ❌ Health check error: {e}")
        return False


def main():
    """Main function."""
    print("=" * 60)
    print("Cannabis EU GMP QMS Creator - Dependency Check")
    print("=" * 60)

    # Store results
    results = []

    # Run checks
    results.append(("Python Dependencies", check_python_deps()))
    results.append(("Configuration Files", check_config_files()))
    results.append(("Directory Structure", check_directory_structure()))
    results.append(("Frontend Build", check_frontend()))
    results.append(("API Health Check", run_health_check()))

    # Print summary
    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)

    all_passed = True
    for check_name, passed in results:
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"{status} - {check_name}")
        if not passed:
            all_passed = False

    print("\n" + "=" * 60)
    if all_passed:
        print("🎉 All checks passed! The system is ready.")
    else:
        print("⚠️  Some checks failed. Review the issues above.")
        print("\nRecommended actions:")
        print("1. Install missing Python packages: pip install -r requirements.txt")
        print("2. Create missing configuration files")
        print("3. Build frontend: cd qms-ui && npm run build")
        print("4. Check .env file configuration")
        sys.exit(1)


if __name__ == "__main__":
    main()
