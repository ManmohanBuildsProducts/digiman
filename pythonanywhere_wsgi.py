# PythonAnywhere WSGI Configuration
#
# Copy this content to your WSGI configuration file on PythonAnywhere
# (Web tab → WSGI configuration file)
#
# Replace YOUR_USERNAME with your PythonAnywhere username

import sys
import os

# Add your project to the path
path = '/home/YOUR_USERNAME/digiman'
if path not in sys.path:
    sys.path.append(path)

# Load environment variables from .env
from dotenv import load_dotenv
load_dotenv(os.path.join(path, '.env'))

# Import the Flask app
from digiman.app import app as application
