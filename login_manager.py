"""
Login Manager
=============
Handles all WhatsApp Web login and session management:
- Session checking and validation
- QR code display
- Persistent session storage
- Browser launch with anti-detection
"""

import json
import asyncio
from pathlib import Path
from playwright.async_api import async_playwright

# ============================================================
# CONFIGURATION
# ============================================================

BASE_DIR = Path(__file__).parent
SESSION_DIR = BASE_DIR / "whatsapp_session"
WHATSAPP_WEB_URL = "https://web.whatsapp.com"
MAX_LOGIN_ATTEMPTS = 3

# Create session directory
SESSION_DIR.mkdir(exist_ok=True)

# ============================================================
# LOGIN MANAGER CLASS
# ============================================================

class LoginManager:
    """Manages WhatsApp Web login and session"""
    
    def __init__(self):
        self.browser = None
        self.context = None
        self.page = None
        self.playwright = None
        self.is_logged_in = False
    
    # ============================================================
    # SESSION MANAGEMENT
    # ============================================================
    
    async def check_session(self) -> bool:
        """Check if session exists and is valid"""
        session_folder = Path("whatsapp_session")
        session_file = Path("whatsapp_session.json")
        
        if not session_folder.exists() or not list(session_folder.glob("*")):
            print("📱 No session folder found - will scan QR")
            return False
        
        if session_file.exists() and session_file.stat().st_size > 0:
            try:
                with open(session_file, 'r') as f:
                    data = json.load(f)
                    if data.get('cookies') or data.get('origins'):
                        print("✅ Valid session found")
                        return True
            except:
                print("⚠️ Session file corrupted - will scan QR")
                return False
        
        print("⚠️ Session incomplete - will scan QR")
        return False
    
    async def ensure_session(self):
        """Ensure session exists, create if needed"""
        print("\n" + "=" * 60)
        print("🔐 SESSION MANAGEMENT")
        print("=" * 60)
        has_session = await self.check_session()
        
        if has_session:
            print("✅ Valid session - auto-login will occur")
        else:
            print("📱 No valid session - QR code will be shown")
            print("   Open WhatsApp on your phone")
            print("   Tap ⋮ → Linked Devices → Link a Device")
            print("   Scan the QR code in the browser")
        
        print("=" * 60 + "\n")
        return has_session
    
    async def save_session_state(self):
        """Save session state properly"""
        try:
            if not self.context:
                return False
            
            storage = await self.context.storage_state()
            
            if not storage.get('cookies') and not storage.get('origins'):
                print("⚠️ No session data to save")
                return False
            
            with open('whatsapp_session.json', 'w') as f:
                json.dump(storage, f)
            
            if Path('whatsapp_session.json').stat().st_size > 0:
                print("💾 Session saved successfully!")
                return True
            else:
                print("⚠️ Session file saved but appears empty")
                return False
                
        except Exception as e:
            print(f"⚠️ Could not save session: {e}")
            return False
    
    # ============================================================
    # BROWSER LAUNCH
    # ============================================================
    
    async def launch_browser(self):
        """Launch browser with persistent context"""
        try:
            self.playwright = await async_playwright().start()
            
            self.context = await self.playwright.chromium.launch_persistent_context(
                user_data_dir="./whatsapp_session",
                headless=False,
                args=[
                    '--disable-blink-features=AutomationControlled',
                    '--disable-dev-shm-usage',
                    '--no-sandbox',
                    '--disable-setuid-sandbox'
                ],
                user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                viewport={'width': 1280, 'height': 720}
            )
            
            if self.context.pages:
                self.page = self.context.pages[0]
            else:
                self.page = await self.context.new_page()
            
            # Add anti-detection script
            await self.page.add_init_script("""
                Object.defineProperty(navigator, 'webdriver', {
                    get: () => undefined
                });
            """)
            
            return True
            
        except Exception as e:
            print(f"❌ Error launching browser: {e}")
            return False
    
    # ============================================================
    # LOGIN
    # ============================================================
    
    async def login(self) -> bool:
        """Complete login process"""
        print("=" * 60)
        print("🚀 WhatsApp Bot Login")
        print("=" * 60)
        
        await self.ensure_session()
        
        for attempt in range(MAX_LOGIN_ATTEMPTS):
            print(f"\n🔄 Login attempt {attempt + 1}/{MAX_LOGIN_ATTEMPTS}")
            
            try:
                if not await self.launch_browser():
                    continue
                
                print("🌐 Loading WhatsApp Web...")
                await self.page.goto(WHATSAPP_WEB_URL, wait_until='domcontentloaded')
                await asyncio.sleep(5)
                
                print("⏳ Waiting for login...")
                login_success = await self._wait_for_login()
                
                if login_success:
                    print("✅ Login successful!")
                    await self.save_session_state()
                    self.is_logged_in = True
                    return True
                else:
                    print(f"❌ Login attempt {attempt + 1} failed")
                    if attempt < MAX_LOGIN_ATTEMPTS - 1:
                        print("🔄 Retrying in 5 seconds...")
                        await asyncio.sleep(5)
                        await self.cleanup()
                        
            except Exception as e:
                print(f"❌ Error during login: {e}")
                if attempt < MAX_LOGIN_ATTEMPTS - 1:
                    print("🔄 Retrying in 5 seconds...")
                    await asyncio.sleep(5)
                    await self.cleanup()
        
        print("❌ Max login attempts reached. Could not log in.")
        return False
    
    async def _wait_for_login(self, timeout=120):
        """Wait for login - show QR if needed"""
        print("🔍 Looking for QR code...")
        print("   Open WhatsApp → Linked Devices → Link a Device")
        
        start_time = asyncio.get_event_loop().time()
        
        login_indicators = [
            '[data-testid="chat-list"]',
            'div[role="row"]',
            '[data-testid="pane-side"]'
        ]
        
        while asyncio.get_event_loop().time() - start_time < timeout:
            try:
                # Check if already logged in
                for selector in login_indicators:
                    element = await self.page.query_selector(selector)
                    if element:
                        is_visible = await element.is_visible()
                        if is_visible:
                            print(f"✅ Already logged in!")
                            return True
                
                # Check for QR code
                qr = await self.page.query_selector('canvas[aria-label="Scan me!"]')
                if qr:
                    is_visible = await qr.is_visible()
                    if is_visible:
                        print("📱 QR CODE FOUND! Scan with your phone")
                
                await asyncio.sleep(2)
                
            except Exception as e:
                print(f"⚠️ Login check error: {e}")
                await asyncio.sleep(2)
        
        print("❌ Login timeout")
        return False
    
    # ============================================================
    # CLEANUP
    # ============================================================
    
    async def cleanup(self):
        """Clean up browser resources"""
        try:
            if self.page:
                await self.page.close()
            if self.context:
                await self.context.close()
            if self.browser:
                await self.browser.close()
            if self.playwright:
                await self.playwright.stop()
        except:
            pass
        
        self.page = None
        self.context = None
        self.browser = None
        self.playwright = None
    
    async def shutdown(self):
        """Shutdown login manager"""
        print("🔄 Shutting down...")
        await self.cleanup()
        print("👋 Goodbye!")