"""
Login Manager - STRICT CONNECTION MONITORING WITH SMART POPUP HANDLING
========================================================================
Handles all WhatsApp Web login and session management with comprehensive popup handling:
- Session checking and validation
- QR code display with retry logic
- FRESH SESSION EACH TIME (no saved state to corrupt)
- Browser launch with anti-detection
- STRICT CONNECTION MONITORING
- COMPREHENSIVE POPUP HANDLING:
  - Auto-cancels dangerous popups (leave group, dismiss admin)
  - Auto-dismisses safe popups (rate limits, notifications)
  - WAITS FOR and clicks CONTINUE on welcome/onboarding popups
  - Handles "What's New" popups
  - Handles "Update Available" popups
  - HANDLES "We encountered a problem" popup (clicks Reload)
  - HANDLES "Memory full" popup (clicks Logout, waits for re-login)
  - Always prioritizes Continue/OK for welcome flows
"""

import json
import asyncio
import shutil
from pathlib import Path
from playwright.async_api import async_playwright
from datetime import datetime

# ============================================================
# CONFIGURATION
# ============================================================

BASE_DIR = Path(__file__).parent
SESSION_DIR = BASE_DIR / "whatsapp_session"
SESSION_FILE = BASE_DIR / "whatsapp_session.json"
WHATSAPP_WEB_URL = "https://web.whatsapp.com"
MAX_LOGIN_ATTEMPTS = 5
RETRY_DELAY = 60
QR_REFRESH_DELAY = 360

# ============================================================
# STRICT CONNECTION MONITORING CONFIG
# ============================================================

CONNECTION_CHECK_INTERVAL = 3
MAX_RECONNECT_ATTEMPTS = 5
RECONNECT_DELAY = 5
CONSECUTIVE_FAILURES_THRESHOLD = 1

SESSION_DIR.mkdir(exist_ok=True)

# ============================================================
# DISCONNECTION INDICATORS
# ============================================================

DISCONNECT_SELECTORS = [
    'div[data-testid="qr-container"]',
    'canvas[aria-label="Scan me!"]',
    'div[data-testid="landing-window"]',
    '.landing-wrapper',
    'div[data-testid="phone-not-connected"]',
    'div[aria-label="Phone not connected"]',
    'div[data-testid="qr-plain"]',
    'div[data-testid="qr-container"] canvas',
    'div[data-testid="app"] .landing-wrapper',
]

CONNECTED_SELECTORS = [
    'div[data-testid="chat-list"]',
    'div[data-testid="pane-side"]',
    'div[role="row"]',
    'div[data-testid="message-container"]',
]

# ============================================================
# WELCOME/ONBOARDING POPUP SELECTORS
# ============================================================

WELCOME_POPUP_SELECTORS = [
    # Welcome/Onboarding popups
    'div[role="dialog"]:has-text("Welcome")',
    'div[role="dialog"]:has-text("welcome")',
    'div[role="dialog"]:has-text("What\'s new")',
    'div[role="dialog"]:has-text("what\'s new")',
    'div[role="dialog"]:has-text("New features")',
    'div[role="dialog"]:has-text("new features")',
    'div[role="dialog"]:has-text("Get started")',
    'div[role="dialog"]:has-text("get started")',
    'div[data-testid="modal"]:has-text("Welcome")',
    'div[data-testid="modal"]:has-text("What\'s new")',
    'div[data-testid="modal"]:has-text("New features")',
    'div[data-testid="modal"]:has-text("Get started")',
    'div[class*="welcome"]',
    'div[class*="onboarding"]',
    'div[class*="tour"]',
    'div[class*="intro"]',
    
    # Generic "Continue" popups (welcome flow)
    'div[role="dialog"]:has-text("Continue")',
    'div[data-testid="modal"]:has-text("Continue")',
    '.popup:has-text("Continue")',
    '.modal:has-text("Continue")',
]

WELCOME_CONTINUE_BUTTONS = [
    'button:has-text("Continue")',
    'button:has-text("continue")',
    'button:has-text("Get started")',
    'button:has-text("get started")',
    'button:has-text("Next")',
    'button:has-text("next")',
    'button:has-text("Got it")',
    'button:has-text("got it")',
    'button:has-text("OK")',
    'button:has-text("ok")',
    'button:has-text("Start")',
    'button:has-text("start")',
]

# ============================================================
# ERROR POPUP SELECTORS
# ============================================================

# "We encountered a problem running WhatsApp" popup
PROBLEM_POPUP_SELECTORS = [
    'div:has-text("We encountered a problem")',
    'div:has-text("encountered a problem running")',
    'div:has-text("problem running WhatsApp")',
    'div[role="dialog"]:has-text("encountered a problem")',
    'div[data-testid="modal"]:has-text("encountered a problem")',
    'div:has-text("Something went wrong")',
    'div:has-text("Please reload")',
]

RELOAD_BUTTONS = [
    'button:has-text("Reload")',
    'button:has-text("reload")',
    'button:has-text("Refresh")',
    'button:has-text("refresh")',
    'button[data-testid="reload-button"]',
]

# "Memory full" popup - Computer does not have enough space
MEMORY_FULL_SELECTORS = [
    'div:has-text("Memory full")',
    'div:has-text("memory full")',
    'div:has-text("Storage full")',
    'div:has-text("storage full")',
    'div:has-text("No storage space")',
    'div:has-text("not enough memory")',
    'div:has-text("clear storage")',
    'div:has-text("does not have enough space")',
    'div:has-text("not have enough space")',
    'div:has-text("computer does not have enough")',
    'div[role="dialog"]:has-text("Memory full")',
    'div[data-testid="modal"]:has-text("Memory full")',
]

# OK button for memory full popup (click to dismiss, then pause)
OK_BUTTONS = [
    'button:has-text("OK")',
    'button:has-text("ok")',
    'button:has-text("Ok")',
    'button[data-testid="ok-button"]',
]

# ============================================================
# POPUP DETECTION - ALL POPUPS
# ============================================================

