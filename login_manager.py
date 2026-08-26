"""
Login Manager
=============
Handles all WhatsApp Web login and session management:
- Session checking and validation
- QR code display with retry logic
- FRESH SESSION EACH TIME (no saved state to corrupt)
- Browser launch with anti-detection
- 5 retry attempts with 1 minute between retries
- 4 minute wait before page refresh
- CONNECTION MONITORING: Multi-layer connection detection
  - Uses multiple indicators (logo, search, title, body)
  - Requires 3 consecutive failures before disconnecting
  - Deep verification before declaring disconnection
"""

import json
import asyncio
import shutil
from pathlib import Path
from playwright.async_api import async_playwright

# ============================================================
# CONFIGURATION
# ============================================================

BASE_DIR = Path(__file__).parent
SESSION_DIR = BASE_DIR / "whatsapp_session"
SESSION_FILE = BASE_DIR / "whatsapp_session.json"
WHATSAPP_WEB_URL = "https://web.whatsapp.com"
MAX_LOGIN_ATTEMPTS = 5
RETRY_DELAY = 60  # 1 minute between retries
QR_REFRESH_DELAY = 360  # 4 minutes before refresh

# ============================================================
# CONNECTION MONITORING CONFIGURATION
# ============================================================

CONNECTION_CHECK_INTERVAL = 5  # Check every 5 seconds
MAX_RECONNECT_ATTEMPTS = 3     # Number of reconnect attempts
RECONNECT_DELAY = 10           # Seconds between reconnect attempts
CONSECUTIVE_FAILURES_THRESHOLD = 3  # Must fail 3 times before declaring disconnected

# Create session directory
SESSION_DIR.mkdir(exist_ok=True)

# ============================================================
# LOGIN MANAGER CLASS
# ============================================================

