"""
Login Manager
=============
Handles all WhatsApp Web login and session management:
- Session checking and validation
- QR code display with retry logic
- Persistent session storage
- Browser launch with anti-detection
- 5 retry attempts with 1 minute between retries
- 4 minute wait before page refresh
- Media blocking for faster performance
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
MAX_LOGIN_ATTEMPTS = 5  # Increased from 3 to 5
RETRY_DELAY = 60  # 1 minute between retries
QR_REFRESH_DELAY = 360  # 4 minutes before refresh

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
        self.media_blocked = False
    
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
            print(f"   ⏳ Will wait up to {QR_REFRESH_DELAY}s before refreshing")
        
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
    # MEDIA BLOCKING (Performance Optimization)
    # ============================================================
    
    async def block_media_downloads(self):
        """
        Block auto-download of media files for faster performance.
        This prevents WhatsApp from downloading images, videos, and other media
        during login and group navigation.
        """
        if self.media_blocked:
            return
        
        print("🛑 Blocking media auto-downloads for faster performance...")
        
        # Media file extensions to block
        media_extensions = [
            '.jpg', '.jpeg', '.png', '.gif', '.webp', '.bmp', '.ico',  # Images
            '.mp4', '.webm', '.avi', '.mov', '.mkv', '.flv', '.wmv',   # Videos
            '.mp3', '.wav', '.ogg', '.m4a', '.flac', '.aac',            # Audio
            '.pdf', '.doc', '.docx', '.xls', '.xlsx', '.ppt', '.pptx',  # Documents
            '.zip', '.rar', '.7z', '.tar', '.gz',                      # Archives
        ]
        
        # Block media file requests
        await self.page.route('**/*', lambda route: self._handle_media_route(route, media_extensions))
        
        self.media_blocked = True
        print("✅ Media downloads blocked - performance optimized!")
    
    async def _handle_media_route(self, route, media_extensions):
        """
        Handle route interception for media files.
        Blocks media files, allows all other requests.
        """
        url = route.request.url.lower()
        
        # Block media files
        for ext in media_extensions:
            if ext in url:
                try:
                    await route.abort()
                except Exception:
                    pass
                return
        
        # Allow all other requests
        try:
            await route.continue_()
        except Exception:
            pass
    
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
                    '--disable-setuid-sandbox',
                    '--disable-features=PreloadMediaEngagementData',  # Disable media preloading
                    '--disable-features=AutomaticTabDiscarding',      # Keep tabs alive
                    '--disable-background-timer-throttling',          # Better performance
                    '--disable-backgrounding-occluded-windows',       # Better performance
                    '--disable-renderer-backgrounding',               # Better performance
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
    # LOGIN WITH RETRY
    # ============================================================
    
    async def login(self) -> bool:
        """Complete login process with 5 retries and 1 minute between retries"""
        print("=" * 60)
        print("🚀 WhatsApp Bot Login")
        print("=" * 60)
        print(f"📋 Max attempts: {MAX_LOGIN_ATTEMPTS}")
        print(f"⏳ Retry delay: {RETRY_DELAY}s between attempts")
        print(f"🔄 Page refresh: After {QR_REFRESH_DELAY}s if no QR")
        print("🛑 Media blocking: Enabled (faster performance)")
        print("=" * 60)
        
        await self.ensure_session()
        
        for attempt in range(MAX_LOGIN_ATTEMPTS):
            attempt_num = attempt + 1
            print(f"\n🔄 Login attempt {attempt_num}/{MAX_LOGIN_ATTEMPTS}")
            
            try:
                if not await self.launch_browser():
                    print(f"❌ Failed to launch browser on attempt {attempt_num}")
                    if attempt_num < MAX_LOGIN_ATTEMPTS:
                        print(f"⏳ Waiting {RETRY_DELAY}s before retry...")
                        await asyncio.sleep(RETRY_DELAY)
                    continue
                
                # Block media BEFORE loading WhatsApp (critical for performance)
                await self.block_media_downloads()
                
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
                    print(f"❌ Login attempt {attempt_num} failed")
                    if attempt_num < MAX_LOGIN_ATTEMPTS:
                        print(f"⏳ Waiting {RETRY_DELAY}s before retry...")
                        await self.cleanup()
                        await asyncio.sleep(RETRY_DELAY)
                        
            except Exception as e:
                print(f"❌ Error during login attempt {attempt_num}: {e}")
                if attempt_num < MAX_LOGIN_ATTEMPTS:
                    print(f"⏳ Waiting {RETRY_DELAY}s before retry...")
                    await self.cleanup()
                    await asyncio.sleep(RETRY_DELAY)
        
        print(f"❌ Max login attempts ({MAX_LOGIN_ATTEMPTS}) reached. Could not log in.")
        return False
    
    async def _wait_for_login(self, timeout=300):
        """
        Wait for login - show QR if needed
        Waits up to 4 minutes (240s) before refreshing the page
        """
        print("🔍 Looking for QR code...")
        print("   Open WhatsApp → Linked Devices → Link a Device")
        print(f"   ⏳ Will wait {QR_REFRESH_DELAY}s before refreshing")
        
        start_time = asyncio.get_event_loop().time()
        last_refresh = start_time
        qr_shown = False
        progress_interval = 30
        
        login_indicators = [
            '[data-testid="chat-list"]',
            'div[role="row"]',
            '[data-testid="pane-side"]'
        ]
        
        qr_selectors = [
            'canvas[aria-label="Scan me!"]',
            'canvas[aria-label="QR code"]',
            'div[data-testid="qr-container"] canvas',
            '.landing-wrapper canvas'
        ]
        
        while asyncio.get_event_loop().time() - start_time < timeout:
            try:
                current_time = asyncio.get_event_loop().time()
                elapsed = int(current_time - start_time)
                
                # Check if already logged in
                for selector in login_indicators:
                    element = await self.page.query_selector(selector)
                    if element:
                        is_visible = await element.is_visible()
                        if is_visible:
                            print(f"✅ Already logged in! (Found: {selector})")
                            return True
                
                # Check for QR code
                if not qr_shown:
                    for selector in qr_selectors:
                        try:
                            qr = await self.page.query_selector(selector)
                            if qr:
                                is_visible = await qr.is_visible()
                                if is_visible:
                                    print("📱 QR CODE FOUND! Scan with your phone")
                                    qr_shown = True
                                    break
                        except:
                            continue
                
                # Show progress every 30 seconds
                if elapsed % progress_interval == 0 and elapsed > 0:
                    remaining = timeout - elapsed
                    if not qr_shown:
                        print(f"⏳ Waiting for QR... ({elapsed}s elapsed, {remaining}s remaining)")
                        if elapsed > 60:
                            print("   💡 Make sure WhatsApp is open on your phone")
                    else:
                        print(f"⏳ Waiting for scan... ({elapsed}s elapsed, {remaining}s remaining)")
                
                # Refresh after 4 minutes (240 seconds) if no QR and not logged in
                if not qr_shown and elapsed >= QR_REFRESH_DELAY:
                    if current_time - last_refresh >= QR_REFRESH_DELAY:
                        print(f"🔄 No QR detected after {QR_REFRESH_DELAY}s, refreshing page...")
                        await self.page.reload()
                        await asyncio.sleep(3)
                        last_refresh = current_time
                        qr_shown = False  # Reset QR detection after refresh
                
                # Check for errors
                try:
                    error = await self.page.query_selector('div[data-testid="error-message"]')
                    if error:
                        error_text = await error.inner_text()
                        print(f"⚠️ WhatsApp error: {error_text}")
                        if "reload" in error_text.lower() or "refresh" in error_text.lower():
                            print("🔄 Reloading due to error...")
                            await self.page.reload()
                            await asyncio.sleep(3)
                            last_refresh = current_time
                except:
                    pass
                
                await asyncio.sleep(2)
                
            except Exception as e:
                print(f"⚠️ Login check error: {e}")
                await asyncio.sleep(2)
        
        print(f"❌ Login timeout after {timeout}s")
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
        self.media_blocked = False
    
    async def shutdown(self):
        """Shutdown login manager"""
        print("🔄 Shutting down...")
        await self.cleanup()
        print("👋 Goodbye!")