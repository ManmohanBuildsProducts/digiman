#!/usr/bin/env python3
"""Run the Digiman Flask app."""

import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

from digiman.app import app

if __name__ == "__main__":
    app.run(debug=True, port=5050, host="0.0.0.0")
