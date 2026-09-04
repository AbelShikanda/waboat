## 📄 README.md

# 📱 WhatsApp Bot Automation Tool (waboat)

A sophisticated WhatsApp marketing automation bot built with Python and Playwright for automated product posting to WhatsApp groups.

## 🌟 Features

### Core Functionality
- **Multi-Product Support**: Loads from WhatsApp catalogs, Instagram, Facebook, LinkedIn, Telegram, Website, and X/Twitter posts
- **Smart Product Management**: Random selection, auto-mark as posted, auto-reset when all products are posted
- **Human-Like Posting**: Character-by-character typing, preserves formatting, waits for link previews
- **Connection Monitoring**: Detects disconnections and automatically reconnects
- **Data Collection**: Collects chat history and stores in SQLite database for analytics

### CLI Commands
| Command | Description |
|---------|-------------|
| `list` | Display pending products |
| `stats` | Show product statistics by status/source |
| `reset` | Reset all products to pending |
| `groups` | List configured target groups |
| `analytics` | Show analytics dashboard |
| `trending` | Show trending topics |

## 🚀 Quick Start

### Prerequisites
- Python 3.8+
- WhatsApp account (test account recommended)
- Git

### Installation on a New Computer

# 1. Clone the repository
git clone https://github.com/yourusername/whatsapp-bot.git
cd whatsapp-bot

# 2. Create and activate virtual environment
python -m venv venv
# On Windows:
venv\Scripts\activate
# On Mac/Linux:
source venv/bin/activate

# 3. Install dependencies
pip install -r requirements.txt
playwright install chromium

# 4. Run the setup script (creates directories and example files)
python setup.py

# 5. Copy example product files to actual files
cp data/products/*.example.json data/products/*.json

# 6. Configure your products and groups
# Edit data/products/*.json with your products
# Edit target_groups.py with your groups
# Edit target_audience.py if needed

### Running the Bot

# Normal product posting
python whatsapp_bot.py

# Group management
python whatsapp_bot.py manage-groups

# Link marketing
python whatsapp_bot.py link-market

# Send messages to contacts
python whatsapp_bot.py send-messages new_year

# CLI commands
python whatsapp_bot.py cli list
python whatsapp_bot.py cli stats
python whatsapp_bot.py cli reset
python whatsapp_bot.py cli groups

# Analytics
python whatsapp_bot.py analytics
python whatsapp_bot.py trending
python whatsapp_bot.py stats

## 📁 Project Structure

whatsapp-bot/
├── 📄 Core Files
│   ├── whatsapp_bot.py          # Main entry point
│   ├── login_manager.py         # Login/session management
│   ├── group_poster.py          # Group posting logic
│   ├── group_manager.py         # Group management
│   ├── group_link_marketer.py   # Link marketing
│   ├── contact_messenger.py     # Contact messaging
│   ├── db_logic.py              # Database operations
│   ├── analytics_module.py      # Analytics
│   ├── smm_cli.py              # CLI commands
│   ├── target_groups.py        # Group lists configuration
│   ├── target_audience.py      # Audience configuration
│   └── setup.py                # Setup script (run once)
│
├── 📁 data/ (Runtime Data - Ignored by Git)
│   ├── 📁 products/
│   │   ├── *.example.json       # ✅ Templates (tracked in Git)
│   │   ├── *.json               # ❌ Actual files (ignored)
│   │   └── README.md            # Documentation
│   ├── 📁 analytics/            # Analytics data (ignored)
│   ├── 📁 exports/              # Export files (ignored)
│   ├── 📁 links/                # Link data (ignored)
│   ├── 📁 marketing/            # Marketing data (ignored)
│   ├── *.db                     # Database (ignored)
│   └── *.json                   # Queue/history (ignored)
│
├── 📁 whatsapp_session/         # Session storage (ignored)
├── 📁 logs/                     # Log files (ignored)
├── 📁 images/                   # Images (ignored)
├── 📁 notes/                    # Notes (ignored)
├── 📁 venv/                     # Virtual environment (ignored)
│
├── requirements.txt             # Python dependencies
├── README.md                    # This file
├── LICENSE                      # License
└── .gitignore                   # Git ignore rules

## 🔄 Git Workflow

### Cloning on a New Computer

# 1. Clone
git clone https://github.com/yourusername/whatsapp-bot.git
cd whatsapp-bot

# 2. Setup
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt
playwright install chromium
python setup.py

# 3. Configure
cp data/products/*.example.json data/products/*.json
# Edit your products and groups

# 4. Run
python whatsapp_bot.py

### Pulling Updates

# Pull latest changes
git pull

# If requirements changed
pip install -r requirements.txt

# If new example files were added
python setup.py  # Creates new directories/examples without overwriting

# Check if product templates changed
# Compare .example files with your .json files
diff data/products/wa_products.example.json data/products/wa_products.json

### What Gets Tracked vs Ignored

| Tracked in Git | Ignored by Git |
|---|---|
| All Python source code | data/*.db (database) |
| Product templates (*.example.json) | data/products/*.json (actual products) |
| Directory structure (.gitkeep) | data/analytics/* (analytics data) |
| README.md, LICENSE | data/exports/* (exports) |
| requirements.txt | whatsapp_session/ (session) |
| .gitignore | logs/*.log (logs) |
| setup.py | venv/ (virtual environment) |
| target_groups.py | __pycache__/ |
| All other .py files | .env (environment variables) |
| .vscode/ (with settings exceptions) | data/links/* (link data) |
| .idea/ | data/marketing/* (marketing data) |

## 📦 Dependencies

playwright==1.48.0
# See requirements.txt for full list

## 🛡️ Safety & Anti-Detection

- ⚠️ **Use a test account** - Never use primary WhatsApp
- **Human-like typing**: Random delays between characters
- **Random delays**: Between posts and groups
- **Line breaks with Shift+Enter**: Looks like manual typing
- **Link preview waiting**: Mimics human behavior
- **Non-headless browser**: Browser is visible like real user
- **Anti-detection script**: Removes automation fingerprints
- **Connection monitoring**: Detects and handles disconnections

## 🔧 Troubleshooting

| Issue | Solution |
|-------|----------|
| QR code every time | Delete `whatsapp_session/` folder and restart |
| Group not found | Check exact names in `target_groups.py` |
| Compose box not found | WhatsApp updated selectors; check `open_group()` |
| Session incomplete | Run once, scan QR, session saves automatically |
| Module not found | Run `pip install -r requirements.txt` |
| Playwright error | Run `playwright install chromium` |
| Data files missing | Run `python setup.py` |
| VS Code settings not applying | Check `.vscode/` folder is tracked |

## 📊 Bot Flow

START → Login → Load Products → Select Random Product →
Post to Each Group (Open → Type → Wait Preview → Send) →
Collect Chat History → Save to Database →
Mark Posted → Check Remaining → If 0 → Reset All → Continue
```

## ⚠️ Disclaimer

**For educational purposes only.** The authors are not responsible for any misuse or violations of WhatsApp's Terms of Service. Always comply with platform policies and respect user privacy.


**Made with ❤️ for educational purposes**