POPUP_SELECTORS = [
    # Generic modals/dialogs
    'div[role="dialog"]',
    'div[role="alert"]',
    'div[data-testid="modal"]',
    'div[data-testid="modal-container"]',
    'div[data-testid="popup"]',
    'div[data-testid="alert"]',
    '.modal',
    '.overlay',
    '.popup',
    '.dialog',
    'div[class*="modal"]',
    'div[class*="overlay"]',
    'div[class*="popup"]',
    'div[class*="dialog"]',
    
    # WhatsApp specific
    'div[data-testid="modal-container"]:visible',
    'div[data-testid="popup"]:visible',
    'div[data-testid="alert"]:visible',
    '.popup-container:visible',
    '.modal-container:visible',
    
    # Rate limit / errors
    'div[data-testid="rate-limit-notification"]',
    'div[data-testid="error-notification"]',
    
    # Permission popups
    'div[data-testid="permission-popup"]',
    'div:has-text("Allow notifications")',
    'div:has-text("Enable notifications")',
    'div:has-text("Grant permission")',
    
    # Connection status
    'div[data-testid="connection-status"]',
    
    # Update/notification
    'div[data-testid="update-popup"]',
    'div[data-testid="notification"]',
]

# ============================================================
# SAFE CANCEL BUTTONS (Priority Order)
# ============================================================

SAFE_CANCEL_BUTTONS = [
    # Cancel buttons (highest priority)
    'button:has-text("Cancel")',
    'button:has-text("cancel")',
    'button[data-testid="cancel-button"]',
    'div[role="button"]:has-text("Cancel")',
    
    # Close buttons
    'button[aria-label="Close"]',
    'button[aria-label="close"]',
    'button[data-testid="close-button"]',
    'button[class*="close"]',
    'div[role="button"][aria-label="Close"]',
    'div[data-testid="close-button"]',
    
    # Dismiss buttons
    'button:has-text("Dismiss")',
    'button:has-text("dismiss")',
    'button[data-testid="dismiss-button"]',
    'button[class*="dismiss"]',
    'div[role="button"]:has-text("Dismiss")',
    'div[data-testid="dismiss-button"]',
    
    # Not now / Later
    'button:has-text("Not now")',
    'button:has-text("not now")',
    'button:has-text("Later")',
    'button:has-text("later")',
    'button:has-text("Skip")',
    'button:has-text("skip")',
]

# ============================================================
# DANGEROUS BUTTONS - NEVER CLICK
# ============================================================

DANGEROUS_BUTTONS = [
    'button:has-text("Leave Group")',
    'button:has-text("Leave")',
    'button:has-text("Leave Community")',
    'button:has-text("Dismiss")',
    'button:has-text("Dismiss Admin")',
    'button:has-text("Remove")',
    'button:has-text("Delete Group")',
    'button:has-text("Delete")',
    'button:has-text("Confirm")',
    'button:has-text("Yes")',
    'button:has-text("Proceed")',
    'button:has-text("Accept")',
]

DANGEROUS_TEXT_PATTERNS = [
    'leave group',
    'leave this group',
    'leave community',
    'leave this community',
    'dismiss as admin',
    'remove as admin',
    'dismiss admin',
    'remove admin',
    'delete group',
    'delete this group',
    'are you sure you want to leave',
    'are you sure you want to dismiss',
    'you will no longer be able to send messages',
    'you will lose admin rights',
    'remove from group',
]


