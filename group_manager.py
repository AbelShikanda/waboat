"""
Group Manager Module
====================
Handles advanced group management:
1. Navigate to core groups
2. Get invite links
3. Update group descriptions with standardized message
4. Save/update links in data/links/group_links.json with proper category
5. EXHAUSTIVE CONNECTION MONITORING: CHECKS EVERY CRITICAL STEP

USAGE: This module does NOT handle its own login.
       It receives page, context, and login_manager from the main bot.
"""

import json
import asyncio
import random
import re
import pyperclip
import shutil
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Optional
from playwright.async_api import async_playwright

# ============================================================
# IMPORT CONFIG
# ============================================================

from target_groups import CORE_GROUPS, GROUP_CATEGORIES, get_groups_by_category

# ============================================================
# CONFIGURATION
# ============================================================

BASE_DIR = Path(__file__).parent
DATA_DIR = BASE_DIR / "data"
LINKS_DIR = DATA_DIR / "links"
BLACKLIST_FILE = DATA_DIR / "blacklist.json"
GROUP_LINKS_FILE = LINKS_DIR / "group_links.json"

# Create directories
DATA_DIR.mkdir(parents=True, exist_ok=True)
LINKS_DIR.mkdir(parents=True, exist_ok=True)

# ============================================================
# DELAY CONFIGURATION (REUSABLE)
# ============================================================

# Standard delays (in seconds)
DELAYS = {
    "short": 1,
    "medium": 2,
    "long": 3,
    "extra": 3,
    "scroll": 2,
    "click": 1,
    "type": 0.1,
    "between_groups": 3.0,
}

# Typing delays (in milliseconds)
TYPING_DELAYS = {
    "min": 5,
    "max": 15,
}

# Connection check interval during long operations
CONNECTION_CHECK_INTERVAL = 30

# ============================================================
# CATEGORY HELPER
# ============================================================

def get_group_category(group_name: str) -> str:
    """Determine the category of a group"""
    for category, groups in GROUP_CATEGORIES.items():
        if group_name in groups:
            return category
    return "core"

def get_group_platform(group_name: str) -> str:
    return "whatsapp"

# ============================================================
# BLACKLIST LOADER
# ============================================================