class LoginManager:
    """Manages WhatsApp Web login and session"""
    
    def __init__(self, use_saved_session: bool = False):
        """
        Initialize LoginManager
        
        Args:
            use_saved_session: If True, try to use saved session (NOT RECOMMENDED)
                              If False (default), always start fresh
        """
        self.browser = None
        self.context = None
        self.page = None
        self.playwright = None
        self.is_logged_in = False
        self.is_connected = False
        self.qr_shown_after_valid_session = False
        self.use_saved_session = use_saved_session
        self.monitor_task = None
        self._consecutive_failures = 0  # Track consecutive failures
    
    # ============================================================
    # SESSION MANAGEMENT
    # ============================================================
    
    async def check_session(self) -> bool:
        """Check if session exists and is valid - ONLY if using saved sessions"""
        if not self.use_saved_session:
            print("📱 Fresh session mode - always scan QR")
            return False
            
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
        
        if self.use_saved_session:
            has_session = await self.check_session()
            if has_session:
                print("✅ Valid session - auto-login will occur")
            else:
                print("📱 No valid session - QR code will be shown")
        else:
            print("📱 FRESH SESSION MODE - QR code will be shown each time")
            print("   This is more reliable for group messaging!")
        
        print("   Open WhatsApp on your phone")
        print("   Tap ⋮ → Linked Devices → Link a Device")
        print("   Scan the QR code in the browser")
        print(f"   ⏳ Will wait up to {QR_REFRESH_DELAY}s before refreshing")
        print("=" * 60 + "\n")
        return False
    
    # ============================================================
    # BROWSER LAUNCH
    # ============================================================
    
    async def launch_browser(self):
        """Launch browser with FRESH context (no saved state)"""
        try:
            self.playwright = await async_playwright().start()
            
            if not self.use_saved_session:
                print("🚀 Launching fresh browser (no saved session)")
                
                if SESSION_FILE.exists():
                    try:
                        SESSION_FILE.unlink()
                        print(f"   🗑️ Removed old session file: {SESSION_FILE}")
                    except:
                        pass
                
                self.browser = await self.playwright.chromium.launch(
                    headless=False,
                    args=[
                        '--disable-blink-features=AutomationControlled',
                        '--disable-dev-shm-usage',
                        '--no-sandbox',
                        '--disable-setuid-sandbox',
                        '--disable-features=PreloadMediaEngagementData',
                        '--disable-features=AutomaticTabDiscarding',
                        '--disable-background-timer-throttling',
                        '--disable-backgrounding-occluded-windows',
                        '--disable-renderer-backgrounding',
                    ]
                )
                
                self.context = await self.browser.new_context(
                    user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                    viewport={'width': 1280, 'height': 720},
                )
                
                self.page = await self.context.new_page()
                
                await self.page.add_init_script("""
                    Object.defineProperty(navigator, 'webdriver', {
                        get: () => undefined
                    });
                """)
                
                return True
            
            else:
                print("🚀 Launching browser with persistent context (SAVED SESSION)")
                print("   ⚠️ This may cause issues with group messaging!")
                
                self.context = await self.playwright.chromium.launch_persistent_context(
                    user_data_dir="./whatsapp_session",
                    headless=False,
                    args=[
                        '--disable-blink-features=AutomationControlled',
                        '--disable-dev-shm-usage',
                        '--no-sandbox',
                        '--disable-setuid-sandbox',
                        '--disable-features=PreloadMediaEngagementData',
                        '--disable-features=AutomaticTabDiscarding',
                        '--disable-background-timer-throttling',
                        '--disable-backgrounding-occluded-windows',
                        '--disable-renderer-backgrounding',
                    ],
                    user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                    viewport={'width': 1280, 'height': 720}
                )
                
                if self.context.pages:
                    self.page = self.context.pages[0]
                else:
                    self.page = await self.context.new_page()
                
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
    # SESSION SAVING
    # ============================================================
    
    async def save_session_state(self):
        """Save session state - ONLY if using persistent context"""
        if not self.use_saved_session:
            print("💡 Fresh session mode - session not saved")
            return True
            
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
    # LOGIN WITH RETRY
    # ============================================================
    
    async def login(self) -> bool:
        """Complete login process with fresh session"""
        print("=" * 60)
        print("🚀 WhatsApp Bot Login")
        print("=" * 60)
        print(f"📋 Mode: {'FRESH SESSION' if not self.use_saved_session else 'SAVED SESSION'}")
        print(f"📋 Max attempts: {MAX_LOGIN_ATTEMPTS}")
        print(f"⏳ Retry delay: {RETRY_DELAY}s between attempts")
        print(f"🔄 Page refresh: After {QR_REFRESH_DELAY}s if no QR")
        print("=" * 60)
        
        await self.ensure_session()
        self.qr_shown_after_valid_session = False
        
        for attempt in range(MAX_LOGIN_ATTEMPTS):
            attempt_num = attempt + 1
            print(f"\n🔄 Login attempt {attempt_num}/{MAX_LOGIN_ATTEMPTS}")
            
            try:
                if not await self.launch_browser():
                    print(f"❌ Failed to launch browser on attempt {attempt_num}")
                    if attempt_num < MAX_LOGIN_ATTEMPTS:
                        print(f"⏳ Waiting {RETRY_DELAY}s before retry...")
                        await self.cleanup()
                        await asyncio.sleep(RETRY_DELAY)
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
                    self.is_connected = True
                    
                    # Start connection monitor
                    self.monitor_task = asyncio.create_task(self._monitor_connection())
                    print("🔌 Connection monitor started (multi-layer detection)")
                    print("   - Checks logo, search, title, and page responsiveness")
                    print(f"   - Requires {CONSECUTIVE_FAILURES_THRESHOLD} consecutive failures before disconnect")
                    
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
        """Wait for login - show QR if needed"""
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
                
                # Refresh after 4 minutes if no QR
                if not qr_shown and elapsed >= QR_REFRESH_DELAY:
                    if current_time - last_refresh >= QR_REFRESH_DELAY:
                        print(f"🔄 No QR detected after {QR_REFRESH_DELAY}s, refreshing page...")
                        await self.page.reload()
                        await asyncio.sleep(3)
                        last_refresh = current_time
                        qr_shown = False
                
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
    # CONNECTION MONITOR - MULTI-LAYER DETECTION
    # ============================================================
    
    async def _monitor_connection(self):
        """
        Continuously monitor WhatsApp connection status using MULTIPLE indicators.
        Uses a tiered approach - checks multiple elements before declaring disconnection.
        """
        print("🔌 Connection monitor active (multi-layer detection)")
        
        while True:
            try:
                await asyncio.sleep(CONNECTION_CHECK_INTERVAL)
                
                # Check if page exists
                if not self.page:
                    print("⚠️ Page missing - connection lost")
                    self.is_connected = False
                    await self._handle_disconnection()
                    self._consecutive_failures = 0
                    continue
                
                # ============================================================
                # TIER 1: Quick checks (most reliable)
                # ============================================================
                is_connected = await self._quick_connection_check()
                
                if is_connected:
                    if self._consecutive_failures > 0:
                        print(f"✅ Connection stable (recovered from {self._consecutive_failures} failures)")
                    self._consecutive_failures = 0
                    if not self.is_connected:
                        self.is_connected = True
                        print("✅ WhatsApp reconnected!")
                    continue
                
                # If quick check fails, increment failures
                self._consecutive_failures += 1
                
                # Only log every few failures to avoid spam
                if self._consecutive_failures < CONSECUTIVE_FAILURES_THRESHOLD:
                    print(f"⚠️ Quick check failed ({self._consecutive_failures}/{CONSECUTIVE_FAILURES_THRESHOLD})")
                
                # ============================================================
                # TIER 2: Deep check if quick check failed multiple times
                # ============================================================
                if self._consecutive_failures >= CONSECUTIVE_FAILURES_THRESHOLD:
                    print("⚠️ Multiple connection checks failed - verifying...")
                    is_actually_connected = await self._deep_connection_check()
                    
                    if is_actually_connected:
                        print("✅ Connection confirmed (deep check passed)")
                        self._consecutive_failures = 0
                        if not self.is_connected:
                            self.is_connected = True
                            print("✅ WhatsApp reconnected!")
                        continue
                    else:
                        # Confirmed disconnection
                        print("⚠️ WhatsApp disconnected! (confirmed by deep check)")
                        self.is_connected = False
                        await self._handle_disconnection()
                        self._consecutive_failures = 0
                
            except Exception as e:
                print(f"⚠️ Connection check error: {e}")
                self._consecutive_failures += 1
                
                if self._consecutive_failures >= CONSECUTIVE_FAILURES_THRESHOLD:
                    self.is_connected = False
                    await self._handle_disconnection()
                    self._consecutive_failures = 0
    
    async def _quick_connection_check(self) -> bool:
        """
        Quick connection check using multiple reliable indicators.
        Returns True if ANY indicator is found.
        """
        try:
            # ============================================================
            # INDICATOR 1: Check page title (fastest)
            # ============================================================
            try:
                page_title = await self.page.title()
                if page_title and "WhatsApp" in page_title:
                    return True
            except:
                pass
            
            # ============================================================
            # INDICATOR 2: Check for WhatsApp logo/icon (always present)
            # ============================================================
            logo_selectors = [
                '[aria-label="WhatsApp"]',
                'div[data-testid="app"]',
                '.landing-wrapper',
                'div[data-testid="landing-window"]',
                'img[alt="WhatsApp"]'
            ]
            
            for selector in logo_selectors:
                try:
                    element = await self.page.query_selector(selector)
                    if element:
                        is_visible = await element.is_visible()
                        if is_visible:
                            return True
                except:
                    continue
            
            # ============================================================
            # INDICATOR 3: Check for search box (appears early)
            # ============================================================
            search_selectors = [
                'div[data-testid="chat-list-search"]',
                'input[type="text"]',
                'div[role="textbox"]',
                'button[aria-label="Search"]'
            ]
            
            for selector in search_selectors:
                try:
                    element = await self.page.query_selector(selector)
                    if element:
                        is_visible = await element.is_visible()
                        if is_visible:
                            return True
                except:
                    continue
            
            # ============================================================
            # INDICATOR 4: Check for chat list (if loaded)
            # ============================================================
            try:
                chat_list = await self.page.query_selector('div[data-testid="chat-list"]')
                if chat_list:
                    is_visible = await chat_list.is_visible()
                    if is_visible:
                        return True
            except:
                pass
            
            # ============================================================
            # INDICATOR 5: Check for any content on the page
            # ============================================================
            try:
                body = await self.page.query_selector('body')
                if body:
                    inner_html = await body.inner_html()
                    if inner_html and len(inner_html) > 100:
                        return True
            except:
                pass
            
            return False
            
        except Exception as e:
            return False
    
    async def _deep_connection_check(self) -> bool:
        """
        Deep connection check - tries to interact with the page.
        Returns True if the page is responsive.
        """
        try:
            # ============================================================
            # METHOD 1: Try to execute JavaScript on the page
            # ============================================================
            try:
                result = await self.page.evaluate('''
                    () => {
                        // Check if the page is responsive
                        const body = document.body;
                        if (!body) return false;
                        
                        // Check if we can access WhatsApp's global objects
                        if (window.Store || window.WWebJS || window.WebSocket) {
                            return true;
                        }
                        
                        // Check if we can find any WhatsApp-specific elements
                        const hasWhatsApp = document.querySelector('[aria-label="WhatsApp"]') ||
                                          document.querySelector('div[data-testid="app"]') ||
                                          document.querySelector('.landing-wrapper');
                        
                        return !!hasWhatsApp;
                    }
                ''')
                if result:
                    return True
            except:
                pass
            
            # ============================================================
            # METHOD 2: Try to find any interactive element
            # ============================================================
            interactive_selectors = [
                'button',
                'input',
                'div[role="button"]',
                'div[role="textbox"]',
                'a'
            ]
            
            for selector in interactive_selectors:
                try:
                    elements = await self.page.query_selector_all(selector)
                    if elements and len(elements) > 0:
                        # Check if at least one is visible
                        for element in elements[:5]:  # Check first 5
                            try:
                                if await element.is_visible():
                                    return True
                            except:
                                continue
                except:
                    continue
            
            # ============================================================
            # METHOD 3: Check if page is still loading (not crashed)
            # ============================================================
            try:
                # Check for loading indicators
                loading_selectors = [
                    'div[data-testid="loading"]',
                    '.loader',
                    '.loading',
                    '[aria-label="Loading"]'
                ]
                
                for selector in loading_selectors:
                    try:
                        element = await self.page.query_selector(selector)
                        if element and await element.is_visible():
                            # Still loading - but this means the page is alive!
                            return True
                    except:
                        continue
            except:
                pass
            
            # ============================================================
            # METHOD 4: Check if page title is accessible
            # ============================================================
            try:
                title = await self.page.title()
                if title and len(title) > 0:
                    return True
            except:
                pass
            
            # ============================================================
            # METHOD 5: Check if we can reload the page (last resort)
            # ============================================================
            try:
                # Try a simple JavaScript call
                await self.page.evaluate('document.readyState')
                return True
            except:
                pass
            
            return False
            
        except Exception as e:
            print(f"⚠️ Deep connection check failed: {e}")
            return False
    
    # ============================================================
    # EXTERNAL CONNECTION METHODS
    # ============================================================
    
    async def check_connection(self) -> bool:
        """
        Quick one-time connection check for external callers.
        Returns True if connected, False if not.
        """
        is_connected = await self._quick_connection_check()
        self.is_connected = is_connected
        return is_connected
    
    async def wait_for_connection(self, timeout: int = 60) -> bool:
        """
        Wait for WhatsApp to be connected.
        Returns True if connected, False if timeout.
        """
        print(f"⏳ Waiting for WhatsApp to connect... (timeout: {timeout}s)")
        
        start_time = asyncio.get_event_loop().time()
        while asyncio.get_event_loop().time() - start_time < timeout:
            is_connected = await self._quick_connection_check()
            if is_connected:
                self.is_connected = True
                print("✅ Connected!")
                return True
            
            # Show progress every 10 seconds
            elapsed = int(asyncio.get_event_loop().time() - start_time)
            if elapsed % 10 == 0 and elapsed > 0:
                print(f"⏳ Still waiting... ({elapsed}s)")
            
            await asyncio.sleep(2)
        
        print(f"❌ Connection timeout after {timeout}s")
        return False
    
    async def ensure_connection(self) -> bool:
        """
        Ensure connection is active. If not, wait for it.
        Returns True if connected, False if failed.
        """
        if self.is_connected:
            return True
        
        print("⏳ Waiting for WhatsApp to reconnect...")
        return await self.wait_for_connection()
    
    # ============================================================
    # HANDLE DISCONNECTION
    # ============================================================
    
    async def _handle_disconnection(self):
        """
        Handle disconnection with retry logic.
        Uses the same multi-layer checks.
        """
        print(f"🔄 Attempting to reconnect...")
        
        for attempt in range(MAX_RECONNECT_ATTEMPTS):
            try:
                # First check if page is alive
                if self.page:
                    # Try to get title - if this works, page is alive
                    try:
                        title = await self.page.title()
                        if title and "WhatsApp" in title:
                            print("✅ Page is alive, checking connection...")
                            # Try reloading the page
                            await self.page.reload()
                            await asyncio.sleep(5)
                            
                            # Check connection with deep check
                            if await self._deep_connection_check():
                                self.is_connected = True
                                self._consecutive_failures = 0
                                print("✅ Successfully reconnected!")
                                return
                    except:
                        pass
                
                # If reload fails, try re-login
                if attempt == MAX_RECONNECT_ATTEMPTS - 1:
                    print("🔄 Attempting full re-login...")
                    await self._re_login()
                    return
                    
            except Exception as e:
                print(f"⚠️ Reconnect attempt {attempt + 1} failed: {e}")
            
            await asyncio.sleep(RECONNECT_DELAY)
        
        print("❌ Failed to reconnect after multiple attempts.")
    
    async def _re_login(self):
        """Full re-login process"""
        try:
            # Close old page and create new one
            if self.page:
                await self.page.close()
            
            self.page = await self.context.new_page()
            
            # Re-apply stealth scripts
            await self.page.add_init_script("""
                Object.defineProperty(navigator, 'webdriver', {
                    get: () => undefined
                });
                Object.defineProperty(navigator, 'plugins', {
                    get: () => [1, 2, 3, 4, 5]
                });
                window.chrome = { runtime: {} };
            """)
            
            await self.page.goto(WHATSAPP_WEB_URL)
            print("📱 Please scan the QR code to re-login...")
            
            # Wait for login using multi-layer check
            for _ in range(60):  # 60 seconds timeout
                if await self._quick_connection_check():
                    self.is_connected = True
                    self._consecutive_failures = 0
                    print("✅ Re-login successful!")
                    return
                await asyncio.sleep(1)
            
            print("❌ Re-login timed out")
            
        except Exception as e:
            print(f"❌ Re-login failed: {e}")
    
    # ============================================================
    # CLEANUP
    # ============================================================
    
    async def cleanup(self):
        """Clean up browser resources"""
        try:
            # Cancel monitor task
            if self.monitor_task:
                self.monitor_task.cancel()
                try:
                    await self.monitor_task
                except:
                    pass
                self.monitor_task = None
            
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
        self.is_connected = False
        self._consecutive_failures = 0
    
    async def shutdown(self):
        """Shutdown login manager"""
        print("🔄 Shutting down...")
        await self.cleanup()
        print("👋 Goodbye!")