class LoginManager:
    """Manages WhatsApp Web login with STRICT connection monitoring and comprehensive popup handling"""
    
    def __init__(self, use_saved_session: bool = False):
        self.browser = None
        self.context = None
        self.page = None
        self.playwright = None
        self.is_logged_in = False
        self.is_connected = False
        self.qr_shown_after_valid_session = False
        self.use_saved_session = use_saved_session
        self.monitor_task = None
        self._consecutive_failures = 0
        self._disconnect_callbacks = []
        self._reconnect_callbacks = []
        
        # Connection state tracking
        self._last_known_connected = False
        self._disconnect_time = None
        self._reconnect_time = None
        
        # Popup tracking
        self._popups_handled = 0
        self._last_popup_time = None
        self._dangerous_popups_cancelled = 0
        self._welcome_popups_handled = 0
        
        # Welcome popup state
        self._welcome_popup_handled = False
        self._waiting_for_welcome_popup = False
        self._welcome_popup_checked = False  # Track if we've already checked for welcome popup
        
        # Error popup tracking
        self._problem_popup_handled = False
        self._memory_full_handled = False
        self._is_logging_out = False  # Prevent multiple logout attempts
    
    def on_disconnect(self, callback):
        """Register a callback to be called when disconnected"""
        self._disconnect_callbacks.append(callback)
    
    def on_reconnect(self, callback):
        """Register a callback to be called when reconnected"""
        self._reconnect_callbacks.append(callback)
    
    # ============================================================
    # SESSION MANAGEMENT
    # ============================================================
    
    async def check_session(self) -> bool:
        """Check if session exists and is valid"""
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
        self._welcome_popup_handled = False
        self._welcome_popup_checked = False  # Reset welcome check flag
        
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
                    
                    # Wait for and handle welcome popup (ONLY ONCE)
                    print("\n🔍 Checking for welcome/onboarding popup...")
                    welcome_handled = await self._handle_welcome_popup()
                    if welcome_handled:
                        print("✅ Welcome popup handled (clicked Continue)")
                    else:
                        print("ℹ️ No welcome popup detected")
                    
                    # Mark as checked so we don't check again
                    self._welcome_popup_checked = True
                    
                    await self.save_session_state()
                    self.is_logged_in = True
                    self.is_connected = True
                    self._last_known_connected = True
                    
                    # Start STRICT connection monitor with comprehensive popup handling
                    self.monitor_task = asyncio.create_task(self._monitor_connection())
                    print("\n🔌 STRICT Connection monitor started:")
                    print("   - Detects QR codes (disconnected)")
                    print("   - Detects 'Phone not connected' errors")
                    print("   - Detects landing/scan pages")
                    print("   - COMPREHENSIVE POPUP HANDLING:")
                    print("     ✅ Waits for and clicks Continue on welcome popups")
                    print("     ✅ Auto-cancels dangerous popups (leave group, dismiss admin)")
                    print("     ✅ Auto-dismisses safe popups (rate limits, notifications)")
                    print("     ✅ Handles 'Problem running' popup (clicks Reload)")
                    print("     ✅ Handles 'Memory full' popup (clicks Logout, waits for re-login)")
                    print("     ✅ Always clicks Cancel/Close/Dismiss")
                    print("     ❌ Never clicks Leave/Delete/Confirm")
                    print(f"   - Triggers after {CONSECUTIVE_FAILURES_THRESHOLD} failure(s)")
                    print(f"   - Checks every {CONNECTION_CHECK_INTERVAL}s")
                    
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
        
        start_time = datetime.now()
        last_refresh = start_time
        qr_shown = False
        progress_interval = 30
        
        login_indicators = [
            'div[data-testid="chat-list"]',
            'div[role="row"]',
            'div[data-testid="pane-side"]'
        ]
        
        while (datetime.now() - start_time).seconds < timeout:
            try:
                current_time = datetime.now()
                elapsed = int((current_time - start_time).seconds)
                
                # Handle error popups during login
                await self._handle_error_popups()
                
                # Cancel any popups that appear (except welcome popups)
                await self._cancel_popups(handle_welcome=False)
                
                # Check login
                for selector in login_indicators:
                    element = await self.page.query_selector(selector)
                    if element:
                        is_visible = await element.is_visible()
                        if is_visible:
                            print(f"✅ Already logged in! (Found: {selector})")
                            return True
                
                # Check QR
                qr_selectors = [
                    'canvas[aria-label="Scan me!"]',
                    'canvas[aria-label="QR code"]',
                    'div[data-testid="qr-container"] canvas',
                    '.landing-wrapper canvas',
                    'div[data-testid="qr-plain"]'
                ]
                
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
                
                # Progress
                if elapsed % progress_interval == 0 and elapsed > 0:
                    remaining = timeout - elapsed
                    if not qr_shown:
                        print(f"⏳ Waiting for QR... ({elapsed}s elapsed, {remaining}s remaining)")
                        if elapsed > 60:
                            print("   💡 Make sure WhatsApp is open on your phone")
                    else:
                        print(f"⏳ Waiting for scan... ({elapsed}s elapsed, {remaining}s remaining)")
                
                # Refresh
                if not qr_shown and elapsed >= QR_REFRESH_DELAY:
                    if (current_time - last_refresh).seconds >= QR_REFRESH_DELAY:
                        print(f"🔄 No QR detected after {QR_REFRESH_DELAY}s, refreshing page...")
                        await self.page.reload()
                        await asyncio.sleep(3)
                        last_refresh = current_time
                        qr_shown = False
                
                # Check errors
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
    # ERROR POPUP HANDLING
    # ============================================================
    
    async def _handle_error_popups(self) -> bool:
        """
        Handle error popups like "We encountered a problem" and "Memory full".
        Returns True if a popup was handled.
        """
        handled = False
        
        try:
            # ============================================================
            # CHECK FOR "We encountered a problem" POPUP
            # ============================================================
            for selector in PROBLEM_POPUP_SELECTORS:
                try:
                    element = await self.page.query_selector(selector)
                    if element and await element.is_visible():
                        print("\n⚠️ 'We encountered a problem' popup detected!")
                        print("   🔄 Trying to reload...")
                        
                        # Try to find and click Reload button
                        reload_clicked = False
                        for button_selector in RELOAD_BUTTONS:
                            try:
                                button = await self.page.query_selector(button_selector)
                                if button and await button.is_visible() and await button.is_enabled():
                                    await button.click()
                                    print("   ✅ Clicked Reload button")
                                    reload_clicked = True
                                    handled = True
                                    self._problem_popup_handled = True
                                    await asyncio.sleep(3)  # Wait for reload
                                    break
                            except:
                                continue
                        
                        if not reload_clicked:
                            # Try to find any button with text containing "Reload" or "Refresh"
                            buttons = await self.page.query_selector_all('button, [role="button"]')
                            for button in buttons:
                                try:
                                    text = await button.inner_text()
                                    if any(word in text.lower() for word in ['reload', 'refresh']):
                                        if await button.is_visible() and await button.is_enabled():
                                            await button.click()
                                            print(f"   ✅ Clicked '{text}' button")
                                            reload_clicked = True
                                            handled = True
                                            self._problem_popup_handled = True
                                            await asyncio.sleep(3)
                                            break
                                except:
                                    continue
                        
                        # ============================================================
                        # FALLBACK: If no Reload button found, REFRESH THE BROWSER
                        # ============================================================
                        if not reload_clicked:
                            print("   ⚠️ Could not find Reload button, refreshing browser page...")
                            try:
                                await self.page.reload()
                                print("   ✅ Browser page refreshed")
                                handled = True
                                self._problem_popup_handled = True
                                await asyncio.sleep(5)  # Wait for page to reload
                            except Exception as e:
                                print(f"   ⚠️ Could not refresh page: {e}")
                                # Last resort: press Escape to dismiss
                                print("   ⏳ Pressing Escape as last resort...")
                                await self.page.keyboard.press('Escape')
                                handled = True
                        
                        # After reload or refresh, wait for WhatsApp to stabilize
                        print("   ⏳ Waiting for WhatsApp to stabilize...")
                        await asyncio.sleep(3)
                        
                        return handled
                except:
                    continue
            
            # ============================================================
            # CHECK FOR "Memory full" POPUP (Computer doesn't have enough space)
            # ============================================================
            for selector in MEMORY_FULL_SELECTORS:
                try:
                    element = await self.page.query_selector(selector)
                    if element and await element.is_visible():
                        print("\n🔴 'Memory full' popup detected!")
                        print("   💻 Computer does not have enough space.")
                        
                        if self._is_logging_out:
                            print("   ⏳ Already handling memory issue, waiting...")
                            return True
                        
                        self._is_logging_out = True
                        
                        # ============================================================
                        # STEP 1: Try to find and click OK button (dismiss the popup)
                        # ============================================================
                        ok_clicked = False
                        for button_selector in OK_BUTTONS:
                            try:
                                button = await self.page.query_selector(button_selector)
                                if button and await button.is_visible() and await button.is_enabled():
                                    await button.click()
                                    print("   ✅ Clicked OK button (dismissed popup)")
                                    ok_clicked = True
                                    handled = True
                                    self._memory_full_handled = True
                                    break
                            except:
                                continue
                        
                        if not ok_clicked:
                            # Try to find any button with text containing "OK"
                            buttons = await self.page.query_selector_all('button, [role="button"]')
                            for button in buttons:
                                try:
                                    text = await button.inner_text()
                                    if text and text.strip().upper() in ['OK', 'OKAY', 'CLOSE']:
                                        if await button.is_visible() and await button.is_enabled():
                                            await button.click()
                                            print(f"   ✅ Clicked '{text}' button")
                                            ok_clicked = True
                                            handled = True
                                            self._memory_full_handled = True
                                            break
                                except:
                                    continue
                        
                        # ============================================================
                        # STEP 2: If OK button not found, REFRESH THE BROWSER
                        # ============================================================
                        if not ok_clicked:
                            print("   ⚠️ Could not find OK button, refreshing browser page...")
                            try:
                                await self.page.reload()
                                print("   ✅ Browser page refreshed")
                                handled = True
                                self._memory_full_handled = True
                                await asyncio.sleep(5)  # Wait for page to reload
                            except Exception as e:
                                print(f"   ⚠️ Could not refresh page: {e}")
                                # Last resort: press Escape to dismiss
                                print("   ⏳ Pressing Escape as last resort...")
                                await self.page.keyboard.press('Escape')
                                handled = True
                        
                        # ============================================================
                        # STEP 3: PAUSE AND WAIT FOR RE-LOGIN/RECONNECTION
                        # ============================================================
                        print("\n" + "=" * 70)
                        print("🔴 MEMORY FULL / DISK SPACE ERROR")
                        print("=" * 70)
                        print("   The computer does not have enough free disk space.")
                        print("")
                        print("   ⚠️  ACTIONS REQUIRED:")
                        print("   1. Free up disk space on your computer")
                        print("   2. Close unnecessary applications")
                        print("   3. Clear temporary files")
                        print("")
                        print("   ⏳ Bot is PAUSED until disk space is freed.")
                        print("   🔄 After freeing space, the bot will automatically reconnect.")
                        print("=" * 70 + "\n")
                        
                        # Mark as disconnected and set state
                        self.is_connected = False
                        self.is_logged_in = False
                        self._welcome_popup_handled = False
                        self._welcome_popup_checked = False
                        
                        # ============================================================
                        # STEP 4: Wait for reconnection (user frees space, bot reconnects)
                        # ============================================================
                        print("   ⏳ Waiting for WhatsApp to reconnect...")
                        print("   💡 Free up disk space, then the bot will auto-reconnect.")
                        
                        # Wait for connection with longer timeout
                        reconnected = await self.wait_for_connection(timeout=600)  # 10 minutes
                        
                        if reconnected:
                            print("   ✅ Reconnected! Resuming operations...")
                            self._is_logging_out = False
                            return True
                        else:
                            print("   ⚠️ Still disconnected. Please check disk space and restart the bot.")
                            self._is_logging_out = False
                            return handled
                        
                except:
                    continue
            
            return handled
            
        except Exception as e:
            print(f"   ⚠️ Error handling error popups: {e}")
            self._is_logging_out = False
            return handled
    
    async def _wait_for_qr_after_logout(self, timeout: int = 60):
        """Wait for QR code to appear after logout"""
        print("   ⏳ Waiting for QR code to appear...")
        
        start_time = datetime.now()
        
        qr_selectors = [
            'canvas[aria-label="Scan me!"]',
            'canvas[aria-label="QR code"]',
            'div[data-testid="qr-container"] canvas',
            '.landing-wrapper canvas',
            'div[data-testid="qr-plain"]'
        ]
        
        while (datetime.now() - start_time).seconds < timeout:
            try:
                for selector in qr_selectors:
                    try:
                        qr = await self.page.query_selector(selector)
                        if qr and await qr.is_visible():
                            print("   ✅ QR code visible")
                            return True
                    except:
                        continue
                
                # Check if we're on the landing page
                try:
                    landing = await self.page.query_selector('div[data-testid="landing-window"]')
                    if landing and await landing.is_visible():
                        print("   ✅ Landing page visible, QR should appear soon")
                except:
                    pass
                
                await asyncio.sleep(2)
                
            except Exception as e:
                print(f"   ⚠️ Error waiting for QR: {e}")
                await asyncio.sleep(2)
        
        print("   ⚠️ QR code did not appear within timeout")
        return False
    
    # ============================================================
    # WELCOME POPUP HANDLING
    # ============================================================
    
    async def _handle_welcome_popup(self, timeout: int = 30) -> bool:
        """
        Wait for and handle the welcome/onboarding popup.
        Clicks Continue/Get Started/Next when it appears.
        Returns True if welcome popup was handled.
        """
        # If we've already handled or checked for welcome popup, skip
        if self._welcome_popup_handled or self._welcome_popup_checked:
            return self._welcome_popup_handled
        
        print("   👋 Looking for welcome popup...")
        self._waiting_for_welcome_popup = True
        
        start_time = datetime.now()
        
        while (datetime.now() - start_time).seconds < timeout:
            try:
                # Check for welcome popup using selectors
                for selector in WELCOME_POPUP_SELECTORS:
                    try:
                        element = await self.page.query_selector(selector)
                        if element and await element.is_visible():
                            print(f"   🎉 Welcome popup detected! ({selector})")
                            
                            # Try to click Continue or similar button
                            clicked = await self._click_welcome_button(element)
                            
                            if clicked:
                                print("   ✅ Clicked Continue on welcome popup")
                                self._welcome_popup_handled = True
                                self._welcome_popups_handled += 1
                                self._waiting_for_welcome_popup = False
                                self._welcome_popup_checked = True
                                
                                # Wait for popup to close
                                await asyncio.sleep(2)
                                return True
                            else:
                                # Try clicking any visible button in the popup
                                try:
                                    buttons = await element.query_selector_all('button, [role="button"]')
                                    for button in buttons:
                                        if await button.is_visible() and await button.is_enabled():
                                            button_text = await button.inner_text()
                                            if any(
                                                word in button_text.lower() 
                                                for word in ['continue', 'get started', 'next', 'got it', 'ok', 'start']
                                            ):
                                                await button.click()
                                                print(f"   ✅ Clicked '{button_text}' on welcome popup")
                                                self._welcome_popup_handled = True
                                                self._welcome_popups_handled += 1
                                                self._waiting_for_welcome_popup = False
                                                self._welcome_popup_checked = True
                                                await asyncio.sleep(2)
                                                return True
                                except:
                                    pass
                    except:
                        continue
                
                # Check for welcome text in any visible dialog
                try:
                    dialogs = await self.page.query_selector_all('div[role="dialog"], div[data-testid="modal"]')
                    for dialog in dialogs:
                        if await dialog.is_visible():
                            text = await dialog.inner_text()
                            if any(
                                word in text.lower() 
                                for word in ['welcome', "what's new", 'new features', 'get started', 'onboarding']
                            ):
                                print("   🎉 Welcome popup detected by text!")
                                
                                # Try to find and click continue button
                                buttons = await dialog.query_selector_all('button, [role="button"]')
                                for button in buttons:
                                    if await button.is_visible() and await button.is_enabled():
                                        button_text = await button.inner_text()
                                        if any(
                                            word in button_text.lower() 
                                            for word in ['continue', 'get started', 'next', 'got it', 'ok', 'start']
                                        ):
                                            await button.click()
                                            print(f"   ✅ Clicked '{button_text}' on welcome popup")
                                            self._welcome_popup_handled = True
                                            self._welcome_popups_handled += 1
                                            self._waiting_for_welcome_popup = False
                                            self._welcome_popup_checked = True
                                            await asyncio.sleep(2)
                                            return True
                except:
                    pass
                
                await asyncio.sleep(1)
                
            except Exception as e:
                print(f"   ⚠️ Error handling welcome popup: {e}")
                await asyncio.sleep(1)
        
        self._waiting_for_welcome_popup = False
        self._welcome_popup_checked = True  # Mark as checked even if not found
        print("   ℹ️ No welcome popup detected within timeout")
        return False
    
    async def _click_welcome_button(self, popup_element) -> bool:
        """
        Find and click Continue/Get Started button in welcome popup.
        """
        try:
            # Try welcome continue buttons
            for button_selector in WELCOME_CONTINUE_BUTTONS:
                try:
                    button = await popup_element.query_selector(button_selector)
                    if button and await button.is_visible() and await button.is_enabled():
                        await button.click()
                        return True
                except:
                    continue
            
            # Try globally
            for button_selector in WELCOME_CONTINUE_BUTTONS:
                try:
                    button = await self.page.query_selector(button_selector)
                    if button and await button.is_visible() and await button.is_enabled():
                        await button.click()
                        return True
                except:
                    continue
            
            return False
            
        except Exception as e:
            return False
    
    # ============================================================
    # SAFE POPUP CANCELLATION
    # ============================================================
    
    async def _cancel_popups(self, handle_welcome: bool = True) -> int:
        """
        SAFELY cancel ALL popups by clicking Cancel, Close, or Dismiss buttons.
        If handle_welcome is True, handles welcome popups by clicking Continue.
        NEVER clicks dangerous buttons like Leave, Delete, Confirm, etc.
        Returns number of popups cancelled.
        """
        cancelled_count = 0
        
        try:
            # FIRST: Handle error popups (critical - they need specific handling)
            error_handled = await self._handle_error_popups()
            if error_handled:
                cancelled_count += 1
                return cancelled_count
            
            # SECOND: Handle welcome popups if enabled AND not already handled/checked
            if handle_welcome and not self._welcome_popup_handled and not self._welcome_popup_checked:
                # Check if welcome popup is present
                for selector in WELCOME_POPUP_SELECTORS:
                    try:
                        element = await self.page.query_selector(selector)
                        if element and await element.is_visible():
                            print("   🎉 Welcome popup detected - clicking Continue...")
                            clicked = await self._click_welcome_button(element)
                            if clicked:
                                print("   ✅ Clicked Continue on welcome popup")
                                self._welcome_popup_handled = True
                                self._welcome_popups_handled += 1
                                self._welcome_popup_checked = True
                                cancelled_count += 1
                                await asyncio.sleep(1)
                                break
                    except:
                        continue
            
            # THIRD: Check for any popup and cancel it safely
            for selector in POPUP_SELECTORS:
                try:
                    element = await self.page.query_selector(selector)
                    if element and await element.is_visible():
                        # Check if this is a dangerous popup (for logging only)
                        text = await element.inner_text() if element else ""
                        is_dangerous = any(
                            danger in text.lower() 
                            for danger in DANGEROUS_TEXT_PATTERNS
                        )
                        
                        if is_dangerous:
                            print(f"🔴 Dangerous popup detected - cancelling safely!")
                            print(f"   Text preview: {text[:150]}...")
                            self._dangerous_popups_cancelled += 1
                        
                        # Try to find a safe button to click
                        button_clicked = await self._click_safe_button(element)
                        
                        if button_clicked:
                            cancelled_count += 1
                            if is_dangerous:
                                print(f"   ✅ Cancelled dangerous popup (would have been: {text[:50]}...)")
                            else:
                                print(f"   ✅ Cancelled popup")
                            await asyncio.sleep(0.5)
                        else:
                            # If no safe button, try clicking outside
                            try:
                                await self.page.click('body', position={'x': 10, 'y': 10})
                                cancelled_count += 1
                                print("   ✅ Cancelled popup by clicking outside")
                                await asyncio.sleep(0.5)
                            except:
                                pass
                except:
                    continue
            
            # FOURTH: Also check for popups by role
            try:
                for role_selector in ['[role="dialog"]', '[role="alert"]']:
                    elements = await self.page.query_selector_all(role_selector)
                    for element in elements:
                        if await element.is_visible():
                            # Skip if it's a welcome popup and we already handled it
                            if self._welcome_popup_handled or self._welcome_popup_checked:
                                text = await element.inner_text()
                                if any(word in text.lower() for word in ['welcome', "what's new", 'new features']):
                                    continue
                            
                            # Try to cancel it
                            button_clicked = await self._click_safe_button(element)
                            if button_clicked:
                                cancelled_count += 1
                                print("   ✅ Cancelled role-based popup")
                                await asyncio.sleep(0.5)
            except:
                pass
            
            # FIFTH: Check for popups by text (for popups without specific selectors)
            # Only if welcome popup hasn't been handled/checked yet
            if handle_welcome and not self._welcome_popup_handled and not self._welcome_popup_checked:
                try:
                    body_text = await self.page.inner_text('body')
                    if body_text and any(word in body_text.lower() for word in ['welcome', "what's new", 'new features']):
                        # Try to find continue button
                        for button_selector in WELCOME_CONTINUE_BUTTONS:
                            try:
                                button = await self.page.query_selector(button_selector)
                                if button and await button.is_visible() and await button.is_enabled():
                                    await button.click()
                                    print("   ✅ Clicked Continue on welcome popup (by text detection)")
                                    self._welcome_popup_handled = True
                                    self._welcome_popups_handled += 1
                                    self._welcome_popup_checked = True
                                    cancelled_count += 1
                                    await asyncio.sleep(1)
                                    break
                            except:
                                continue
                except:
                    pass
            
            if cancelled_count > 0:
                self._popups_handled += cancelled_count
                self._last_popup_time = datetime.now()
                
            return cancelled_count
            
        except Exception as e:
            print(f"⚠️ Error cancelling popups: {e}")
            return cancelled_count
    
    async def _click_safe_button(self, popup_element) -> bool:
        """
        Find and click a safe button (Cancel, Close, Dismiss, etc.) within a popup.
        Returns True if a safe button was clicked.
        """
        try:
            # FIRST: Try safe cancel buttons within the popup
            for button_selector in SAFE_CANCEL_BUTTONS:
                try:
                    button = await popup_element.query_selector(button_selector)
                    if button:
                        if await button.is_visible() and await button.is_enabled():
                            button_text = await button.inner_text()
                            # Double-check it's not a dangerous button
                            if not any(
                                danger in button_text.lower() 
                                for danger in ['leave', 'dismiss', 'remove', 'delete', 'confirm', 'yes']
                            ):
                                await button.click()
                                return True
                except:
                    continue
            
            # SECOND: Try globally (if button not found in popup)
            for button_selector in SAFE_CANCEL_BUTTONS:
                try:
                    button = await self.page.query_selector(button_selector)
                    if button:
                        if await button.is_visible() and await button.is_enabled():
                            button_text = await button.inner_text()
                            # Double-check it's not a dangerous button
                            if not any(
                                danger in button_text.lower() 
                                for danger in ['leave', 'dismiss', 'remove', 'delete', 'confirm', 'yes']
                            ):
                                await button.click()
                                return True
                except:
                    continue
            
            # THIRD: Try to find any close/X button
            try:
                close_buttons = await popup_element.query_selector_all(
                    'button[aria-label*="close"], button[aria-label*="Close"], '
                    'button[class*="close"], button[class*="Close"], '
                    'svg[aria-label*="close"], svg[aria-label*="Close"]'
                )
                for close_button in close_buttons:
                    if await close_button.is_visible() and await close_button.is_enabled():
                        await close_button.click()
                        return True
            except:
                pass
            
            # FOURTH: Try pressing Escape key
            try:
                await self.page.keyboard.press('Escape')
                await asyncio.sleep(0.3)
                if not await popup_element.is_visible():
                    return True
            except:
                pass
            
            return False
            
        except Exception as e:
            print(f"   ⚠️ Error clicking safe button: {e}")
            return False
    
    async def _check_for_blocking_popups(self) -> bool:
        """
        Check if there are any popups blocking operations.
        Returns True if blocking popup exists.
        """
        try:
            for selector in POPUP_SELECTORS:
                try:
                    element = await self.page.query_selector(selector)
                    if element and await element.is_visible():
                        return True
                except:
                    continue
            
            # Check for role-based dialogs
            try:
                dialogs = await self.page.query_selector_all('[role="dialog"], [role="alert"]')
                for dialog in dialogs:
                    if await dialog.is_visible():
                        return True
            except:
                pass
            
            return False
            
        except Exception as e:
            return False
    
    async def ensure_no_popups(self, max_attempts: int = 5) -> bool:
        """
        Ensure all popups are cancelled before continuing.
        Returns True if no popups remain.
        """
        print("🔍 Checking for and handling popups...")
        
        for attempt in range(max_attempts):
            # Handle error popups first (critical)
            error_handled = await self._handle_error_popups()
            if error_handled:
                print("   ✅ Error popup handled")
                continue
            
            # Handle welcome popup first if not handled and not checked
            if not self._welcome_popup_handled and not self._welcome_popup_checked:
                welcome_handled = await self._handle_welcome_popup(timeout=10)
                if welcome_handled:
                    print("   ✅ Welcome popup handled")
                    continue
            
            # Cancel any other popups
            cancelled = await self._cancel_popups()
            
            if cancelled > 0:
                print(f"   Handled {cancelled} popup(s), waiting for them to clear...")
                await asyncio.sleep(1)
                continue
            
            # Check if any blocking popups remain
            if await self._check_for_blocking_popups():
                print(f"   Popup still present (attempt {attempt + 1}/{max_attempts})")
                # Try clicking outside
                try:
                    await self.page.click('body', position={'x': 10, 'y': 10})
                    await asyncio.sleep(0.5)
                except:
                    pass
                continue
            
            print("✅ No popups detected, continuing...")
            return True
        
        print("⚠️ Popups may still be present after max attempts")
        return False
    
    # ============================================================
    # STRICT CONNECTION MONITOR - WITH POPUP HANDLING
    # ============================================================
    
    async def _monitor_connection(self):
        """
        STRICT connection monitoring - detects disconnection IMMEDIATELY.
        Handles welcome popups and cancels all other popups safely.
        """
        print("🔌 STRICT Connection monitor active")
        print(f"   Checking every {CONNECTION_CHECK_INTERVAL}s")
        print(f"   Triggering after {CONSECUTIVE_FAILURES_THRESHOLD} failure(s)")
        print("   🛡️ Comprehensive popup handling:")
        print("   ✅ Waits for and clicks Continue on welcome popups")
        print("   ✅ Auto-cancels dangerous popups (leave group, dismiss admin)")
        print("   ✅ Auto-dismisses safe popups (rate limits, notifications)")
        print("   ✅ Handles 'Problem running' popup (clicks Reload)")
        print("   ✅ Handles 'Memory full' popup (clicks Logout, waits for re-login)")
        print("   ❌ Never clicks Leave/Delete/Confirm")
        
        while True:
            try:
                await asyncio.sleep(CONNECTION_CHECK_INTERVAL)
                
                if not self.page:
                    print("⚠️ Page is None - disconnected")
                    await self._handle_immediate_disconnect("Page is None")
                    continue
                
                # ============================================================
                # STEP 0: Handle error popups (critical - do this first)
                # ============================================================
                error_handled = await self._handle_error_popups()
                if error_handled:
                    print("   🛡️ Error popup handled")
                    continue
                
                # ============================================================
                # STEP 0.5: Handle welcome popup if not handled AND not checked yet
                # ============================================================
                if not self._welcome_popup_handled and not self._welcome_popup_checked:
                    # Check for welcome popup
                    for selector in WELCOME_POPUP_SELECTORS:
                        try:
                            element = await self.page.query_selector(selector)
                            if element and await element.is_visible():
                                print("   🎉 Welcome popup detected - clicking Continue...")
                                clicked = await self._click_welcome_button(element)
                                if clicked:
                                    print("   ✅ Clicked Continue on welcome popup")
                                    self._welcome_popup_handled = True
                                    self._welcome_popups_handled += 1
                                    self._welcome_popup_checked = True
                                    await asyncio.sleep(1)
                                    break
                        except:
                            continue
                    
                    # If no welcome popup found, mark as checked to avoid future checks
                    if not self._welcome_popup_handled:
                        self._welcome_popup_checked = True
                
                # ============================================================
                # STEP 1: Cancel all other popups safely
                # ============================================================
                popups_handled = await self._cancel_popups()
                if popups_handled > 0:
                    print(f"   🛡️ Handled {popups_handled} popup(s)")
                
                # ============================================================
                # STEP 2: Check for DISCONNECTION
                # ============================================================
                disconnected = await self._check_disconnection()
                
                if disconnected:
                    self._consecutive_failures += 1
                    print(f"⚠️ Disconnection detected! ({self._consecutive_failures}/{CONSECUTIVE_FAILURES_THRESHOLD})")
                    
                    if self._consecutive_failures >= CONSECUTIVE_FAILURES_THRESHOLD:
                        await self._handle_immediate_disconnect("Disconnection confirmed")
                        self._consecutive_failures = 0
                else:
                    # Check connection
                    connected = await self._check_connected()
                    
                    if connected:
                        if self._consecutive_failures > 0:
                            print(f"✅ Connection restored! (was {self._consecutive_failures} failures)")
                            self._consecutive_failures = 0
                            
                        if not self.is_connected:
                            self.is_connected = True
                            self._last_known_connected = True
                            self._reconnect_time = datetime.now()
                            await self._notify_reconnect()
                    else:
                        self._consecutive_failures += 1
                        if self._consecutive_failures >= CONSECUTIVE_FAILURES_THRESHOLD:
                            # Try handling popups again before triggering disconnect
                            await self._cancel_popups()
                            
                            await self._handle_immediate_disconnect("Neither connected nor disconnected")
                            self._consecutive_failures = 0
                
            except Exception as e:
                print(f"⚠️ Connection monitor error: {e}")
                self._consecutive_failures += 1
                
                if self._consecutive_failures >= CONSECUTIVE_FAILURES_THRESHOLD:
                    await self._handle_immediate_disconnect(f"Monitor error: {e}")
                    self._consecutive_failures = 0
    
    async def _check_disconnection(self) -> bool:
        """STRICT: Check for definitive disconnection indicators."""
        try:
            for selector in DISCONNECT_SELECTORS:
                try:
                    element = await self.page.query_selector(selector)
                    if element:
                        is_visible = await element.is_visible()
                        if is_visible:
                            return True
                except:
                    continue
            
            try:
                title = await self.page.title()
                if title:
                    title_lower = title.lower()
                    if any(word in title_lower for word in ['qr', 'scan', 'connect', 'link device']):
                        return True
            except:
                pass
            
            try:
                body_text = await self.page.inner_text('body')
                if body_text:
                    if any(phrase in body_text for phrase in [
                        'phone not connected',
                        'scan the qr code',
                        'link a device',
                        'keep your phone connected'
                    ]):
                        return True
            except:
                pass
            
            return False
            
        except Exception as e:
            print(f"⚠️ Could not check disconnection: {e}")
            return True
    
    async def _check_connected(self) -> bool:
        """Check if we are definitively connected."""
        try:
            for selector in CONNECTED_SELECTORS:
                try:
                    element = await self.page.query_selector(selector)
                    if element:
                        is_visible = await element.is_visible()
                        if is_visible:
                            return True
                except:
                    continue
            
            try:
                messages = await self.page.query_selector('div[data-testid="msg-container"]')
                if messages:
                    return True
            except:
                pass
            
            return False
            
        except Exception as e:
            return False
    
    async def _handle_immediate_disconnect(self, reason: str):
        """Handle immediate disconnection - notify all callbacks."""
        if self.is_connected:
            self.is_connected = False
            self._last_known_connected = False
            self._disconnect_time = datetime.now()
            
            print("\n" + "=" * 70)
            print("🔴 WHATSAPP DISCONNECTED!")
            print(f"   Reason: {reason}")
            print(f"   Time: {self._disconnect_time.strftime('%H:%M:%S')}")
            print("=" * 70)
            print("   All operations will be paused until reconnection.")
            print("   The bot will automatically retry to reconnect.")
            print("=" * 70 + "\n")
            
            await self._notify_disconnect()
            asyncio.create_task(self._attempt_reconnect())
    
    async def _attempt_reconnect(self):
        """Attempt to reconnect with immediate detection."""
        print(f"\n🔄 Attempting to reconnect... (max {MAX_RECONNECT_ATTEMPTS} attempts)")
        
        for attempt in range(MAX_RECONNECT_ATTEMPTS):
            try:
                print(f"📡 Reconnect attempt {attempt + 1}/{MAX_RECONNECT_ATTEMPTS}")
                
                # Handle error popups first
                await self._handle_error_popups()
                
                # Handle welcome popup if needed
                if not self._welcome_popup_handled and not self._welcome_popup_checked:
                    await self._handle_welcome_popup(timeout=10)
                
                # Cancel any popups
                await self._cancel_popups()
                
                # Check connection
                if await self._check_connected():
                    print("✅ Already connected!")
                    self.is_connected = True
                    self._last_known_connected = True
                    await self._notify_reconnect()
                    return True
                
                # Try reload
                if self.page:
                    try:
                        await self.page.reload()
                        print("   🔄 Page reloaded")
                        await asyncio.sleep(3)
                    except:
                        print("   ⚠️ Could not reload page")
                
                # Handle error popups after reload
                await self._handle_error_popups()
                
                # Handle welcome popup after reload
                if not self._welcome_popup_handled and not self._welcome_popup_checked:
                    await self._handle_welcome_popup(timeout=10)
                
                # Cancel popups after reload
                await self._cancel_popups()
                
                if await self._check_connected():
                    print("✅ Reconnected after reload!")
                    self.is_connected = True
                    self._last_known_connected = True
                    await self._notify_reconnect()
                    return True
                
                if await self._check_disconnection():
                    print("📱 QR code detected - manual re-login needed")
                    await self._re_login()
                    return True
                
                if attempt < MAX_RECONNECT_ATTEMPTS - 1:
                    print(f"⏳ Waiting {RECONNECT_DELAY}s before next attempt...")
                    await asyncio.sleep(RECONNECT_DELAY)
                
            except Exception as e:
                print(f"❌ Reconnect attempt {attempt + 1} failed: {e}")
                if attempt < MAX_RECONNECT_ATTEMPTS - 1:
                    await asyncio.sleep(RECONNECT_DELAY)
        
        print("❌ All reconnect attempts failed. Please check your WhatsApp connection manually.")
        return False
    
    async def _re_login(self):
        """Force re-login by showing QR code"""
        try:
            print("📱 Starting re-login process...")
            self._welcome_popup_handled = False  # Reset welcome state
            self._welcome_popup_checked = False  # Reset welcome check flag
            
            await self.page.goto(WHATSAPP_WEB_URL + "?noredirect", wait_until='domcontentloaded')
            await asyncio.sleep(2)
            
            # Handle error popups
            await self._handle_error_popups()
            
            # Cancel any popups
            await self._cancel_popups()
            
            print("⏳ Waiting for QR code...")
            start_time = datetime.now()
            timeout = 60
            
            while (datetime.now() - start_time).seconds < timeout:
                # Handle error popups while waiting
                await self._handle_error_popups()
                
                # Cancel popups while waiting
                await self._cancel_popups()
                
                if await self._check_disconnection():
                    print("📱 QR code visible - please scan with your phone")
                    await self.wait_for_connection()
                    return True
                
                await asyncio.sleep(1)
            
            print("❌ Re-login timed out")
            return False
            
        except Exception as e:
            print(f"❌ Re-login failed: {e}")
            return False
    
    async def _notify_disconnect(self):
        """Notify all disconnect callbacks"""
        for callback in self._disconnect_callbacks:
            try:
                if asyncio.iscoroutinefunction(callback):
                    await callback()
                else:
                    callback()
            except Exception as e:
                print(f"⚠️ Disconnect callback error: {e}")
    
    async def _notify_reconnect(self):
        """Notify all reconnect callbacks"""
        for callback in self._reconnect_callbacks:
            try:
                if asyncio.iscoroutinefunction(callback):
                    await callback()
                else:
                    callback()
            except Exception as e:
                print(f"⚠️ Reconnect callback error: {e}")
    
    # ============================================================
    # EXTERNAL CONNECTION METHODS
    # ============================================================
    
    async def check_connection(self) -> bool:
        """One-time connection check for external callers."""
        # Handle error popups first
        await self._handle_error_popups()
        
        # Handle welcome popup if needed
        if not self._welcome_popup_handled and not self._welcome_popup_checked:
            await self._handle_welcome_popup(timeout=10)
        
        # Cancel any popups first
        await self._cancel_popups()
        
        if await self._check_disconnection():
            self.is_connected = False
            return False
        
        connected = await self._check_connected()
        self.is_connected = connected
        return connected
    
    async def wait_for_connection(self, timeout: int = 240) -> bool:
        """Wait for WhatsApp to be connected."""
        print(f"⏳ Waiting for WhatsApp to connect... (timeout: {timeout}s)")
        
        start_time = datetime.now()
        last_progress = start_time
        
        while (datetime.now() - start_time).seconds < timeout:
            # Handle error popups
            await self._handle_error_popups()
            
            # Handle welcome popup if needed
            if not self._welcome_popup_handled and not self._welcome_popup_checked:
                await self._handle_welcome_popup(timeout=10)
            
            # Cancel any popups
            await self._cancel_popups()
            
            if await self._check_connected():
                self.is_connected = True
                self._last_known_connected = True
                print("✅ Connected!")
                return True
            
            elapsed = int((datetime.now() - start_time).seconds)
            if elapsed % 10 == 0 and elapsed > 0:
                if (datetime.now() - last_progress).seconds >= 10:
                    last_progress = datetime.now()
                    print(f"⏳ Still waiting... ({elapsed}s)")
                    
                    if await self._check_disconnection():
                        print("   📱 QR code still visible - waiting for scan")
            
            await asyncio.sleep(2)
        
        print(f"❌ Connection timeout after {timeout}s")
        return False
    
    async def ensure_connection(self) -> bool:
        """Ensure connection is active and no popups are blocking."""
        # Handle error popups first
        await self._handle_error_popups()
        
        # Handle welcome popup if needed
        if not self._welcome_popup_handled and not self._welcome_popup_checked:
            await self._handle_welcome_popup(timeout=15)
        
        # Cancel any popups
        await self.ensure_no_popups()
        
        if await self.check_connection():
            return True
        
        print("⏳ Waiting for WhatsApp to reconnect...")
        return await self.wait_for_connection()
    
    # ============================================================
    # SESSION SAVING
    # ============================================================
    
    async def save_session_state(self):
        """Save session state"""
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
    # CLEANUP
    # ============================================================
    
    async def cleanup(self):
        """Clean up browser resources"""
        try:
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

    # ============================================================
    # STATISTICS
    # ============================================================
    
    def get_stats(self) -> dict:
        """Get popup handling statistics"""
        return {
            'total_popups_handled': self._popups_handled,
            'dangerous_popups_cancelled': self._dangerous_popups_cancelled,
            'welcome_popups_handled': self._welcome_popups_handled,
            'welcome_popup_handled': self._welcome_popup_handled,
            'last_popup_time': self._last_popup_time.isoformat() if self._last_popup_time else None,
            'is_connected': self.is_connected,
            'is_logged_in': self.is_logged_in,
        }