def load_blacklist() -> dict:
    if BLACKLIST_FILE.exists():
        try:
            with open(BLACKLIST_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except:
            return {"users": [], "numbers": []}
    return {"users": [], "numbers": []}

# ============================================================
# GROUP LINKS MANAGER
# ============================================================

class GroupLinksManager:
    def __init__(self):
        self.links_file = GROUP_LINKS_FILE
        self.data = self._load()
    
    def _load(self) -> dict:
        if self.links_file.exists():
            try:
                with open(self.links_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except:
                return {"groups": []}
        return {"groups": []}
    
    def _save(self):
        groups = self.data.get("groups", [])
        self.data["total_groups"] = len(groups)
        self.data["total_pending"] = len([g for g in groups if g.get("status") == "pending"])
        self.data["total_posted"] = len([g for g in groups if g.get("status") == "posted"])
        self.data["last_updated"] = datetime.now().isoformat()
        
        with open(self.links_file, 'w', encoding='utf-8') as f:
            json.dump(self.data, f, indent=2, ensure_ascii=False)
    
    def get_group(self, group_name: str) -> Optional[dict]:
        for group in self.data.get("groups", []):
            if group.get("name") == group_name:
                return group
        return None
    
    def add_or_update_group(self, group_name: str, url: str, description: str, 
                           platform: str = "whatsapp", category: str = "core"):
        groups = self.data.get("groups", [])
        
        existing = None
        for g in groups:
            if g.get("name") == group_name:
                existing = g
                break
        
        now = datetime.now()
        iso_str = now.isoformat()
        
        if existing:
            existing["url"] = url
            existing["description"] = description
            existing["platform"] = platform
            existing["category"] = category
            existing["last_updated"] = iso_str
        else:
            groups.append({
                "name": group_name,
                "platform": platform,
                "url": url,
                "description": description,
                "category": category,
                "status": "pending",
                "posted_date": None,
                "posted_time": None,
                "last_updated": iso_str
            })
        
        self.data["groups"] = groups
        self._save()
        return True
    
    def get_all_groups(self) -> List[dict]:
        return self.data.get("groups", [])

# ============================================================
# DESCRIPTION GENERATOR
# ============================================================

def generate_group_description(group_name: str, invite_link: str) -> str:
    """Single line description - ZERO scrolling during typing"""
    return f"Welcome to {group_name}! 📌 Be respectful • No spam • Stay on topic • No hate speech • Share value • 🔗 {invite_link} • Connect, share ideas & grow! 🚀"

# ============================================================
# LINK VALIDATOR
# ============================================================

def is_valid_whatsapp_link(link: str) -> bool:
    """Check if a string is a valid WhatsApp invite link"""
    if not link:
        return False
    if "whatsapp.com" not in link:
        return False
    if not link.startswith(('http://', 'https://')):
        return False
    if ':root' in link or '{' in link or '--' in link:
        return False
    if '{"' in link or '};' in link or 'function' in link:
        return False
    if len(link) > 500:
        return False
    if '<' in link or '>' in link:
        return False
    if 'pending-participantsMembers' in link:
        return False
    return True

def clean_whatsapp_link(link: str) -> str:
    """Clean a WhatsApp link by removing extra text"""
    if not link:
        return link
    if 'pending-participantsMembers' in link:
        link = link.replace('pending-participantsMembers', '')
    match = re.search(r'https?://[^\s]+whatsapp\.com[^\s]*', link)
    if match:
        return match.group(0)
    return link

# ============================================================
# GROUP MANAGER CLASS - EXHAUSTIVE CONNECTION MONITORING
# ============================================================

class GroupManager:
    """
    Handles group management with EXHAUSTIVE connection monitoring.
    
    EXHAUSTIVE CONNECTION MONITORING:
    - Checks connection at EVERY critical step
    - Pauses ALL activity when disconnected
    - Resumes automatically when reconnected
    - Background health monitor for proactive detection
    
    NOTE: This class receives page, context, and login_manager from the main bot.
          It does NOT handle its own login.
    """
    
    def __init__(self, login_manager=None):
        """
        Initialize GroupManager
        
        Args:
            login_manager: LoginManager instance for connection monitoring
        """
        self.page = None
        self.context = None
        self.login_manager = login_manager
        
        # Validate login_manager
        if login_manager:
            print("✅ Connection monitoring ENABLED - exhaustive checks active")
        else:
            print("⚠️ No login manager - connection monitoring DISABLED")
            print("   The bot will NOT pause on disconnection!")
        
        self.blacklist = load_blacklist()
        self.links_manager = GroupLinksManager()
        self.is_paused = False
        self.is_running = False
        
        # Connection monitoring stats
        self.connection_stats = {
            "checks_performed": 0,
            "disconnections_detected": 0,
            "reconnections_succeeded": 0,
            "operations_paused": 0
        }
        
        # Track connection check counter for periodic checks during loops
        self._connection_check_counter = 0
    
    # ============================================================
    # EXHAUSTIVE CONNECTION MONITORING METHODS
    # ============================================================
    
    async def ensure_connection(self, context: str = "unknown") -> bool:
        """
        EXHAUSTIVE connection check - PAUSES ALL ACTIVITY if disconnected.
        
        Args:
            context: Description of where the check is being called from
            
        Returns:
            bool: True if connected, False if not (but will wait for reconnection)
        """
        self._connection_check_counter += 1
        self.connection_stats["checks_performed"] += 1
        
        if not self.login_manager:
            return True  # No login manager, assume connected
        
        try:
            is_connected = await self.login_manager.check_connection()
            
            if is_connected:
                # If we were paused, clear the flag
                if self.is_paused:
                    self.is_paused = False
                    print(f"✅ Connection restored (checked from: {context})")
                return True
            
            # DISCONNECTED - PAUSE ALL ACTIVITY
            self.is_paused = True
            self.connection_stats["disconnections_detected"] += 1
            self.connection_stats["operations_paused"] += 1
            
            print("\n" + "=" * 70)
            print(f"⏸️  CONNECTION LOST - PAUSING ALL ACTIVITY")
            print(f"   Location: {context}")
            print(f"   Time: {datetime.now().strftime('%H:%M:%S')}")
            print("=" * 70)
            print("   WhatsApp connection lost. Waiting for reconnection...")
            print("   All group management operations are on hold.")
            print("   Will check every 5 seconds...")
            print("=" * 70 + "\n")
            
            # Wait indefinitely until reconnected
            reconnected = await self.login_manager.wait_for_connection()
            
            if reconnected:
                self.is_paused = False
                self.connection_stats["reconnections_succeeded"] += 1
                
                print("\n" + "=" * 70)
                print("▶️  CONNECTION RESTORED - RESUMING ACTIVITY")
                print(f"   Location: {context}")
                print(f"   Time: {datetime.now().strftime('%H:%M:%S')}")
                print("=" * 70)
                print("   WhatsApp reconnected successfully!")
                print("   Resuming group management operations...")
                print("=" * 70 + "\n")
                
                # Small delay to let WhatsApp stabilize
                await asyncio.sleep(2)
                return True
            
            # If wait_for_connection returns False (shouldn't happen with indefinite wait)
            print("❌ Failed to reconnect after waiting")
            return False
            
        except Exception as e:
            print(f"⚠️ Connection check error at {context}: {e}")
            # If we can't check, assume we're connected to avoid false positives
            return True
    
    async def check_connection_before_operation(self, operation_name: str) -> bool:
        """
        Convenience method to check connection before any operation.
        
        Args:
            operation_name: Name of the operation being performed
            
        Returns:
            bool: True if safe to proceed, False if should abort
        """
        if not self.login_manager:
            return True
        
        is_connected = await self.ensure_connection(f"Before: {operation_name}")
        
        if not is_connected:
            print(f"⚠️ Cannot perform '{operation_name}' - no connection")
            return False
        
        # Additional quick check - ensure page is responsive
        try:
            # Try to find any element to verify page is responsive
            await self.page.wait_for_timeout(100)  # Very short timeout
        except:
            # Page might be frozen
            print(f"⚠️ Page seems unresponsive before '{operation_name}'")
            # Try to recover by checking connection again
            return await self.ensure_connection(f"Recovery check: {operation_name}")
        
        return True
    
    async def wait_if_paused(self, context: str = "general") -> bool:
        """
        EXHAUSTIVE: Check if paused and wait if needed.
        Used between operations to ensure we don't continue if disconnected.
        
        Args:
            context: Description of where this is being called
            
        Returns:
            bool: True if safe to proceed, False if should abort
        """
        if self.is_paused:
            print(f"⏳ Bot is paused (waiting for reconnection)... [{context}]")
            
            if not self.login_manager:
                print("⚠️ No login manager but paused flag is set - clearing")
                self.is_paused = False
                return True
            
            await self.login_manager.wait_for_connection()
            self.is_paused = False
            print(f"▶️ Bot resumed! [{context}]")
            
            # Wait a moment for stability
            await asyncio.sleep(1)
        
        # Always do a fresh check if we have a login manager
        if self.login_manager:
            return await self.ensure_connection(f"wait_if_paused: {context}")
        
        return True
    
    async def safe_operation(self, operation_name: str, operation_func, *args, **kwargs):
        """
        Wrapper to safely execute an operation with connection checking.
        
        Args:
            operation_name: Name of the operation (for logging)
            operation_func: Async function to execute
            *args, **kwargs: Arguments to pass to the function
            
        Returns:
            The result of the operation, or None if connection failed
        """
        # Check connection before operation
        if not await self.check_connection_before_operation(operation_name):
            return None
        
        try:
            # Execute the operation
            result = await operation_func(*args, **kwargs)
            
            # Check connection after operation
            if not await self.ensure_connection(f"After: {operation_name}"):
                return None
            
            return result
            
        except Exception as e:
            print(f"⚠️ Error during {operation_name}: {e}")
            # Check if error was due to connection issues
            if self.login_manager:
                is_connected = await self.ensure_connection(f"Error recovery: {operation_name}")
                if not is_connected:
                    return None
            # Re-raise if not a connection issue
            raise
    
    # ============================================================
    # BACKGROUND HEALTH MONITOR
    # ============================================================
    
    async def connection_health_monitor(self):
        """
        Background task that periodically checks connection health.
        Runs in the background while other operations are ongoing.
        """
        print("🔄 Connection health monitor started for GroupManager")
        
        while self.is_running:
            await asyncio.sleep(CONNECTION_CHECK_INTERVAL)
            
            if not self.login_manager:
                continue
            
            try:
                # Quick connection check
                is_connected = await self.login_manager.check_connection()
                
                if not is_connected and not self.is_paused:
                    # Disconnection detected by background monitor
                    print("\n⚠️ Background monitor detected disconnection!")
                    self.is_paused = True
                    self.connection_stats["disconnections_detected"] += 1
                    self.connection_stats["operations_paused"] += 1
                    
                    print("⏳ Waiting for reconnection...")
                    await self.login_manager.wait_for_connection()
                    
                    self.is_paused = False
                    self.connection_stats["reconnections_succeeded"] += 1
                    print("✅ Background monitor: Connection restored!")
                    
            except Exception as e:
                print(f"⚠️ Background monitor error: {e}")
    
    # ============================================================
    # START/STOP METHODS
    # ============================================================
    
    async def start(self):
        """Start the manager with connection monitoring"""
        self.is_running = True
        
        # Start background health monitor
        asyncio.create_task(self.connection_health_monitor())
        
        print("✅ Group Manager started with EXHAUSTIVE connection monitoring")
        print(f"   Connection checks at EVERY critical step")
        print(f"   Health monitor running every {CONNECTION_CHECK_INTERVAL}s")
    
    async def stop(self):
        """Stop the manager"""
        self.is_running = False
        print("🛑 Group Manager stopped")
    
    # ============================================================
    # SET PAGE AND CONTEXT
    # ============================================================
    
    def set_page(self, page, context):
        """Set the page and context for the manager"""
        self.page = page
        self.context = context
        print("✅ Page and context set for GroupManager")
    
    # ============================================================
    # 1. OPEN GROUP - WITH EXHAUSTIVE CONNECTION CHECKS
    # ============================================================
    
    async def open_group(self, group_name: str) -> bool:
        """Open a group by name with EXHAUSTIVE connection checks at EVERY step"""
        
        # CONNECTION CHECK: Before starting
        if not await self.ensure_connection(f"open_group_start_{group_name}"):
            print("❌ WhatsApp not connected. Cannot open group.")
            return False
        
        print(f"  🔍 Opening: {group_name}")
        
        if group_name in self.blacklist.get("groups", []):
            print(f"  ⚠️ Group '{group_name}' is blacklisted. Skipping.")
            return False
        
        for attempt in range(2):
            # CONNECTION CHECK: Before each attempt
            if not await self.ensure_connection(f"open_group_attempt_{attempt}_{group_name}"):
                print("❌ Connection lost during open attempt. Pausing...")
                await self.ensure_connection(f"open_group_reconnect_{attempt}_{group_name}")
                print("✅ Connection restored. Retrying...")
                continue
            
            try:
                # Click search
                print(f"    [1/4] Clicking search...")
                
                search_selectors = [
                    'div[data-testid="chat-list-search"]',
                    'button[aria-label="Search"]',
                    'div[role="textbox"]'
                ]
                
                search_clicked = False
                for selector in search_selectors:
                    # CONNECTION CHECK: During search selector iteration
                    if not await self.ensure_connection(f"open_group_search_selector_{attempt}_{selector[:20]}"):
                        continue
                    
                    try:
                        search = await self.page.query_selector(selector)
                        if search:
                            await search.click()
                            await asyncio.sleep(DELAYS["short"])
                            search_clicked = True
                            break
                    except:
                        continue
                
                if not search_clicked:
                    await self.page.keyboard.press('Control+Shift+J')
                    await asyncio.sleep(DELAYS["short"])
                
                # CONNECTION CHECK: After search
                if not await self.ensure_connection(f"open_group_after_search_{attempt}_{group_name}"):
                    continue
                
                # Type group name
                print(f"    [2/4] Typing group name...")
                
                input_selectors = [
                    'input[type="text"]',
                    'div[data-testid="chat-list-search"] input'
                ]
                
                typed = False
                for selector in input_selectors:
                    # CONNECTION CHECK: During typing
                    if not await self.ensure_connection(f"open_group_typing_{attempt}_{group_name}"):
                        continue
                    
                    try:
                        search_input = await self.page.query_selector(selector)
                        if search_input:
                            await search_input.click()
                            await search_input.fill("")
                            await asyncio.sleep(DELAYS["short"])
                            for char in group_name:
                                await search_input.type(char, delay=random.randint(10, 30))
                            await asyncio.sleep(DELAYS["medium"])
                            typed = True
                            break
                    except:
                        continue
                
                if not typed:
                    await self.page.keyboard.type(group_name, delay=random.randint(10, 30))
                    await asyncio.sleep(DELAYS["medium"])
                
                # CONNECTION CHECK: After typing
                if not await self.ensure_connection(f"open_group_after_typing_{attempt}_{group_name}"):
                    continue
                
                # Click group
                print(f"    [3/4] Finding group in results...")
                
                group_selectors = [
                    f'div[role="row"]:has-text("{group_name}")',
                    f'span[data-testid="chat-name"]:has-text("{group_name}")'
                ]
                
                group_found = False
                for selector in group_selectors:
                    # CONNECTION CHECK: During group finding
                    if not await self.ensure_connection(f"open_group_finding_{attempt}_{group_name}"):
                        continue
                    
                    try:
                        group = await self.page.query_selector(selector)
                        if group:
                            await group.click()
                            await asyncio.sleep(DELAYS["long"])
                            group_found = True
                            print(f"  ✅ Opened: {group_name}")
                            return True
                    except:
                        continue
                
                if not group_found:
                    print(f"    [3/4] Scanning chats for '{group_name}'...")
                    chats = await self.page.query_selector_all('div[role="row"]')
                    for chat_index, chat in enumerate(chats):
                        # CONNECTION CHECK: During chat scanning (every 5 chats)
                        if chat_index % 5 == 0:
                            if not await self.ensure_connection(f"open_group_scanning_{attempt}_{group_name}"):
                                break
                        
                        try:
                            text = await chat.inner_text()
                            if group_name.lower() in text.lower():
                                await chat.click()
                                await asyncio.sleep(DELAYS["long"])
                                print(f"  ✅ Opened: {group_name}")
                                return True
                        except:
                            continue
                
                print(f"  ❌ Group not found: {group_name}")
                if attempt < 1:
                    await asyncio.sleep(DELAYS["long"])
                    
            except Exception as e:
                print(f"  ❌ Error: {e}")
                if attempt < 1:
                    await asyncio.sleep(DELAYS["long"])
        
        return False
    
    # ============================================================
    # 2. OPEN GROUP INFO - WITH CONNECTION CHECK
    # ============================================================
    
    async def open_group_info(self) -> bool:
        """Open group info by clicking the group name in header"""
        
        # CONNECTION CHECK: Before starting
        if not await self.ensure_connection("open_group_info"):
            print("❌ WhatsApp not connected. Cannot open group info.")
            return False
        
        print(f"    🔍 Opening group info...")
        
        try:
            header = await self.page.query_selector('header[data-testid="conversation-header"]')
            if header:
                await header.click()
                await asyncio.sleep(DELAYS["long"])
                print(f"    ✅ Opened group info by clicking header")
                return True
        except:
            pass
        
        try:
            name_el = await self.page.query_selector('header[data-testid="conversation-header"] span[dir="auto"]')
            if name_el:
                await name_el.click()
                await asyncio.sleep(DELAYS["long"])
                print(f"    ✅ Opened group info by clicking group name")
                return True
        except:
            pass
        
        print(f"    ❌ Could not open group info")
        return False
    
    # ============================================================
    # 3. GO BACK FROM INVITE SECTION - WITH CONNECTION CHECK
    # ============================================================
    
    async def go_back_from_invite(self) -> bool:
        """Go back from invite section with connection check"""
        
        # CONNECTION CHECK: Before starting
        if not await self.ensure_connection("go_back_from_invite"):
            print("❌ WhatsApp not connected. Cannot go back.")
            return False
        
        print(f"    🔍 Going back from invite section...")
        
        back_selectors = [
            '[aria-label="Back"]',
            'button[aria-label="Back"]',
            '[data-tab="2"][aria-label="Back"]',
            'header button:first-child'
        ]
        
        for selector in back_selectors:
            # CONNECTION CHECK: During selector iteration
            if not await self.ensure_connection(f"go_back_selector_{selector[:20]}"):
                continue
            
            try:
                back_btn = await self.page.query_selector(selector)
                if back_btn:
                    is_visible = await back_btn.is_visible()
                    if is_visible:
                        await back_btn.click()
                        await asyncio.sleep(DELAYS["long"])
                        print(f"    ✅ Clicked back button: {selector}")
                        return True
            except:
                continue
        
        try:
            header = await self.page.query_selector('header')
            if header:
                await header.click()
                await asyncio.sleep(DELAYS["long"])
                print(f"    ✅ Clicked header to go back")
                return True
        except:
            pass
        
        print(f"    ❌ Could not find back button")
        return False
    
    # ============================================================
    # 4. GET GROUP LINK - WITH EXHAUSTIVE CONNECTION CHECKS
    # ============================================================
    
    async def get_group_link(self, group_name: str) -> Optional[str]:
        """Get the invite link for a group with EXHAUSTIVE connection checks"""
        
        # CONNECTION CHECK: Before starting
        if not await self.ensure_connection(f"get_group_link_start_{group_name}"):
            print("❌ WhatsApp not connected. Cannot get link.")
            return None
        
        print(f"  🔗 Getting link for: {group_name}")
        
        try:
            # CONNECTION CHECK: Before opening group info
            if not await self.ensure_connection(f"get_group_link_open_info_{group_name}"):
                return None
            
            if not await self.open_group_info():
                return None
            
            await asyncio.sleep(DELAYS["long"])
            
            # CONNECTION CHECK: After opening group info
            if not await self.ensure_connection(f"get_group_link_after_info_{group_name}"):
                return None
            
            print(f"    🔍 Looking for invite link section...")
            
            await self.page.evaluate('''
                () => {
                    const panel = document.querySelector('div[data-testid="group-panel"]');
                    if (panel) {
                        panel.scrollTop = panel.scrollHeight;
                    }
                }
            ''')
            await asyncio.sleep(DELAYS["scroll"])
            
            # CONNECTION CHECK: After scrolling
            if not await self.ensure_connection(f"get_group_link_after_scroll_{group_name}"):
                return None
            
            invite_found = False
            
            invite_selectors = [
                '[data-testid="cell-frame-container"]:has-text("Invite to group via link")',
                'div[role="button"]:has-text("Invite to group via link")',
                'div:has-text("Invite to group via link")',
                'button:has-text("Invite")'
            ]
            
            for selector in invite_selectors:
                # CONNECTION CHECK: During invite selector iteration
                if not await self.ensure_connection(f"get_group_link_invite_{group_name}"):
                    continue
                
                try:
                    invite_el = await self.page.query_selector(selector)
                    if invite_el:
                        is_visible = await invite_el.is_visible()
                        if is_visible:
                            await invite_el.click()
                            await asyncio.sleep(DELAYS["click"])
                            invite_found = True
                            print(f"    ✅ Clicked invite section")
                            break
                except:
                    continue
            
            if not invite_found:
                print(f"    ⚠️ No invite link section found")
                return None
            
            # CONNECTION CHECK: After clicking invite
            if not await self.ensure_connection(f"get_group_link_after_invite_{group_name}"):
                return None
            
            print(f"    🔍 Clicking copy link...")
            
            copy_selectors = [
                '[data-testid="li-copy-link"]',
                '[aria-label="Copy link"]',
                'button:has-text("Copy link")'
            ]
            
            copy_clicked = False
            for selector in copy_selectors:
                # CONNECTION CHECK: During copy selector iteration
                if not await self.ensure_connection(f"get_group_link_copy_{group_name}"):
                    continue
                
                try:
                    copy_btn = await self.page.query_selector(selector)
                    if copy_btn:
                        await copy_btn.click()
                        await asyncio.sleep(DELAYS["extra"])
                        copy_clicked = True
                        print(f"    ✅ Clicked copy button")
                        break
                except:
                    continue
            
            if not copy_clicked:
                print(f"    ⚠️ Could not find copy button")
                return None
            
            # CONNECTION CHECK: After clicking copy
            if not await self.ensure_connection(f"get_group_link_after_copy_{group_name}"):
                return None
            
            print(f"    📋 Reading link from clipboard...")
            
            link_text = None
            for attempt in range(3):
                # CONNECTION CHECK: During each clipboard attempt
                if not await self.ensure_connection(f"get_group_link_clipboard_{attempt}_{group_name}"):
                    continue
                
                try:
                    await asyncio.sleep(DELAYS["short"])
                    link_text = pyperclip.paste()
                    
                    if link_text and "whatsapp.com" in link_text:
                        print(f"    ✅ Link captured from clipboard (attempt {attempt+1})")
                        return clean_whatsapp_link(link_text)
                    else:
                        print(f"    ⚠️ Attempt {attempt+1}: No valid link in clipboard")
                        
                except Exception as e:
                    print(f"    ⚠️ Attempt {attempt+1} failed: {e}")
                    await asyncio.sleep(DELAYS["short"])
            
            # CONNECTION CHECK: Before fallback method
            if not await self.ensure_connection(f"get_group_link_fallback_{group_name}"):
                return None
            
            print(f"    🔍 Fallback: Using Ctrl+V to verify...")
            
            try:
                search_input = await self.page.query_selector('input[type="text"], div[role="textbox"]')
                if search_input:
                    await search_input.click()
                    await asyncio.sleep(DELAYS["short"])
                    await search_input.fill("")
                    await asyncio.sleep(DELAYS["short"])
                    await self.page.keyboard.press('Control+V')
                    await asyncio.sleep(DELAYS["medium"])
                    
                    pasted_text = await search_input.get_attribute('value')
                    if not pasted_text:
                        pasted_text = await search_input.text_content()
                    
                    if pasted_text and "whatsapp.com" in pasted_text:
                        print(f"    ✅ Link verified via Ctrl+V paste")
                        await search_input.fill("")
                        return clean_whatsapp_link(pasted_text)
                    
                    await search_input.fill("")
            except Exception as e:
                print(f"    ⚠️ Ctrl+V verification failed: {e}")
            
            # CONNECTION CHECK: Before page scan
            if not await self.ensure_connection(f"get_group_link_scan_{group_name}"):
                return None
            
            print(f"    🔍 Scanning for link...")
            link_text = await self.page.evaluate('''
                () => {
                    const inputs = document.querySelectorAll('input');
                    for (const input of inputs) {
                        if (input.value && input.value.includes('whatsapp.com')) {
                            return input.value;
                        }
                    }
                    
                    const elements = document.querySelectorAll('span, div, p');
                    for (const el of elements) {
                        const text = el.textContent || '';
                        if (text.includes('whatsapp.com') && 
                            !text.includes(':root') && 
                            !text.includes('{') &&
                            !text.includes('__fb') &&
                            text.length < 500) {
                            const match = text.match(/https?:\\/\\/[^\\s]+whatsapp\\.com[^\\s]*/);
                            if (match) {
                                return match[0];
                            }
                            return text.trim();
                        }
                    }
                    return null;
                }
            ''')
            
            if link_text and "whatsapp.com" in link_text:
                print(f"    ✅ Found link in page")
                return clean_whatsapp_link(link_text)
            
            print(f"    ❌ Could not get link after all methods")
            return None
                
        except Exception as e:
            print(f"  ❌ Error getting link: {e}")
            import traceback
            traceback.print_exc()
            return None
    
    # ============================================================
    # 5. UPDATE GROUP DESCRIPTION - WITH EXHAUSTIVE CONNECTION CHECKS
    # ============================================================

    async def update_group_description(self, group_name: str, description: str) -> bool:
        """Update the group description with EXHAUSTIVE connection checks"""
        
        # CONNECTION CHECK: Before starting
        if not await self.ensure_connection(f"update_desc_start_{group_name}"):
            print("❌ WhatsApp not connected. Cannot update description.")
            return False
        
        print(f"  📝 Updating description for: {group_name}")
        
        try:
            # CONNECTION CHECK: Before going back
            if not await self.ensure_connection(f"update_desc_back_{group_name}"):
                return False
            
            print(f"    🔍 Going back from invite section...")
            
            back_selectors = [
                '[aria-label="Back"]',
                'button[aria-label="Back"]',
                '[data-tab="2"][aria-label="Back"]',
                'header button:first-child'
            ]
            
            went_back = False
            for selector in back_selectors:
                # CONNECTION CHECK: During back selector iteration
                if not await self.ensure_connection(f"update_desc_back_selector_{selector[:20]}"):
                    continue
                
                try:
                    back_btn = await self.page.query_selector(selector)
                    if back_btn:
                        is_visible = await back_btn.is_visible()
                        if is_visible:
                            await back_btn.click()
                            went_back = True
                            print(f"    ✅ Clicked back button: {selector}")
                            break
                except:
                    continue
            
            if not went_back:
                print(f"    ⚠️ Could not find back button, trying header click...")
                try:
                    header = await self.page.query_selector('header')
                    if header:
                        await header.click()
                        went_back = True
                        print(f"    ✅ Clicked header to go back")
                except:
                    pass
            
            if not went_back:
                print(f"    ❌ Could not go back from invite section")
                return False
            
            await asyncio.sleep(2)
            
            # CONNECTION CHECK: After going back
            if not await self.ensure_connection(f"update_desc_after_back_{group_name}"):
                return False
            
            print(f"    🔍 Looking for edit button...")
            
            edit_clicked = False
            
            edit_selectors = [
                '[aria-label="Edit group description"]',
                'button[aria-label="Edit group description"]',
                '[data-testid="pencil-refreshed"]',
                '[data-testid="group-info-drawer-description-title-input-empty-placeholder"]'
            ]
            
            for selector in edit_selectors:
                # CONNECTION CHECK: During edit selector iteration
                if not await self.ensure_connection(f"update_desc_edit_{group_name}"):
                    continue
                
                try:
                    edit_btn = await self.page.query_selector(selector)
                    if edit_btn:
                        is_visible = await edit_btn.is_visible()
                        if is_visible:
                            await edit_btn.click()
                            edit_clicked = True
                            print(f"    ✅ Clicked edit button: {selector}")
                            break
                except:
                    continue
            
            if not edit_clicked:
                print(f"    🔍 Edit button not found, clicking description section...")
                desc_selectors = [
                    '[data-testid="group-info-drawer-description-container"]',
                    '[data-testid="group-description"]'
                ]
                
                for selector in desc_selectors:
                    # CONNECTION CHECK: During desc selector iteration
                    if not await self.ensure_connection(f"update_desc_click_{group_name}"):
                        continue
                    
                    try:
                        desc_section = await self.page.query_selector(selector)
                        if desc_section and await desc_section.is_visible():
                            await desc_section.click()
                            edit_clicked = True
                            print(f"    ✅ Clicked description section: {selector}")
                            break
                    except:
                        continue
            
            if not edit_clicked:
                print(f"    ❌ Could not find edit button or description")
                return False
            
            # CONNECTION CHECK: After clicking edit
            if not await self.ensure_connection(f"update_desc_after_edit_{group_name}"):
                return False
            
            print(f"    ⏳ Waiting 2 seconds for edit mode...")
            await asyncio.sleep(2)
            
            # CONNECTION CHECK: Before clearing
            if not await self.ensure_connection(f"update_desc_before_clear_{group_name}"):
                return False
            
            print(f"    🔍 Clearing existing content...")
            await self.page.keyboard.press('Control+A')
            await asyncio.sleep(0.5)
            await self.page.keyboard.press('Backspace')
            await asyncio.sleep(0.5)
            print(f"    ✅ Cleared existing content")
            
            # CONNECTION CHECK: Before typing
            if not await self.ensure_connection(f"update_desc_before_typing_{group_name}"):
                return False
            
            print(f"    📝 Typing description...")
            
            # Type with connection checks during long typing
            for char_index, char in enumerate(description):
                # Check connection every 100 characters
                if char_index % 100 == 0 and char_index > 0:
                    if not await self.ensure_connection(f"update_desc_typing_{char_index}_{group_name}"):
                        print("⚠️ Connection lost during typing. Waiting...")
                        await self.ensure_connection(f"update_desc_typing_reconnect_{char_index}_{group_name}")
                        print("✅ Connection restored. Continuing typing...")
                        continue
                
                await self.page.keyboard.type(char, delay=random.randint(5, 15))
            
            await asyncio.sleep(0.5)
            print(f"    ✅ Description typed")
            
            # CONNECTION CHECK: Before saving
            if not await self.ensure_connection(f"update_desc_before_save_{group_name}"):
                return False
            
            print(f"    🔍 Saving description with Enter...")
            await self.page.keyboard.press('Enter')
            await asyncio.sleep(2)
            print(f"    ✅ Description saved")
            
            return True
            
        except Exception as e:
            print(f"  ❌ Error updating description: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    # ============================================================
    # 6. PROCESS SINGLE GROUP - WITH EXHAUSTIVE CONNECTION CHECKS
    # ============================================================
    
    async def process_group(self, group_name: str) -> dict:
        """Process a single group with EXHAUSTIVE connection checks"""
        
        # CONNECTION CHECK: Before starting
        if not await self.ensure_connection(f"process_group_start_{group_name}"):
            print("❌ WhatsApp not connected. Cannot process group.")
            return {"group": group_name, "success": False}
        
        result = {
            "group": group_name,
            "success": False,
            "link": None,
            "description_updated": False,
            "category": "core"
        }
        
        try:
            # CONNECTION CHECK: Before opening group
            if not await self.ensure_connection(f"process_group_open_{group_name}"):
                return result
            
            if not await self.open_group(group_name):
                print(f"  ❌ Failed to open group: {group_name}")
                return result
            
            await asyncio.sleep(DELAYS["short"])
            
            # CONNECTION CHECK: Before getting link
            if not await self.ensure_connection(f"process_group_get_link_{group_name}"):
                return result
            
            link = await self.get_group_link(group_name)
            if not link:
                print(f"  ❌ No link found for: {group_name}")
                return result
            
            result["link"] = link
            print(f"  ✅ Link retrieved successfully")
            
            description = generate_group_description(group_name, link)
            
            # CONNECTION CHECK: Before updating description
            if not await self.ensure_connection(f"process_group_update_desc_{group_name}"):
                return result
            
            if await self.update_group_description(group_name, description):
                result["description_updated"] = True
                print(f"  ✅ Description updated")
            else:
                print(f"  ⚠️ Description update failed")
            
            category = get_group_category(group_name)
            result["category"] = category
            platform = get_group_platform(group_name)
            
            # CONNECTION CHECK: Before saving to file
            if not await self.ensure_connection(f"process_group_save_{group_name}"):
                print("⚠️ Connection lost before saving. Will try anyway...")
            
            self.links_manager.add_or_update_group(
                group_name=group_name,
                url=link,
                description=description,
                platform=platform,
                category=category
            )
            
            result["success"] = True
            print(f"  📂 Category: {category}")
            return result
            
        except Exception as e:
            print(f"  ❌ Error processing {group_name}: {e}")
            import traceback
            traceback.print_exc()
            return result
    
    # ============================================================
    # 7. MANAGE ALL GROUPS - WITH EXHAUSTIVE CONNECTION CHECKS
    # ============================================================
    
    async def manage_all_groups(self):
        """Run all management tasks with EXHAUSTIVE connection checks"""
        
        # CONNECTION CHECK: Before starting
        if not await self.ensure_connection("manage_all_groups_start"):
            print("❌ WhatsApp not connected. Cannot start group management.")
            return
        
        print("\n" + "=" * 60)
        print("🔧 RUNNING GROUP MANAGEMENT")
        print("=" * 60)
        print(f"📱 Core groups to manage: {len(CORE_GROUPS)}")
        print("=" * 60)
        
        results = {
            "processed": 0,
            "links_found": 0,
            "descriptions_updated": 0,
            "failed": [],
            "categories": {}
        }
        
        for i, group_name in enumerate(CORE_GROUPS):
            # ============================================================
            # CONNECTION CHECK: Before EACH group (EXHAUSTIVE)
            # ============================================================
            if not await self.ensure_connection(f"manage_all_groups_before_{group_name}"):
                print("⏳ Connection lost during group management. Waiting for reconnection...")
                await self.ensure_connection(f"manage_all_groups_reconnect_{group_name}")
                print("✅ Connection restored. Resuming group management...")
                # Continue to next group after reconnection
                continue
            
            print(f"\n{'='*60}")
            print(f"📱 Processing: {group_name}")
            print(f"{'='*60}")
            
            result = await self.process_group(group_name)
            
            # CONNECTION CHECK: After processing group
            if not await self.ensure_connection(f"manage_all_groups_after_{group_name}"):
                print("⚠️ Connection lost after processing. Checking status...")
                # We'll continue to next group if possible
            
            if result["success"]:
                results["processed"] += 1
                if result["link"]:
                    results["links_found"] += 1
                if result["description_updated"]:
                    results["descriptions_updated"] += 1
                
                cat = result.get("category", "core")
                results["categories"][cat] = results["categories"].get(cat, 0) + 1
            else:
                results["failed"].append(group_name)
            
            if i < len(CORE_GROUPS) - 1:
                # ============================================================
                # CONNECTION CHECK: Before waiting (EXHAUSTIVE)
                # ============================================================
                if not await self.ensure_connection(f"manage_all_groups_wait_{group_name}"):
                    print("⏳ Connection lost before wait. Waiting for reconnection...")
                    await self.ensure_connection(f"manage_all_groups_wait_reconnect_{group_name}")
                    print("✅ Connection restored. Resuming...")
                    continue
                
                delay = random.uniform(2, DELAYS["between_groups"] + 2)
                print(f"⏳ Waiting {delay:.1f}s before next group...")
                await asyncio.sleep(delay)
        
        # CONNECTION CHECK: Before final summary
        if not await self.ensure_connection("manage_all_groups_summary"):
            print("⚠️ Connection lost during final summary. Some stats may be incomplete.")
        
        # Print summary
        print("\n" + "=" * 60)
        print("📊 MANAGEMENT SUMMARY")
        print("=" * 60)
        print(f"✅ Groups processed: {results['processed']}")
        print(f"🔗 Links found/saved: {results['links_found']}")
        print(f"📝 Descriptions updated: {results['descriptions_updated']}")
        
        print("\n📂 Categories:")
        for cat, count in results["categories"].items():
            print(f"  - {cat.upper()}: {count} groups")
        
        if results["failed"]:
            print(f"\n❌ Failed: {len(results['failed'])} groups")
            for g in results["failed"]:
                print(f"   - {g}")
        
        print("")
        print("📊 CONNECTION MONITORING STATISTICS")
        print("-" * 40)
        print(f"Total connection checks: {self.connection_stats['checks_performed']}")
        print(f"Disconnections detected: {self.connection_stats['disconnections_detected']}")
        print(f"Reconnections succeeded: {self.connection_stats['reconnections_succeeded']}")
        print(f"Operations paused: {self.connection_stats['operations_paused']}")
        print("=" * 60)
        
        all_groups = self.links_manager.get_all_groups()
        print(f"\n📋 Total groups in data/links/group_links.json: {len(all_groups)}")
        for g in all_groups[:5]:
            print(f"  - [{g.get('category', 'core')}] {g.get('name')}: {g.get('url')[:40]}...")
        if len(all_groups) > 5:
            print(f"  ... and {len(all_groups) - 5} more")
        print("=" * 60)
        
        return results


# ============================================================
# MAIN ENTRY POINT - FOR STANDALONE USE
# ============================================================

async def main():
    """Main entry point for standalone testing"""
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)
        context = await browser.new_context(
            viewport={'width': 1280, 'height': 800},
            user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        )
        page = await context.new_page()
        
        # Initialize manager (no login manager for standalone)
        manager = GroupManager()
        manager.set_page(page, context)
        
        # Start the manager (starts background health monitor)
        await manager.start()
        
        # Navigate to WhatsApp Web
        await page.goto("https://web.whatsapp.com")
        print("📱 Please scan the QR code to login...")
        print("⏳ Waiting for WhatsApp to load...")
        
        # Wait for WhatsApp to load
        await page.wait_for_selector('div[data-testid="chat-list"]', timeout=120000)
        print("✅ WhatsApp loaded successfully!")
        
        try:
            # Manage all groups
            await manager.manage_all_groups()
            
        except KeyboardInterrupt:
            print("\n\n⏹️ Stopped by user")
        except Exception as e:
            print(f"\n❌ Error: {e}")
            import traceback
            traceback.print_exc()
        
        finally:
            # Stop the manager
            await manager.stop()
            
            print("\n📊 Management complete!")
            print(f"📊 Connection checks performed: {manager.connection_stats['checks_performed']}")
            print(f"   Disconnections detected: {manager.connection_stats['disconnections_detected']}")
            print(f"   Reconnections succeeded: {manager.connection_stats['reconnections_succeeded']}")
            
            # Keep browser open for a moment
            print("\n⏳ Press Ctrl+C to close browser...")
            await asyncio.sleep(10)
            await browser.close()

if __name__ == "__main__":
    asyncio.run(main())