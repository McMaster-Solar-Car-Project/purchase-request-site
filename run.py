#!/usr/bin/env python3
"""
Simple runner script for the Purchase Request Site application.
This script allows running the app from the project root while the code is in purchase_request-site/
"""

import os
import subprocess
import sys

from dotenv import load_dotenv


def main():
    load_dotenv()
    # Change to the purchase_request-site directory
    script_dir = os.path.dirname(os.path.abspath(__file__))
    app_dir = os.path.join(script_dir, "purchase_request_site")

    if not os.path.exists(app_dir):
        print("Error: purchase_request-site directory not found!")
        sys.exit(1)

    # Change to the app directory
    os.chdir(app_dir)

    # Run the application using uvicorn
    # Check if we're in production (no --reload, use PORT env var)
    is_production = os.getenv("ENVIRONMENT") == "production"

    try:
        if is_production:
            # Production: No reload, use PORT env var or default to 8000
            port = os.getenv("PORT", "8000")
            subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "uvicorn",
                    "main:app",
                    "--host",
                    "0.0.0.0",
                    "--port",
                    port,
                    "--workers",
                    "1",
                ],
                check=True,
            )
        else:
            # Development: Keep reload, use uv
            subprocess.run(
                [
                    "uv",
                    "run",
                    "uvicorn",
                    "main:app",
                    "--reload",
                    "--host",
                    "0.0.0.0",
                    "--port",
                    "8000",
                ],
                check=True,
            )
    except subprocess.CalledProcessError as e:
        print(f"Error running the application: {e}")
        sys.exit(1)
    except KeyboardInterrupt:
        print("\nApplication stopped by user")
        sys.exit(0)


if __name__ == "__main__":
    main()
