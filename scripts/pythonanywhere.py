#!/usr/bin/env python3
"""PythonAnywhere management script for Digiman.

Usage:
    python scripts/pythonanywhere.py status      # Check app status and recent errors
    python scripts/pythonanywhere.py logs        # View recent error logs
    python scripts/pythonanywhere.py reload      # Reload the web app
    python scripts/pythonanywhere.py deploy      # Upload all digiman files and reload
    python scripts/pythonanywhere.py upload FILE # Upload a specific file
"""

import argparse
import json
import os
import sys
from pathlib import Path
import urllib.request
import urllib.error

# Load config
CONFIG_PATH = Path(__file__).parent.parent / ".pythonanywhere-config.json"

def load_config():
    if not CONFIG_PATH.exists():
        print("Error: .pythonanywhere-config.json not found")
        print("Create it with: {\"username\": \"...\", \"api_token\": \"...\"}")
        sys.exit(1)
    with open(CONFIG_PATH) as f:
        return json.load(f)

CONFIG = load_config()
USERNAME = CONFIG["username"]
API_TOKEN = CONFIG["api_token"]
API_BASE = f"https://www.pythonanywhere.com/api/v0/user/{USERNAME}"
DOMAIN = f"{USERNAME}.pythonanywhere.com"

def api_request(endpoint, method="GET", data=None, files=None):
    """Make an API request to PythonAnywhere."""
    url = f"{API_BASE}/{endpoint}"
    headers = {"Authorization": f"Token {API_TOKEN}"}

    if files:
        # Multipart form data for file uploads
        import mimetypes
        boundary = "----PythonAnywhereUpload"
        headers["Content-Type"] = f"multipart/form-data; boundary={boundary}"

        body = []
        for field_name, file_path in files.items():
            with open(file_path, "rb") as f:
                file_content = f.read()
            body.append(f"--{boundary}".encode())
            body.append(f'Content-Disposition: form-data; name="{field_name}"; filename="{Path(file_path).name}"'.encode())
            body.append(b"Content-Type: application/octet-stream")
            body.append(b"")
            body.append(file_content)
        body.append(f"--{boundary}--".encode())
        body.append(b"")
        data = b"\r\n".join(body)
    elif data and isinstance(data, dict):
        data = json.dumps(data).encode()
        headers["Content-Type"] = "application/json"

    req = urllib.request.Request(url, data=data, headers=headers, method=method)

    try:
        with urllib.request.urlopen(req) as response:
            content = response.read().decode()
            if content:
                try:
                    return json.loads(content)
                except json.JSONDecodeError:
                    return content
            return {"status": "OK"}
    except urllib.error.HTTPError as e:
        error_body = e.read().decode()
        print(f"API Error {e.code}: {error_body}")
        return None

def cmd_status(args):
    """Check app status and recent errors."""
    print(f"Checking {DOMAIN}...\n")

    # Check if site responds
    try:
        req = urllib.request.Request(f"https://{DOMAIN}/", method="HEAD")
        with urllib.request.urlopen(req, timeout=10) as response:
            print(f"Site Status: {response.status} OK")
    except urllib.error.HTTPError as e:
        print(f"Site Status: {e.code} ERROR")
    except Exception as e:
        print(f"Site Status: UNREACHABLE - {e}")

    # Get webapp info
    apps = api_request("webapps/")
    if apps:
        app = apps[0] if isinstance(apps, list) else apps
        print(f"Python Version: {app.get('python_version', 'unknown')}")
        print(f"Source Directory: {app.get('source_directory', 'unknown')}")
        print(f"Expiry: {app.get('expiry', 'unknown')}")

    # Show recent errors
    print("\n--- Recent Errors ---")
    cmd_logs(args, limit=10)

def cmd_logs(args, limit=50):
    """View recent error logs."""
    log_path = f"files/path/var/log/{DOMAIN.lower()}.error.log"
    content = api_request(log_path)

    if content and isinstance(content, str):
        lines = content.strip().split("\n")
        for line in lines[-limit:]:
            print(line)
    elif content and "error" in str(content).lower():
        print(f"Could not fetch logs: {content}")
    else:
        print("No recent errors found.")

def cmd_reload(args):
    """Reload the web app."""
    print(f"Reloading {DOMAIN}...")
    result = api_request(f"webapps/{DOMAIN}/reload/", method="POST")
    if result and result.get("status") == "OK":
        print("Reload successful!")
    else:
        print(f"Reload failed: {result}")

def cmd_upload(args):
    """Upload a specific file."""
    local_path = Path(args.file).resolve()
    if not local_path.exists():
        print(f"File not found: {local_path}")
        sys.exit(1)

    # Determine remote path
    project_root = Path(__file__).parent.parent
    if local_path.is_relative_to(project_root):
        relative = local_path.relative_to(project_root)
        remote_path = f"/home/{USERNAME}/digiman/{relative}"
    else:
        remote_path = f"/home/{USERNAME}/{local_path.name}"

    print(f"Uploading {local_path.name} -> {remote_path}")

    # Read file and upload
    with open(local_path, "rb") as f:
        content = f.read()

    # Use curl for file upload (urllib multipart is tricky)
    import subprocess
    result = subprocess.run([
        "curl", "-s", "-X", "POST",
        "-H", f"Authorization: Token {API_TOKEN}",
        "-F", f"content=@{local_path}",
        f"{API_BASE}/files/path{remote_path}"
    ], capture_output=True, text=True)

    if result.returncode == 0:
        print("Upload successful!")
    else:
        print(f"Upload failed: {result.stderr}")

def cmd_deploy(args):
    """Upload all digiman files and reload."""
    project_root = Path(__file__).parent.parent
    digiman_dir = project_root / "digiman"

    # Files to upload
    files_to_upload = []
    for pattern in ["**/*.py", "**/*.html", "**/*.css", "**/*.js"]:
        files_to_upload.extend(digiman_dir.glob(pattern))

    print(f"Deploying {len(files_to_upload)} files to PythonAnywhere...")

    import subprocess
    for local_path in files_to_upload:
        relative = local_path.relative_to(project_root)
        remote_path = f"/home/{USERNAME}/digiman/{relative}"

        result = subprocess.run([
            "curl", "-s", "-X", "POST",
            "-H", f"Authorization: Token {API_TOKEN}",
            "-F", f"content=@{local_path}",
            f"{API_BASE}/files/path{remote_path}"
        ], capture_output=True, text=True)

        status = "OK" if result.returncode == 0 else "FAILED"
        print(f"  {relative}: {status}")

    print("\nReloading app...")
    cmd_reload(args)

def main():
    parser = argparse.ArgumentParser(description="PythonAnywhere management for Digiman")
    subparsers = parser.add_subparsers(dest="command", help="Command to run")

    subparsers.add_parser("status", help="Check app status and recent errors")
    subparsers.add_parser("logs", help="View recent error logs")
    subparsers.add_parser("reload", help="Reload the web app")
    subparsers.add_parser("deploy", help="Upload all digiman files and reload")

    upload_parser = subparsers.add_parser("upload", help="Upload a specific file")
    upload_parser.add_argument("file", help="File to upload")

    args = parser.parse_args()

    if args.command == "status":
        cmd_status(args)
    elif args.command == "logs":
        cmd_logs(args)
    elif args.command == "reload":
        cmd_reload(args)
    elif args.command == "deploy":
        cmd_deploy(args)
    elif args.command == "upload":
        cmd_upload(args)
    else:
        parser.print_help()

if __name__ == "__main__":
    main()
