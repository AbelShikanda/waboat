# waboat
# 📱 WhatsApp Bot Automation Tool

A sophisticated WhatsApp marketing automation bot built with Python and Playwright for automated product posting to WhatsApp groups.

## 🌟 Features

### Core Functionality
- **Multi-Product Support**: Loads from WhatsApp catalogs, Instagram posts, and Facebook posts
- **Smart Product Management**: Random selection, auto-mark as posted, auto-reset when all products are posted
- **Human-Like Posting**: Character-by-character typing, preserves formatting, waits for link previews (15s)
- **Persistent Session**: Saves login to avoid QR code scanning on every run

### CLI Commands
| Command | Description |
|---------|-------------|
| `list` | Display pending products |
| `stats` | Show product statistics by status/source |
| `reset` | Reset all products to pending |
| `groups` | List configured target groups |


## 🚀 Quick Start

### Prerequisites
- Python 3.8+
- WhatsApp account (test account recommended)

### Installation

# Clone and setup
python -m venv venv
venv\Scripts\activate  # Windows
source venv/bin/activate  # Mac/Linux

# Install dependencies
pip install -r requirements.txt
playwright install chromium


### Configure Groups
Edit `target_groups.py` with your WhatsApp group names (exact match required).

### Run the Bot
python whatsapp_bot.py


### CLI Commands
```bash
python whatsapp_bot.py cli list
python whatsapp_bot.py cli stats
python whatsapp_bot.py cli reset
python whatsapp_bot.py cli groups

## 📁 Project Structure

whatsapp_automation/
├── whatsapp_bot.py          # Main entry point
├── login_manager.py         # Login/session management
├── group_poster.py          # Group posting logic
├── smm_cli.py              # CLI commands
├── target_groups.py        # Group lists configuration
├── data/products/          # Product JSON files
│   ├── wa_products.json
│   ├── instagram_posts.json
│   └── facebook_posts.json
└── whatsapp_session/       # Persistent session storage

## 🛡️ Safety & Anti-Detection

- ⚠️ **Use a test account** - Never use primary WhatsApp
- **Human-like typing**: Random delays between characters (100-250ms)
- **Random delays**: 5-12 seconds between posts
- **Line breaks with Shift+Enter**: Looks like manual typing
- **Link preview waiting**: Mimics human behavior (15s delay)
- **Non-headless browser**: Browser is visible like real user
- **Anti-detection script**: Removes automation fingerprints

---

## 🔧 Troubleshooting

| Issue | Solution |
|-------|----------|
| QR code every time | Delete `whatsapp_session/` folder and restart |
| Group not found | Check exact names in `target_groups.py` |
| Compose box not found | WhatsApp updated selectors; check `open_group()` |
| Session incomplete | Run once, scan QR, session saves automatically |


## 📦 Dependencies

playwright==1.48.0

## ⚠️ Disclaimer

**For educational purposes only.** The authors are not responsible for any misuse or violations of WhatsApp's Terms of Service. Always comply with platform policies and respect user privacy.

## 📊 Bot Flow

START → Login → Load Products → Select Random Product → 
Post to Each Group (Open → Type → Wait Preview → Send) → 
Mark Posted → Check Remaining → If 0 → Reset All → Continue


---

**Made with ❤️ for educational purposes**
```
