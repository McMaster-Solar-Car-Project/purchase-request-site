#!/usr/bin/env python3
"""
Simple runner script for the Purchase Request Site application.
This script allows running the app from the project root while the code is in purchase_request-site/
"""

import os
import sys
import subprocess

def main():
    # Change to the purchase_request-site directory
    script_dir = os.path.dirname(os.path.abspath(__file__))
    app_dir = os.path.join(script_dir, "purchase_request-site")
    
    if not os.path.exists(app_dir):
        print("Error: purchase_request-site directory not found!")
        sys.exit(1)
    
    # Change to the app directory
    os.chdir(app_dir)
    
    # Run the application using uvicorn
    try:
        subprocess.run([
            "uv", "run", "uvicorn", "main:app", 
            "--reload", "--host", "0.0.0.0", "--port", "8000"
        ], check=True)
    except subprocess.CalledProcessError as e:
        print(f"Error running the application: {e}")
        sys.exit(1)
    except KeyboardInterrupt:
        print("\nApplication stopped by user")
        sys.exit(0)

if __name__ == "__main__":
    main() 