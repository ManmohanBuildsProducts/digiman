# Digiman Deployment Guide - PythonAnywhere

## Step 1: Create PythonAnywhere Account

1. Go to https://www.pythonanywhere.com
2. Sign up for a **free** account
3. Note your username (it will be in your URL: `YOUR_USERNAME.pythonanywhere.com`)

---

## Step 2: Clone and Setup

Open a **Bash console** on PythonAnywhere (Consoles → Bash):

```bash
# Clone your repo
git clone https://github.com/Mission10k/digiman.git
cd digiman

# Create virtual environment
python3.10 -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Create data directory
mkdir -p data

# Initialize database
python scripts/setup_db.py
```

---

## Step 3: Configure Environment

Create the `.env` file:

```bash
cat > .env << 'EOF'
DATABASE_PATH=/home/YOUR_USERNAME/digiman/data/todos.db
FLASK_SECRET_KEY=your-secure-random-key-here
FLASK_DEBUG=false
EOF
```

**Replace `YOUR_USERNAME` with your actual PythonAnywhere username!**

Generate a secure secret key:
```bash
python -c "import secrets; print(secrets.token_hex(32))"
```

---

## Step 4: Configure Web App

1. Go to **Web** tab → **Add a new web app**
2. Click **Next** (accept free domain)
3. Select **Manual configuration**
4. Select **Python 3.10**
5. Click **Next** to create

Now configure:

### Source code
```
/home/YOUR_USERNAME/digiman
```

### Working directory
```
/home/YOUR_USERNAME/digiman
```

### Virtualenv
```
/home/YOUR_USERNAME/digiman/venv
```

### WSGI configuration file
Click the link to edit, then **replace ALL content** with:

```python
import sys
import os

path = '/home/YOUR_USERNAME/digiman'
if path not in sys.path:
    sys.path.append(path)

from dotenv import load_dotenv
load_dotenv(os.path.join(path, '.env'))

from digiman.app import app as application
```

**Replace `YOUR_USERNAME` in all 3 places!**

---

## Step 5: Reload and Test

1. Click the green **Reload** button on the Web tab
2. Visit: `https://YOUR_USERNAME.pythonanywhere.com`
3. Add a todo, complete it, check the Calendar view

---

## Troubleshooting

### Check Error Log
Web tab → Error log (link at bottom)

### Common Issues

**ModuleNotFoundError**
- Check virtualenv path is correct
- Run `pip list` in console to verify flask is installed

**Database errors**
- Ensure `/home/YOUR_USERNAME/digiman/data/` exists
- Run `python scripts/setup_db.py` again

**500 errors**
- Check the error log
- Verify `.env` file exists and has correct paths

---

## Updating the App

In PythonAnywhere Bash console:
```bash
cd ~/digiman
git pull
source venv/bin/activate
pip install -r requirements.txt
```

Then click **Reload** on the Web tab.

---

## GitHub Repo

https://github.com/Mission10k/digiman
