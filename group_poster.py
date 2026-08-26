"""
Group Poster Module with Data Collection
========================================
Handles all WhatsApp group posting functionality with data collection:
- Loading products from JSON files
- Opening groups
- Posting messages with line breaks
- Smart link preview waiting (detects when preview loads)
- Product status management
- Posts ONE product per run (configurable)
- Tracks failed groups and auto-removes after 10 failures
- DATA COLLECTION: Stays in groups longer to collect chat data
- Downloads recent chat history
- Stores all data in SQLite database for analysis
- CONNECTION MONITORING: PAUSES ALL ACTIVITY when disconnected, resumes after reconnection
- EXHAUSTIVE connection checking at EVERY critical step
"""

import json
import random
import asyncio
from pathlib import Path
from datetime import datetime, timedelta
from typing import List, Optional, Dict, Any
from playwright.async_api import async_playwright
import re

# ============================================================
# IMPORT DATABASE LOGIC
# ============================================================

from db_logic import DatabaseManager

# ============================================================
# IMPORT TARGET GROUPS
# ============================================================

from target_groups import TARGET_GROUPS

# ============================================================
# CONFIGURATION
# ============================================================

BASE_DIR = Path(__file__).parent
DATA_DIR = BASE_DIR / "data"
PRODUCTS_DIR = DATA_DIR / "products"
FAILED_GROUPS_FILE = DATA_DIR / "failed_groups.json"
DB_FILE = DATA_DIR / "whatsapp_data.db"

# Product files
WA_PRODUCTS_FILE = PRODUCTS_DIR / "wa_products.json"
INSTAGRAM_POSTS_FILE = PRODUCTS_DIR / "instagram_posts.json"
FACEBOOK_POSTS_FILE = PRODUCTS_DIR / "facebook_posts.json"

# Create directories
PRODUCTS_DIR.mkdir(parents=True, exist_ok=True)
DATA_DIR.mkdir(parents=True, exist_ok=True)

# ============================================================
# TIMING CONFIGURATION
# ============================================================

# Typing delays (milliseconds per character - SLOW & HUMAN)
HUMAN_TYPING_DELAY_MIN = 10
HUMAN_TYPING_DELAY_MAX = 20

# Page interaction delays
SEARCH_WAIT = 1
OPEN_WAIT = 1
FIND_COMPOSE_WAIT = 1
AFTER_TYPING_WAIT = 1
SEND_CONFIRM_WAIT = 1
BETWEEN_GROUPS_WAIT = 1
BETWEEN_PRODUCTS_WAIT = 1
RETRY_DELAY = 2

# Link preview delay (seconds) - Maximum wait time
LINK_PREVIEW_DELAY = 5

# DATA COLLECTION CONFIGURATION
STAY_IN_GROUP_DURATION = 2  # Seconds to stay in group after posting
SCROLL_COUNT = 1  # Number of scrolls to perform for chat history
MAX_MESSAGES_TO_COLLECT = 500  # Maximum messages to collect per group
DATA_COLLECTION_INTERVAL = 2  # Seconds between scrolls

# Number of products to post per run (1 = post one product to all groups)
POSTS_PER_RUN = 6

# Group failure threshold (auto-remove after this many failures)
MAX_GROUP_FAILURES = 100

# Connection check intervals (seconds)
CONNECTION_CHECK_INTERVAL = 30  # Check connection every 30 seconds during long operations
CONNECTION_RETRY_INTERVAL = 5  # Wait 5 seconds between reconnection attempts

# ============================================================
# FAILED GROUPS TRACKER
# ============================================================

class FailedGroupsTracker:
    """Tracks groups that fail to open and auto-removes them"""
    
    def __init__(self, data_dir: Path = DATA_DIR):
        self.data_dir = data_dir
        self.failed_groups_file = data_dir / "failed_groups.json"
        self.failed_groups = self._load_failed_groups()
    
    def _load_failed_groups(self) -> Dict[str, dict]:
        """Load failed groups from JSON file"""
        if self.failed_groups_file.exists():
            try:
                with open(self.failed_groups_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except:
                return {}
        return {}
    
    def _save_failed_groups(self):
        """Save failed groups to JSON file"""
        with open(self.failed_groups_file, 'w', encoding='utf-8') as f:
            json.dump(self.failed_groups, f, indent=2, ensure_ascii=False)
    
    def record_failure(self, group_name: str):
        """Record a failure for a group"""
        if group_name not in self.failed_groups:
            self.failed_groups[group_name] = {
                "failures": 0,
                "first_failure": datetime.now().isoformat(),
                "last_failure": datetime.now().isoformat(),
                "status": "active"
            }
        
        self.failed_groups[group_name]["failures"] += 1
        self.failed_groups[group_name]["last_failure"] = datetime.now().isoformat()
        
        if self.failed_groups[group_name]["failures"] >= MAX_GROUP_FAILURES:
            self.failed_groups[group_name]["status"] = "pending_removal"
            print(f"  ⚠️ Group '{group_name}' has failed {self.failed_groups[group_name]['failures']} times. Marked for removal.")
        
        self._save_failed_groups()
    
    def record_success(self, group_name: str):
        """Record a success for a group (reset failures)"""
        if group_name in self.failed_groups:
            self.failed_groups[group_name]["failures"] = 0
            self.failed_groups[group_name]["status"] = "active"
            self.failed_groups[group_name]["last_success"] = datetime.now().isoformat()
            self._save_failed_groups()
    
    def get_failed_groups(self, status: str = None) -> List[str]:
        """Get groups with failures"""
        if status:
            return [name for name, data in self.failed_groups.items() if data.get("status") == status]
        return list(self.failed_groups.keys())
    
    def get_groups_to_remove(self) -> List[str]:
        """Get groups that have reached the failure threshold"""
        return self.get_failed_groups("pending_removal")
    
    def remove_group(self, group_name: str) -> bool:
        """Remove a group from the failed groups list"""
        if group_name in self.failed_groups:
            self.failed_groups[group_name]["status"] = "removed"
            self.failed_groups[group_name]["removed_at"] = datetime.now().isoformat()
            self._save_failed_groups()
            return True
        return False
    
    def is_group_failing(self, group_name: str) -> bool:
        """Check if a group is currently failing"""
        if group_name in self.failed_groups:
            return self.failed_groups[group_name]["failures"] > 0
        return False
    
    def get_failure_count(self, group_name: str) -> int:
        """Get the failure count for a group"""
        if group_name in self.failed_groups:
            return self.failed_groups[group_name]["failures"]
        return 0
    
    def get_summary(self) -> dict:
        """Get a summary of failed groups"""
        total = len(self.failed_groups)
        pending_removal = len(self.get_groups_to_remove())
        active = len([g for g in self.failed_groups.values() if g.get("status") == "active"])
        removed = len([g for g in self.failed_groups.values() if g.get("status") == "removed"])
        
        return {
            "total": total,
            "active": active,
            "pending_removal": pending_removal,
            "removed": removed
        }
    
    def print_summary(self):
        """Print a summary of failed groups"""
        summary = self.get_summary()
        print("\n" + "=" * 60)
        print("📊 FAILED GROUPS SUMMARY")
        print("=" * 60)
        print(f"Total tracked groups: {summary['total']}")
        print(f"  ✅ Active (recovering): {summary['active']}")
        print(f"  ⚠️ Pending removal: {summary['pending_removal']}")
        print(f"  🗑️ Removed: {summary['removed']}")
        
        if summary['pending_removal'] > 0:
            print("\n⚠️ Groups pending removal (will be removed from target list):")
            for group in self.get_groups_to_remove():
                failures = self.failed_groups[group]["failures"]
                print(f"  - {group} ({failures} failures)")
        print("=" * 60)

# ============================================================
# PRODUCT LOADER
# ============================================================

class ProductLoader:
    """Load products from multiple JSON files"""
    
    def __init__(self):
        self.products = []
        self.posted_count = 0
        self.failed_count = 0
        self.reset_count = 0
        
        self.loaded_files = {
            "wa": WA_PRODUCTS_FILE,
            "instagram": INSTAGRAM_POSTS_FILE,
            "facebook": FACEBOOK_POSTS_FILE
        }
    
    def load_all_products(self, status: str = "pending") -> List[dict]:
        """Load ALL pending products from all JSON files"""
        all_products = []
        
        for source, file_path in self.loaded_files.items():
            products = self._load_from_file(file_path, source)
            all_products.extend(products)
        
        if status:
            all_products = [p for p in all_products if p.get("status") == status]
        
        random.shuffle(all_products)
        self.products = all_products
        
        print(f"\n📦 Total pending products: {len(all_products)}")
        print(f"   - WhatsApp: {len([p for p in all_products if p.get('source') == 'wa'])}")
        print(f"   - Instagram: {len([p for p in all_products if p.get('source') == 'instagram'])}")
        print(f"   - Facebook: {len([p for p in all_products if p.get('source') == 'facebook'])}")
        
        return all_products
    
    def _load_from_file(self, file_path: Path, source: str) -> List[dict]:
        """Load products from a single JSON file"""
        if not file_path.exists():
            print(f"⚠️ File not found: {file_path}")
            return []
        
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            products = []
            
            if source == "wa":
                raw_products = data.get("products", [])
                for p in raw_products:
                    p["source"] = "wa"
                    p["product_type"] = "wa"
                    products.append(p)
            
            elif source == "instagram":
                raw_posts = data.get("posts", [])
                raw_reels = data.get("reels", [])
                for p in raw_posts + raw_reels:
                    p["source"] = "instagram"
                    p["product_type"] = "instagram"
                    if not p.get("description") and p.get("caption"):
                        p["description"] = p.get("caption", "")
                    products.append(p)
            
            elif source == "facebook":
                raw_posts = data.get("posts", [])
                for p in raw_posts:
                    p["source"] = "facebook"
                    p["product_type"] = "facebook"
                    if not p.get("description") and p.get("caption"):
                        p["description"] = p.get("caption", "")
                    products.append(p)
            
            print(f"✅ Loaded {len(products)} products from {source}")
            return products
            
        except Exception as e:
            print(f"❌ Error loading {file_path}: {e}")
            return []
    
    def get_all_pending(self) -> List[dict]:
        """Get all pending products"""
        return [p for p in self.products if p.get("status") == "pending"]
    
    def get_pending_count(self) -> int:
        """Get count of pending products"""
        return len([p for p in self.products if p.get("status") == "pending"])
    
    def mark_as_posted(self, product: dict) -> bool:
        """Mark a product as posted in its source file"""
        source = product.get("source")
        product_id = product.get("id")
        
        if not source or not product_id:
            print(f"❌ Missing source or ID for product")
            return False
        
        file_path = self.loaded_files.get(source)
        if not file_path:
            print(f"❌ Unknown source: {source}")
            return False
        
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            updated = False
            
            if source == "wa":
                products = data.get("products", [])
                for p in products:
                    if p.get("id") == product_id:
                        p["status"] = "posted"
                        p["posted_date"] = datetime.now().strftime("%Y-%m-%d")
                        p["posted_time"] = datetime.now().strftime("%H:%M:%S")
                        updated = True
                        break
                data["products"] = products
            
            elif source == "instagram":
                posts = data.get("posts", [])
                for p in posts:
                    if p.get("id") == product_id:
                        p["status"] = "posted"
                        p["posted_date"] = datetime.now().strftime("%Y-%m-%d")
                        p["posted_time"] = datetime.now().strftime("%H:%M:%S")
                        updated = True
                        break
                if not updated:
                    reels = data.get("reels", [])
                    for p in reels:
                        if p.get("id") == product_id:
                            p["status"] = "posted"
                            p["posted_date"] = datetime.now().strftime("%Y-%m-%d")
                            p["posted_time"] = datetime.now().strftime("%H:%M:%S")
                            updated = True
                            break
                    data["reels"] = reels
                data["posts"] = posts
            
            elif source == "facebook":
                posts = data.get("posts", [])
                for p in posts:
                    if p.get("id") == product_id:
                        p["status"] = "posted"
                        p["posted_date"] = datetime.now().strftime("%Y-%m-%d")
                        p["posted_time"] = datetime.now().strftime("%H:%M:%S")
                        updated = True
                        break
                data["posts"] = posts
            
            if not updated:
                print(f"❌ Product {product_id} not found in {source}")
                return False
            
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            
            for p in self.products:
                if p.get("id") == product_id and p.get("source") == source:
                    p["status"] = "posted"
                    p["posted_date"] = datetime.now().strftime("%Y-%m-%d")
                    p["posted_time"] = datetime.now().strftime("%H:%M:%S")
                    break
            
            self.posted_count += 1
            return True
            
        except Exception as e:
            print(f"❌ Error marking product as posted: {e}")
            self.failed_count += 1
            return False
    
    def reset_all_products(self) -> bool:
        """Reset ALL products to pending (fresh start)"""
        print("\n🔄 Resetting all products to pending...")
        
        reset_success = True
        
        for source, file_path in self.loaded_files.items():
            if not file_path.exists():
                continue
            
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                
                if source == "wa":
                    for p in data.get("products", []):
                        p["status"] = "pending"
                        p["posted_date"] = None
                        p["posted_time"] = None
                
                elif source == "instagram":
                    for p in data.get("posts", []):
                        p["status"] = "pending"
                        p["posted_date"] = None
                        p["posted_time"] = None
                    for p in data.get("reels", []):
                        p["status"] = "pending"
                        p["posted_date"] = None
                        p["posted_time"] = None
                
                elif source == "facebook":
                    for p in data.get("posts", []):
                        p["status"] = "pending"
                        p["posted_date"] = None
                        p["posted_time"] = None
                
                if "total_posted" in data:
                    data["total_posted"] = 0
                if "total_pending" in data:
                    data["total_pending"] = len(data.get("posts", []) or data.get("products", []))
                
                with open(file_path, 'w', encoding='utf-8') as f:
                    json.dump(data, f, indent=2, ensure_ascii=False)
                
                print(f"   ✅ Reset {source} products")
                self.reset_count += 1
                
            except Exception as e:
                print(f"   ❌ Failed to reset {source}: {e}")
                reset_success = False
        
        if reset_success:
            self.load_all_products(status="pending")
            print(f"✅ All products reset! Total pending: {self.get_pending_count()}")
        
        return reset_success
    
    def get_product_message(self, product: dict, contact_name: str = "") -> str:
        """Create a marketing message with optional personalization"""
        name = product.get("product_name") or product.get("id") or "Product"
        description = product.get("description") or product.get("caption") or ""
        url = product.get("url") or ""
        source = product.get("source", "unknown")
        
        if not description:
            description = f"Check out this {source} post!"
        
        call_to_actions = [
            "DM to order | Inbox for inquiries",
            "Order via DM | Chat with us",
            "Send a message to order",
            "DM for pricing and availability",
            "Inbox us to secure yours",
            "Order now - limited stock available"
        ]
        
        promos = [
            "Quality you can trust.",
            "Don't miss out on this one!",
            "Perfect for any occasion.",
            "Designed with you in mind.",
            "Stand out from the crowd.",
            "Experience the difference."
        ]
        
        headers = [
            "[ PREMIUM SELECTION ]",
            "[ LIMITED EDITION ]",
            "[ LIFESTYLE PICK ]",
            "[ FLASH SALE ]",
            "[ NEW ARRIVAL ]",
            "[ BOLD STATEMENT ]"
        ]
        
        header = random.choice(headers)
        cta = random.choice(call_to_actions)
        promo = random.choice(promos)
        
        hashtag_name = ''.join(c for c in name if c.isalnum())
        
        parts = []
        if contact_name:
            parts.append(f"Hi {contact_name}!")
        parts.extend([
            header,
            f"Product: {name}",
            description,
            f"Link: {url}",
            promo,
            cta,
            f"#{hashtag_name} #Kenya #Tulia"
        ])
        
        return "\n".join(parts)
    
    def has_url(self, message: str) -> bool:
        return "http" in message or "www." in message
    
    def get_stats(self) -> dict:
        return {
            "posted": self.posted_count,
            "failed": self.failed_count,
            "reset_count": self.reset_count,
            "total": self.posted_count + self.failed_count,
            "pending": self.get_pending_count()
        }

# ============================================================
# CONNECTION LOST EXCEPTION
# ============================================================

class ConnectionLostError(Exception):
    """Raised when WhatsApp connection is lost during an operation"""
    pass

# ============================================================
# GROUP POSTER CLASS (ENHANCED WITH EXHAUSTIVE CONNECTION MONITORING)
# ============================================================

class GroupPoster:
    """
    Handles all group posting operations with EXHAUSTIVE connection monitoring.
    
    EVERY critical operation checks connection status before proceeding.
    Connection checks are performed at:
    - Start of every public method
    - Before and after every major operation
    - During long-running operations (scrolling, waiting)
    - Before database operations
    - Before marking products as posted
    - Before and after sending messages
    - During data collection
    """
    
    def __init__(self, page, context, login_manager=None):
        """
        Initialize GroupPoster
        
        Args:
            page: Playwright page object
            context: Playwright context object  
            login_manager: LoginManager instance for connection monitoring
        """
        self.page = page
        self.context = context
        self.login_manager = login_manager
        
        # Validate login_manager
        if login_manager:
            print("✅ Connection monitoring ENABLED - exhaustive checks active")
        else:
            print("⚠️ No login manager - connection monitoring DISABLED")
            print("   The bot will NOT pause on disconnection!")
        
        self.product_loader = ProductLoader()
        self.failed_tracker = FailedGroupsTracker()
        self.db = DatabaseManager()
        self.is_running = False
        self.current_product = None
        self.collected_messages = []
        self.is_paused = False
        self._connection_check_counter = 0  # For periodic checks during loops
        
        # Connection monitoring stats
        self.connection_stats = {
            "checks_performed": 0,
            "disconnections_detected": 0,
            "reconnections_succeeded": 0,
            "operations_paused": 0
        }
    
    # ============================================================
    # EXHAUSTIVE CONNECTION MONITORING
    # ============================================================

    async def ensure_connection(self, context: str = "unknown") -> bool:
        """
        EXHAUSTIVE connection check - RAISES EXCEPTION if disconnected.
        
        Args:
            context: Description of where the check is being called from
            
        Returns:
            bool: True if connected
            
        Raises:
            ConnectionLostError: If connection is lost (will wait for reconnection first)
        """
        self._connection_check_counter += 1
        self.connection_stats["checks_performed"] += 1
        
        if not self.login_manager:
            return True
        
        try:
            is_connected = await self.login_manager.check_connection()
            
            if is_connected:
                # If we were paused, clear the flag
                if self.is_paused:
                    self.is_paused = False
                    print(f"✅ Connection restored (checked from: {context})")
                return True
            
            # ============================================================
            # DISCONNECTED - PAUSE ALL ACTIVITY AND RAISE EXCEPTION
            # ============================================================
            self.is_paused = True
            self.connection_stats["disconnections_detected"] += 1
            self.connection_stats["operations_paused"] += 1
            
            print("\n" + "=" * 70)
            print(f"⏸️  CONNECTION LOST - PAUSING ALL ACTIVITY")
            print(f"   Location: {context}")
            print(f"   Time: {datetime.now().strftime('%H:%M:%S')}")
            print("=" * 70)
            print("   WhatsApp connection lost. All operations STOPPED.")
            print("   Waiting for reconnection...")
            print("=" * 70 + "\n")
            
            # ============================================================
            # CLEAR ANY PENDING KEYBOARD/MOUSE ACTIONS
            # ============================================================
            try:
                # Release all keys to stop any ongoing typing
                await self.page.keyboard.up('Shift')
                await self.page.keyboard.up('Enter')
                await self.page.keyboard.up('Control')
                await self.page.keyboard.up('Alt')
                await asyncio.sleep(0.5)
                
                # Try to click somewhere neutral to stop typing
                try:
                    await self.page.click('body', timeout=1000)
                except:
                    pass
                    
                print("   ✅ Stopped all keyboard/mouse actions")
            except Exception as e:
                print(f"   ⚠️ Could not clear actions: {e}")
            
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
                print("   Waiting 3 seconds to stabilize...")
                print("=" * 70 + "\n")
                
                # Wait for WhatsApp to stabilize
                await asyncio.sleep(3)
                
                # Clear any leftover input
                try:
                    await self.page.keyboard.press('Escape')
                    await asyncio.sleep(0.5)
                    await self.page.keyboard.press('Escape')
                    await asyncio.sleep(0.5)
                except:
                    pass
                
                # ============================================================
                # RAISE EXCEPTION TO ABORT THE CURRENT OPERATION
                # ============================================================
                raise ConnectionLostError(f"Connection was lost and restored at {context}")
            
            # If we get here, reconnection failed
            print("❌ Failed to reconnect after waiting")
            return False
            
        except ConnectionLostError:
            # Re-raise ConnectionLostError
            raise
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
        
        try:
            await self.ensure_connection(f"Before: {operation_name}")
            return True
        except ConnectionLostError:
            print(f"⚠️ Cannot perform '{operation_name}' - connection lost")
            return False
    
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
            try:
                await self.ensure_connection(f"wait_if_paused: {context}")
                return True
            except ConnectionLostError:
                return False
        
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
        try:
            # Check connection before operation
            await self.ensure_connection(f"Before: {operation_name}")
            
            # Execute the operation
            result = await operation_func(*args, **kwargs)
            
            # Check connection after operation
            await self.ensure_connection(f"After: {operation_name}")
            
            return result
            
        except ConnectionLostError as e:
            print(f"⚠️ Connection lost during {operation_name}: {e}")
            return None
        except Exception as e:
            print(f"⚠️ Error during {operation_name}: {e}")
            # Check if error was due to connection issues
            if self.login_manager:
                try:
                    await self.ensure_connection(f"Error recovery: {operation_name}")
                    return None
                except ConnectionLostError:
                    return None
            raise
    
    # ============================================================
    # DATA COLLECTION METHODS - WITH EXHAUSTIVE CONNECTION CHECKS
    # ============================================================
    
    async def collect_chat_history(self, group_name: str, group_id: int) -> int:
        """
        Collect chat history with EXHAUSTIVE connection checking.
        Checks connection BEFORE, DURING, and AFTER every scroll.
        If connection is lost, aborts and returns what was collected.
        """
        
        try:
            # CONNECTION CHECK: Before starting
            await self.ensure_connection("collect_chat_history_start")
            
            print(f"  📥 Collecting chat history from: {group_name}")
            print(f"    ⏳ Staying for {STAY_IN_GROUP_DURATION}s to collect data...")
            
            messages_collected = 0
            unique_messages = set()
            
            # Wait for chat to load
            await asyncio.sleep(3)
            
            # CONNECTION CHECK: After loading
            await self.ensure_connection("collect_chat_history_after_load")
            
            # Scroll to load more messages
            for i in range(SCROLL_COUNT):
                # ============================================================
                # CONNECTION CHECK: Before EACH scroll (EXHAUSTIVE)
                # ============================================================
                await self.ensure_connection(f"collect_chat_history_scroll_{i+1}")
                
                print(f"    📜 Scrolling {i+1}/{SCROLL_COUNT}...")
                
                # Try multiple scroll methods
                try:
                    await self.page.evaluate("window.scrollBy(0, -500)")
                except:
                    pass
                
                try:
                    await self.page.mouse.wheel(delta_x=0, delta_y=-500)
                except:
                    pass
                
                try:
                    await self.page.keyboard.press('PageUp')
                except:
                    pass
                
                await asyncio.sleep(DATA_COLLECTION_INTERVAL)
                
                # CONNECTION CHECK: After scrolling, before extracting messages
                await self.ensure_connection(f"collect_chat_history_extract_{i+1}")
                
                # ============================================================
                # FIXED: Better message extraction
                # ============================================================
                
                # Try multiple selectors for message containers
                message_selectors = [
                    'div[data-testid="msg-container"]',
                    'div[data-testid="message-container"]',
                    'div[role="row"]',
                    'div[data-testid="msg-wrapper"]',
                    'div[data-testid="message-text"]'
                ]
                
                message_elements = []
                used_selector = None
                
                for selector in message_selectors:
                    try:
                        elements = await self.page.query_selector_all(selector)
                        if elements and len(elements) > 0:
                            message_elements = elements
                            used_selector = selector
                            if i == 0:
                                print(f"    ✅ Found {len(elements)} elements using: {selector}")
                            break
                    except:
                        continue
                
                if not message_elements:
                    # Fallback: look for any div with text that might be a message
                    try:
                        message_elements = await self.page.query_selector_all('div[dir="auto"]')
                        if message_elements and i == 0:
                            print(f"    ✅ Using text-based extraction: found {len(message_elements)} elements")
                    except:
                        pass
                
                if not message_elements:
                    if i % 3 == 0:
                        print(f"    ⚠️ No messages found on scroll {i+1}")
                    continue
                
                # Extract each message
                for element_index, element in enumerate(message_elements):
                    # CONNECTION CHECK: During message extraction (every 10 messages)
                    if element_index % 10 == 0:
                        await self.ensure_connection(f"collect_chat_history_message_{messages_collected}")
                    
                    try:
                        # ============================================================
                        # FIXED: Better text extraction
                        # ============================================================
                        
                        # Try multiple ways to get the text
                        text = None
                        
                        # Method 1: Direct text content
                        try:
                            text = await element.text_content()
                        except:
                            pass
                        
                        # Method 2: Inner text (better for visible text)
                        if not text or not text.strip():
                            try:
                                text = await element.inner_text()
                            except:
                                pass
                        
                        # Method 3: Get from specific message-text child
                        if not text or not text.strip():
                            try:
                                text_el = await element.query_selector('div[data-testid="message-text"]')
                                if text_el:
                                    text = await text_el.text_content()
                            except:
                                pass
                        
                        # Method 4: Get from any span with text
                        if not text or not text.strip():
                            try:
                                spans = await element.query_selector_all('span')
                                for span in spans:
                                    span_text = await span.text_content()
                                    if span_text and span_text.strip() and len(span_text.strip()) > 2:
                                        text = span_text
                                        break
                            except:
                                pass
                        
                        # Skip if no text
                        if not text or not text.strip():
                            continue
                        
                        text = text.strip()
                        
                        # Skip short messages and date headers
                        if len(text) < 2:
                            continue
                        
                        # Skip common WhatsApp UI text
                        skip_texts = [
                            "Today", "Yesterday", "Messages", "Chat", 
                            "Search", "Type a message", "Click to chat",
                            "📷", "🎤", "😊", "👍", "❤️", "😂", "😮", "😢", "😡"
                        ]
                        if text in skip_texts:
                            continue
                        
                        # Skip if it looks like a timestamp only
                        if re.match(r'^\d{1,2}:\d{2}\s*(AM|PM)?$', text):
                            continue
                        
                        # ============================================================
                        # Extract sender info
                        # ============================================================
                        sender = "Unknown"
                        try:
                            sender_el = await element.query_selector('div[data-testid="message-author"]')
                            if sender_el:
                                sender_text = await sender_el.text_content()
                                if sender_text and sender_text.strip():
                                    sender = sender_text.strip()
                        except:
                            pass
                        
                        # Check if message is from us
                        is_ours = False
                        try:
                            own_el = await element.query_selector('div[data-testid="msg-own"]')
                            if own_el:
                                is_ours = True
                        except:
                            pass
                        
                        # Extract timestamp
                        timestamp = datetime.now()
                        try:
                            time_el = await element.query_selector('div[data-testid="message-timestamp"]')
                            if time_el:
                                time_text = await time_el.text_content()
                                if time_text:
                                    timestamp = self._parse_whatsapp_time(time_text)
                        except:
                            pass
                        
                        # Create unique ID for deduplication
                        msg_id = f"{sender}_{text[:50]}_{timestamp.isoformat()}"
                        
                        if msg_id not in unique_messages:
                            unique_messages.add(msg_id)
                            
                            # CONNECTION CHECK: Before database save (every 50 messages)
                            if messages_collected % 50 == 0:
                                await self.ensure_connection(f"collect_chat_history_db_save_{messages_collected}")
                            
                            # Save to database
                            self.db.save_message(
                                group_id=group_id,
                                sender=sender,
                                message=text,
                                timestamp=timestamp,
                                is_from_us=is_ours,
                                message_type="text"
                            )
                            
                            messages_collected += 1
                            
                            # Debug: Print first few messages
                            if messages_collected <= 5:
                                print(f"      📝 Sample {messages_collected}: {sender[:15]}: {text[:50]}...")
                            
                            if messages_collected >= MAX_MESSAGES_TO_COLLECT:
                                break
                    
                    except Exception as e:
                        # Don't stop on individual message errors
                        continue
                
                if messages_collected >= MAX_MESSAGES_TO_COLLECT:
                    print(f"    ✅ Reached max messages ({MAX_MESSAGES_TO_COLLECT})")
                    break
                
                if i % 5 == 0:
                    print(f"    📊 Collected {messages_collected} messages so far...")
            
            # CONNECTION CHECK: Before database update
            await self.ensure_connection("collect_chat_history_final_update")
            
            self.db.update_group_activity(group_id, messages_collected)
            
            print(f"  ✅ Collected {messages_collected} messages from {group_name}")
            
            # CONNECTION CHECK: Before final scroll
            await self.ensure_connection("collect_chat_history_final_scroll")
            
            await self.page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            await asyncio.sleep(1)
            
            return messages_collected
            
        except ConnectionLostError as e:
            print(f"  ⚠️ Connection lost during data collection: {e}")
            print(f"  🔄 Data collection aborted. Will retry on next run.")
            return 0
        except Exception as e:
            print(f"  ❌ Error collecting chat history: {e}")
            import traceback
            traceback.print_exc()
            return 0
    
    def _parse_whatsapp_time(self, time_text: str) -> datetime:
        """Parse WhatsApp time format to datetime"""
        try:
            # WhatsApp web shows relative times like "11:30 AM" or "Yesterday" or "2:30 PM"
            # Try to parse relative times
            now = datetime.now()
            
            if "Yesterday" in time_text:
                return now - timedelta(days=1)
            elif "Today" in time_text:
                return now
            else:
                # Try to parse time like "11:30 AM"
                try:
                    time_parts = time_text.strip().split()
                    if len(time_parts) >= 2:
                        time_str = time_parts[0]
                        ampm = time_parts[1] if len(time_parts) > 1 else ""
                        
                        # Parse time
                        hour, minute = map(int, time_str.split(':'))
                        if ampm.lower() == 'pm' and hour < 12:
                            hour += 12
                        elif ampm.lower() == 'am' and hour == 12:
                            hour = 0
                        
                        dt = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
                        return dt
                except:
                    pass
                
                # If all else fails, return current time
                return now
                
        except:
            return datetime.now()
    
    def _extract_topics(self, text: str) -> List[str]:
        """Extract potential trending topics from text"""
        topics = []
        
        # Look for hashtags
        hashtags = re.findall(r'#\w+', text)
        topics.extend([h[1:] for h in hashtags])
        
        # Look for product mentions (capped with $ or specific terms)
        product_terms = ['product', 'item', 'deal', 'offer', 'sale', 'new', 'limited', 'dm', 'order']
        words = text.lower().split()
        
        for word in words:
            if word in product_terms:
                # Get surrounding words as context
                idx = words.index(word)
                if idx > 0 and idx < len(words) - 1:
                    context = f"{words[idx-1]}_{words[idx]}_{words[idx+1]}"
                    topics.append(context)
        
        # Look for keywords in specific categories
        categories = {
            'fashion': ['dress', 'shirt', 'pants', 'skirt', 'jacket', 'shoe', 'bag', 'fashion'],
            'electronics': ['phone', 'laptop', 'computer', 'tv', 'screen', 'battery', 'charger'],
            'food': ['food', 'meal', 'delivery', 'restaurant', 'order food'],
            'services': ['service', 'repair', 'consult', 'booking', 'schedule']
        }
        
        for category, keywords in categories.items():
            if any(kw in text.lower() for kw in keywords):
                topics.append(f"{category}_trend")
        
        return list(set(topics))[:5]  # Limit to 5 topics per message
    
    # ============================================================
    # GROUP OPENING - WITH EXHAUSTIVE CONNECTION CHECKS
    # ============================================================
    
    async def open_group(self, group_name: str) -> bool:
        """
        Open a group with EXHAUSTIVE connection checking.
        Checks connection at EVERY major step.
        If connection is lost at any point, aborts and retries from beginning.
        """
        
        print(f"  🔍 Opening: {group_name}")
        
        # Check if group is marked for removal
        if group_name in self.failed_tracker.get_groups_to_remove():
            print(f"  ⚠️ Group '{group_name}' is marked for removal. Skipping.")
            return False
        
        for attempt in range(3):
            try:
                # ============================================================
                # CONNECTION CHECK: Before starting attempt
                # ============================================================
                await self.ensure_connection(f"open_group_attempt_{attempt+1}_{group_name}")
                
                print(f"    [1/5] Clicking search...")
                
                search_selectors = [
                    'div[data-testid="chat-list-search"]',
                    'div[role="textbox"]',
                    'button[aria-label="Search"]',
                    'div[aria-label="Search"]',
                    'div[data-tab="1"]'
                ]
                
                search_clicked = False
                for selector in search_selectors:
                    # CONNECTION CHECK: Before each selector attempt
                    await self.ensure_connection(f"open_group_search_selector_{attempt}_{selector[:20]}")
                    
                    try:
                        search = await self.page.query_selector(selector)
                        if search:
                            await search.click()
                            await asyncio.sleep(random.uniform(1, 2))
                            search_clicked = True
                            print(f"    ✅ Search clicked")
                            break
                    except:
                        continue
                
                if not search_clicked:
                    await self.page.keyboard.press('Control+Shift+J')
                    await asyncio.sleep(random.uniform(1, 2))
                    print(f"    ✅ Search via keyboard")
                
                # ============================================================
                # CONNECTION CHECK: After search
                # ============================================================
                await self.ensure_connection(f"open_group_after_search_{attempt}")
                
                print(f"    [2/5] Typing: {group_name}")
                
                input_selectors = [
                    'input[type="text"]',
                    'div[data-testid="chat-list-search"] input',
                    'div[role="textbox"]'
                ]
                
                typed = False
                for selector in input_selectors:
                    # CONNECTION CHECK: Before each typing attempt
                    await self.ensure_connection(f"open_group_typing_selector_{attempt}_{selector[:20]}")
                    
                    try:
                        search_input = await self.page.query_selector(selector)
                        if search_input:
                            await search_input.click()
                            await search_input.fill("")
                            await asyncio.sleep(0.5)
                            
                            # ============================================================
                            # TYPE WITH CONNECTION CHECKS BETWEEN CHARACTERS
                            # ============================================================
                            for char_index, char in enumerate(group_name):
                                # Check connection every 5 characters
                                if char_index % 5 == 0 and char_index > 0:
                                    await self.ensure_connection(f"open_group_typing_char_{char_index}_{attempt}")
                                
                                await search_input.type(char, delay=random.randint(HUMAN_TYPING_DELAY_MIN, HUMAN_TYPING_DELAY_MAX))
                            
                            await asyncio.sleep(SEARCH_WAIT + random.uniform(0, 2))
                            typed = True
                            print(f"    ✅ Typed: {group_name}")
                            break
                    except:
                        continue
                
                if not typed:
                    # ============================================================
                    # KEYBOARD TYPING WITH CONNECTION CHECKS
                    # ============================================================
                    for char_index, char in enumerate(group_name):
                        # Check connection every 5 characters
                        if char_index % 5 == 0 and char_index > 0:
                            await self.ensure_connection(f"open_group_typing_keyboard_{char_index}_{attempt}")
                        
                        await self.page.keyboard.type(char, delay=random.randint(HUMAN_TYPING_DELAY_MIN, HUMAN_TYPING_DELAY_MAX))
                    
                    await asyncio.sleep(SEARCH_WAIT + random.uniform(0, 2))
                    print(f"    ✅ Typed via keyboard")
                
                # ============================================================
                # CONNECTION CHECK: After typing
                # ============================================================
                await self.ensure_connection(f"open_group_after_typing_{attempt}")
                
                print(f"    [3/5] Finding group...")
                
                group_selectors = [
                    f'div[role="row"]:has-text("{group_name}")',
                    f'span[data-testid="chat-name"]:has-text("{group_name}")'
                ]
                
                group_found = False
                for selector in group_selectors:
                    # CONNECTION CHECK: Before each group finding attempt
                    await self.ensure_connection(f"open_group_finding_selector_{attempt}_{selector[:20]}")
                    
                    try:
                        group = await self.page.query_selector(selector)
                        if group:
                            await group.click()
                            await asyncio.sleep(OPEN_WAIT + random.uniform(0, 2))
                            group_found = True
                            print(f"    ✅ Group found and clicked")
                            break
                    except:
                        continue
                
                if not group_found:
                    print(f"    [3/5] Scanning chats...")
                    chats = await self.page.query_selector_all('div[role="row"]')
                    
                    for chat_index, chat in enumerate(chats):
                        # CONNECTION CHECK: During chat scanning (every 5 chats)
                        if chat_index % 5 == 0:
                            await self.ensure_connection(f"open_group_scanning_chat_{attempt}_{chat_index}")
                        
                        try:
                            text = await chat.inner_text()
                            if group_name.lower() in text.lower():
                                await chat.click()
                                await asyncio.sleep(OPEN_WAIT + random.uniform(0, 2))
                                group_found = True
                                print(f"    ✅ Found via text scan")
                                break
                        except:
                            continue
                
                if not group_found:
                    print(f"    ❌ Group not found in results")
                    self.failed_tracker.record_failure(group_name)
                    if attempt < 2:
                        print(f"    🔄 Retrying in {RETRY_DELAY}-{RETRY_DELAY+3}s...")
                        await asyncio.sleep(RETRY_DELAY + random.uniform(0, 3))
                    continue
                
                # ============================================================
                # CONNECTION CHECK: After finding group
                # ============================================================
                await self.ensure_connection(f"open_group_after_finding_{attempt}")
                
                print(f"    [4/5] Verifying group opened...")
                
                compose_selectors = [
                    '#main > footer > div > span > div > div > div > div > div.x1hx0egp > p',
                    'div[contenteditable="true"]',
                    'div[role="textbox"]',
                    'div[aria-label="Type a message"]',
                    'div[data-testid="conversation-compose-box"]',
                    'footer div[contenteditable="true"]',
                    'p[contenteditable="true"]'
                ]
                
                compose_found = False
                for selector in compose_selectors:
                    # CONNECTION CHECK: During compose verification
                    await self.ensure_connection(f"open_group_compose_verify_{attempt}_{selector[:20]}")
                    
                    try:
                        compose = await self.page.query_selector(selector)
                        if compose:
                            is_visible = await compose.is_visible()
                            if is_visible:
                                print(f"    ✅ Group opened! (Found compose box)")
                                compose_found = True
                                break
                    except:
                        continue
                
                if compose_found:
                    print(f"    ✅ Group opened successfully!")
                    self.failed_tracker.record_success(group_name)
                    return True
                else:
                    print(f"    ❌ Compose box not found")
                    self.failed_tracker.record_failure(group_name)
                    if attempt < 2:
                        print(f"    🔄 Retrying in {RETRY_DELAY}-{RETRY_DELAY+3}s...")
                        await asyncio.sleep(RETRY_DELAY + random.uniform(0, 3))
                        continue
                    else:
                        return False
                
            except ConnectionLostError as e:
                # ============================================================
                # CONNECTION LOST - ABORT AND CLEAN UP
                # ============================================================
                print(f"  ⚠️ Connection lost during attempt {attempt+1}: {e}")
                print(f"  🔄 Waiting for reconnection, then retrying from start...")
                
                # Clean up - clear any keyboard state
                try:
                    # Release all keys
                    await self.page.keyboard.up('Shift')
                    await self.page.keyboard.up('Enter')
                    await self.page.keyboard.up('Control')
                    await self.page.keyboard.up('Alt')
                    await asyncio.sleep(0.5)
                except:
                    pass
                
                try:
                    # Press Escape to close any open dialogs
                    await self.page.keyboard.press('Escape')
                    await asyncio.sleep(0.5)
                except:
                    pass
                
                # Ensure we're reconnected (this may raise ConnectionLostError again)
                try:
                    await self.ensure_connection(f"open_group_reconnect_{attempt+1}")
                except ConnectionLostError:
                    # If we're still disconnected, wait and retry
                    print(f"  ⚠️ Still disconnected, waiting longer...")
                    await asyncio.sleep(5)
                    await self.ensure_connection(f"open_group_reconnect_retry_{attempt+1}")
                
                # Wait a moment for stability
                await asyncio.sleep(1)
                
                # Continue to next attempt
                continue
                
            except Exception as e:
                print(f"    ❌ Error: {e}")
                self.failed_tracker.record_failure(group_name)
                
                if attempt < 2:
                    print(f"    🔄 Retrying in {RETRY_DELAY}-{RETRY_DELAY+3}s...")
                    await asyncio.sleep(RETRY_DELAY + random.uniform(0, 3))
                    continue
                else:
                    return False
        
        print(f"  ❌ Failed to open: {group_name}")
        return False
    
    # ============================================================
    # POST TO GROUP - WITH EXHAUSTIVE CONNECTION CHECKS
    # ============================================================
    
    async def post_to_group(self, group_name: str, message: str) -> bool:
        """
        Post a message to a group with EXHAUSTIVE connection checking.
        Checks connection at EVERY critical step.
        If connection is lost at any point, aborts and returns False.
        """
        
        try:
            # CONNECTION CHECK: Before starting
            await self.ensure_connection(f"post_to_group_start_{group_name}")
            
            print(f"\n📤 Posting to: {group_name}")
            
            # CONNECTION CHECK: Before database operation
            await self.ensure_connection(f"post_to_group_db_prep_{group_name}")
            
            # Get or create group in database
            group_id = self.db.get_or_create_group(group_name)
            
            # CONNECTION CHECK: Before opening group
            await self.ensure_connection(f"post_to_group_open_{group_name}")
            
            if not await self.open_group(group_name):
                print(f"  ❌ Could not open group: {group_name}")
                return False
            
            # CONNECTION CHECK: After opening group
            await self.ensure_connection(f"post_to_group_after_open_{group_name}")
            
            print(f"  [6/9] Finding compose box...")
            
            compose_selectors = [
                '#main > footer > div > span > div > div > div > div > div.x1hx0egp > p',
                'div[contenteditable="true"]',
                'div[role="textbox"]',
                'div[aria-label="Type a message"]',
                'div[data-testid="conversation-compose-box"]',
                'footer div[contenteditable="true"]',
                'p[contenteditable="true"]'
            ]
            
            compose = None
            for attempt in range(3):
                # CONNECTION CHECK: During compose search
                await self.ensure_connection(f"post_to_group_compose_attempt_{attempt}_{group_name}")
                
                for selector in compose_selectors:
                    try:
                        compose = await self.page.query_selector(selector)
                        if compose:
                            is_visible = await compose.is_visible()
                            if is_visible:
                                print(f"    ✅ Compose box found")
                                break
                    except:
                        continue
                
                if compose:
                    break
                
                print(f"    ⏳ Waiting for compose box... (attempt {attempt+1}/3)")
                await asyncio.sleep(FIND_COMPOSE_WAIT + random.uniform(0, 2))
            
            if not compose:
                print(f"  ❌ Compose box not found")
                self.failed_tracker.record_failure(group_name)
                return False
            
            # CONNECTION CHECK: Before typing
            await self.ensure_connection(f"post_to_group_before_typing_{group_name}")
            
            print(f"  [7/9] Typing message with formatting...")
            
            await compose.click()
            await asyncio.sleep(0.5)
            await compose.fill("")
            await asyncio.sleep(0.5)
            
            lines = message.split('\n')
            
            for line_index, line in enumerate(lines):
                # CONNECTION CHECK: During typing (every few lines)
                if line_index % 3 == 0:
                    await self.ensure_connection(f"post_to_group_typing_line_{line_index}_{group_name}")
                
                for char in line:
                    await compose.type(char, delay=random.randint(HUMAN_TYPING_DELAY_MIN, HUMAN_TYPING_DELAY_MAX))
                    if random.random() < 0.02:
                        await asyncio.sleep(random.uniform(0.1, 0.3))
                
                if line_index < len(lines) - 1:
                    await self.page.keyboard.press('Shift+Enter')
                    await asyncio.sleep(random.uniform(0.1, 0.3))
            
            print(f"    ✅ Message typed with {len(lines)} lines")
            
            # CONNECTION CHECK: After typing
            await self.ensure_connection(f"post_to_group_after_typing_{group_name}")
            
            # Smart Link Preview Detection
            if self.product_loader.has_url(message):
                print(f"  [7.5/9] ⏳ Waiting for link preview to load...")
                print(f"    ⏳ WhatsApp needs up to {LINK_PREVIEW_DELAY}s to generate the preview")
                
                preview_loaded = False
                url_selector = 'div[data-testid="message-text"]'
                
                for attempt in range(LINK_PREVIEW_DELAY):
                    # CONNECTION CHECK: During preview wait (every 2 seconds)
                    if attempt % 2 == 0:
                        try:
                            await self.ensure_connection(f"post_to_group_preview_wait_{attempt}_{group_name}")
                        except ConnectionLostError:
                            print(f"    ⚠️ Connection issue during preview wait, continuing...")
                            await asyncio.sleep(2)
                            continue
                    
                    await asyncio.sleep(1)
                    
                    try:
                        message_text = await self.page.evaluate(f'''
                            (selector) => {{
                                const el = document.querySelector(selector);
                                return el ? el.textContent : '';
                            }}
                        ''', url_selector)
                        
                        if message_text and not self.product_loader.has_url(message_text):
                            preview_loaded = True
                            print(f"    ✅ Link preview loaded! (took {attempt+1}s)")
                            break
                        
                        preview_selectors = [
                            'div[data-testid="link-preview"]',
                            'div[data-testid="link"]',
                            'div[aria-label="Link preview"]',
                            'div.link-preview-container',
                            'div[data-testid="message-link"]',
                            'div[data-testid="image-container"]'
                        ]
                        
                        for selector in preview_selectors:
                            try:
                                preview = await self.page.query_selector(selector)
                                if preview and await preview.is_visible():
                                    preview_loaded = True
                                    print(f"    ✅ Link preview loaded! (found: {selector})")
                                    break
                            except:
                                continue
                        
                        if preview_loaded:
                            break
                        
                    except Exception as e:
                        pass
                    
                    if (attempt + 1) % 5 == 0:
                        print(f"    ⏳ Still loading... ({attempt+1}/{LINK_PREVIEW_DELAY}s)")
                
                if not preview_loaded:
                    print(f"    ⚠️ Link preview didn't appear, waiting extra 2s...")
                    await asyncio.sleep(2)
                    print(f"    ✅ Proceeding with send")
            else:
                print(f"  [7.5/9] ⏳ No link detected, proceeding...")
            
            # CONNECTION CHECK: Before sending
            await self.ensure_connection(f"post_to_group_before_send_{group_name}")
            
            print(f"  [8/9] Final pause before sending...")
            await asyncio.sleep(AFTER_TYPING_WAIT + random.uniform(0, 2))
            
            print(f"  [9/9] Sending message...")
            
            # Send using Enter key
            print(f"    ⏳ Pressing Enter to send...")
            await self.page.keyboard.press('Enter')
            await asyncio.sleep(2)
            print(f"    ✅ Enter key pressed - message sent")
            
            # CONNECTION CHECK: After sending
            try:
                await self.ensure_connection(f"post_to_group_after_send_{group_name}")
            except ConnectionLostError:
                print(f"  ⚠️ Connection lost after sending, but continuing for confirmation...")
            
            print(f"  [10/9] Waiting for send confirmation...")
            await asyncio.sleep(SEND_CONFIRM_WAIT + random.uniform(0, 4))
            
            # CONNECTION CHECK: Before checking confirmation
            try:
                await self.ensure_connection(f"post_to_group_confirmation_check_{group_name}")
            except ConnectionLostError:
                print(f"  ⚠️ Connection lost during confirmation check. Proceeding anyway...")
            
            # Check if message was sent
            message_sent = False
            try:
                last_msg = await self.page.query_selector('div[data-testid="msg-container"]:last-child')
                if last_msg:
                    is_own = await last_msg.query_selector('div[data-testid="msg-own"]')
                    if is_own:
                        print(f"    ✅ Message confirmed in chat!")
                        message_sent = True
                    else:
                        print(f"    ⚠️ Message sent (not confirmed)")
                        message_sent = True
                else:
                    print(f"    ✅ Message sent")
                    message_sent = True
            except:
                print(f"    ✅ Message sent")
                message_sent = True
            
            # ============================================================
            # DATA COLLECTION: ALWAYS COLLECT, even if message send failed
            # ============================================================
            
            # CONNECTION CHECK: Before data collection
            try:
                await self.ensure_connection(f"post_to_group_data_collection_start_{group_name}")
            except ConnectionLostError:
                print(f"  ⚠️ Connection lost before data collection. Will try anyway...")
            
            print(f"\n  📊 Beginning data collection for: {group_name}")
            
            # Collect chat history (handles its own connection checks)
            messages_collected = await self.collect_chat_history(group_name, group_id)
            
            # CONNECTION CHECK: Before database save
            try:
                await self.ensure_connection(f"post_to_group_db_save_{group_name}")
            except ConnectionLostError:
                print(f"  ⚠️ Connection lost before saving product post. Will try anyway...")
            
            # Save product post to database (always save)
            if self.current_product:
                product_id = self.db.save_product_post(
                    product=self.current_product,
                    group_id=group_id,
                    message=message
                )
                print(f"    ✅ Product post saved to database (ID: {product_id})")
            
            print(f"  ✅ Data collection complete for: {group_name}")
            print(f"    📊 Total messages collected: {messages_collected}")
            
            # Record success or failure
            if message_sent:
                self.failed_tracker.record_success(group_name)
                print(f"  ✅ Posted and collected data from: {group_name}")
                return True
            else:
                self.failed_tracker.record_failure(group_name)
                print(f"  ⚠️ Message may not have sent, but data collected")
                return False
            
        except ConnectionLostError as e:
            print(f"  ⚠️ Connection lost during posting to {group_name}: {e}")
            print(f"  🔄 Posting aborted. Will retry on next run.")
            self.failed_tracker.record_failure(group_name)
            return False
        except Exception as e:
            print(f"  ❌ Error posting: {e}")
            self.failed_tracker.record_failure(group_name)
            
            # Try to save any collected data even on error
            try:
                if self.current_product and 'group_id' in locals():
                    self.db.save_product_post(
                        product=self.current_product,
                        group_id=group_id,
                        message=message,
                        status="error",
                        error_message=str(e)
                    )
            except:
                pass
            
            return False
    
    # ============================================================
    # FILTER GROUPS - WITH CONNECTION CHECK
    # ============================================================
    
    def filter_groups(self, groups: List[str]) -> List[str]:
        """Filter out groups that are marked for removal"""
        groups_to_remove = self.failed_tracker.get_groups_to_remove()
        
        if groups_to_remove:
            print(f"\n⚠️ Removing {len(groups_to_remove)} failed groups from target list:")
            for group in groups_to_remove:
                failures = self.failed_tracker.failed_groups[group]["failures"]
                print(f"  - {group} ({failures} failures)")
                self.failed_tracker.remove_group(group)
            
            print(f"\n✅ Removed {len(groups_to_remove)} groups. They will be skipped in future runs.")
        
        return [g for g in groups if g not in groups_to_remove]
    
    # ============================================================
    # POST RANDOM PRODUCTS - WITH EXHAUSTIVE CONNECTION CHECKS
    # ============================================================
    
    async def post_random_products(self, count: int = None, groups: List[str] = None):
        """
        Post random products with EXHAUSTIVE connection checking.
        Checks connection at EVERY critical step.
        """
        
        try:
            # CONNECTION CHECK: Before starting
            await self.ensure_connection("post_random_products_start")
        except ConnectionLostError:
            print("❌ Cannot start - WhatsApp not connected")
            return
        
        if groups is None:
            groups = TARGET_GROUPS
        
        groups = self.filter_groups(groups)
        
        if not groups:
            print("\n❌ No groups available to post to!")
            self.failed_tracker.print_summary()
            return
        
        try:
            # CONNECTION CHECK: Before loading products
            await self.ensure_connection("post_random_products_load_products")
        except ConnectionLostError:
            print("❌ Cannot load products - WhatsApp not connected")
            return
        
        products = self.product_loader.load_all_products(status="pending")
        
        if not products:
            print("\n📭 No pending products found!")
            print("🔄 Attempting to reset all products...")
            if self.product_loader.reset_all_products():
                products = self.product_loader.load_all_products(status="pending")
            
            if not products:
                print("❌ Still no products after reset")
                return
        
        pending_products = self.product_loader.get_all_pending()
        pending_count = len(pending_products)
        
        print(f"\n📦 Total pending products: {pending_count}")
        print(f"📱 Active groups: {len(groups)}")
        
        pending_removal = self.failed_tracker.get_groups_to_remove()
        if pending_removal:
            print(f"⚠️ {len(pending_removal)} groups are pending removal (will be removed after this run)")
        
        if count is None:
            count = POSTS_PER_RUN
        
        if count > pending_count:
            print(f"⚠️ Requested {count} products but only {pending_count} pending. Posting {pending_count}.")
            count = pending_count
        
        selected = random.sample(pending_products, count)
        
        print(f"\n📢 Will post {count} product(s) to {len(groups)} groups")
        print(f"📋 Selected product(s):")
        for i, p in enumerate(selected, 1):
            source = p.get("source", "unknown")
            name = p.get("product_name") or p.get("id", "Unknown")
            has_link = "🔗" if p.get("url") else "📝"
            print(f"  {i}. {has_link} [{source}] {name}")
        
        print(f"\n▶️ Posting to {len(groups)} groups...")
        print("=" * 60)
        
        successful_products = 0
        failed_products = 0
        total_messages_collected = 0
        
        for i, product in enumerate(selected, 1):
            try:
                # CONNECTION CHECK: Before each product
                await self.ensure_connection(f"post_random_products_product_{i}")
            except ConnectionLostError:
                print("❌ Connection lost. Stopping posting.")
                break
            
            product_name = product.get("product_name") or product.get("id", "Product")
            source = product.get("source", "unknown")
            has_link = bool(product.get("url"))
            
            # Store current product for database
            self.current_product = product
            
            print(f"\n{'='*60}")
            print(f"📦 [{i}/{len(selected)}] {source.upper()}: {product_name}")
            print(f"   Link: {'Yes' if has_link else 'No'}")
            print(f"{'='*60}")
            
            message = self.product_loader.get_product_message(product)
            
            successful_groups = []
            failed_groups = []
            
            for j, group in enumerate(groups, 1):
                try:
                    # CONNECTION CHECK: Before each group
                    await self.ensure_connection(f"post_random_products_group_{j}_{group}")
                except ConnectionLostError:
                    print("❌ Connection lost. Stopping posting.")
                    break
                
                print(f"\n--- Group {j}/{len(groups)} ---")
                
                success = await self.post_to_group(group, message)
                
                # CONNECTION CHECK: After posting to group
                try:
                    await self.ensure_connection(f"post_random_products_after_group_{j}_{group}")
                except ConnectionLostError:
                    print("⚠️ Connection lost after posting to group. Checking...")
                    try:
                        await self.ensure_connection(f"post_random_products_reconnect_{j}_{group}")
                    except ConnectionLostError:
                        print("❌ Connection lost. Stopping posting.")
                        break
                
                if success:
                    successful_groups.append(group)
                    total_messages_collected += 1
                else:
                    failed_groups.append(group)
                
                if j < len(groups):
                    # CONNECTION CHECK: Before waiting
                    try:
                        await self.ensure_connection(f"post_random_products_wait_{j}_{group}")
                    except ConnectionLostError:
                        print("⚠️ Connection lost before wait. Waiting for reconnection...")
                        try:
                            await self.ensure_connection(f"post_random_products_wait_reconnect_{j}_{group}")
                        except ConnectionLostError:
                            print("❌ Connection lost. Stopping posting.")
                            break
                    
                    print(f"⏳ Waiting {BETWEEN_GROUPS_WAIT}s before next group...")
                    await asyncio.sleep(BETWEEN_GROUPS_WAIT + random.uniform(0, 2))
            
            # CONNECTION CHECK: Before marking product as posted
            try:
                await self.ensure_connection(f"post_random_products_mark_product_{i}")
            except ConnectionLostError:
                print("⚠️ Connection lost before marking product. Skipping mark.")
                failed_products += 1
                continue
            
            if successful_groups:
                mark_success = self.product_loader.mark_as_posted(product)
                if mark_success:
                    successful_products += 1
                    print(f"\n✅ Product '{product_name}' posted to {len(successful_groups)} groups")
                else:
                    failed_products += 1
                    print(f"\n❌ Product '{product_name}' failed to mark as posted")
            else:
                failed_products += 1
                print(f"\n❌ Product '{product_name}' failed to post")
            
            if failed_groups:
                print(f"⚠️ Failed groups: {failed_groups}")
            
            if i < len(selected) and len(selected) > 1:
                # CONNECTION CHECK: Before waiting for next product
                try:
                    await self.ensure_connection(f"post_random_products_next_product_{i}")
                except ConnectionLostError:
                    print("⚠️ Connection lost before next product. Waiting...")
                    try:
                        await self.ensure_connection(f"post_random_products_next_product_reconnect_{i}")
                    except ConnectionLostError:
                        print("❌ Connection lost. Stopping posting.")
                        break
                
                print(f"\n⏳ Waiting {BETWEEN_PRODUCTS_WAIT}s before next product...")
                await asyncio.sleep(BETWEEN_PRODUCTS_WAIT + random.uniform(0, 2))
        
        # CONNECTION CHECK: Before final summary
        try:
            await self.ensure_connection("post_random_products_summary")
        except ConnectionLostError:
            print("⚠️ Connection lost during final summary. Some stats may be incomplete.")
        
        # Final summary
        stats = self.product_loader.get_stats()
        db_stats = self.db.get_db_stats()
        
        print("\n" + "=" * 60)
        print("📊 POSTING & DATA COLLECTION SUMMARY")
        print("=" * 60)
        print(f"✅ Successful products: {successful_products}")
        print(f"❌ Failed products: {failed_products}")
        print(f"📱 Groups used: {len(groups)}")
        print(f"📦 Pending remaining: {stats['pending']}")
        print(f"⏳ Link preview max delay: {LINK_PREVIEW_DELAY}s")
        print("")
        print("📊 DATABASE STATISTICS")
        print("-" * 40)
        print(f"Total groups in DB: {db_stats['total_groups']}")
        print(f"Total messages in DB: {db_stats['total_messages']}")
        print(f"Total products posted: {db_stats['total_products_posted']}")
        print(f"Unique words tracked: {db_stats['unique_words']}")
        print(f"Trending topics tracked: {db_stats['trending_topics']}")
        print("")
        print("📊 CONNECTION MONITORING STATISTICS")
        print("-" * 40)
        print(f"Total connection checks: {self.connection_stats['checks_performed']}")
        print(f"Disconnections detected: {self.connection_stats['disconnections_detected']}")
        print(f"Reconnections succeeded: {self.connection_stats['reconnections_succeeded']}")
        print(f"Operations paused: {self.connection_stats['operations_paused']}")
        print("=" * 60)
        
        self.failed_tracker.print_summary()
        
        if stats['pending'] == 0:
            print("\n🎉 All products are posted!")
            print("🔄 Auto-resetting all products to pending for fresh start...")
            self.product_loader.reset_all_products()
            print("✅ Products reset! Ready for next round.")
        
        print(f"\n✅ Posting complete! {successful_products} product(s) posted.")
        print(f"📊 Data collected and stored in database: {DB_FILE}")
    
    # ============================================================
    # GENERATE ANALYTICS REPORT
    # ============================================================
    
    def generate_report(self):
        """Generate and save a comprehensive analytics report"""
        report = self.db.generate_report()
        print(report)
        
        # Save report to file
        report_file = DATA_DIR / f"analytics_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
        with open(report_file, 'w', encoding='utf-8') as f:
            f.write(report)
        print(f"\n📄 Report saved to: {report_file}")
        
        return report
    
    # ============================================================
    # CONNECTION HEALTH CHECK - BACKGROUND TASK
    # ============================================================
    
    async def connection_health_monitor(self):
        """
        Background task that periodically checks connection health.
        Runs in the background while other operations are ongoing.
        """
        print("🔄 Connection health monitor started")
        
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
        """Start the poster with connection monitoring"""
        self.is_running = True
        
        # Start background health monitor
        asyncio.create_task(self.connection_health_monitor())
        
        print("✅ Group Poster started with EXHAUSTIVE connection monitoring")
        print(f"   Connection checks at EVERY critical step")
        print(f"   Health monitor running every {CONNECTION_CHECK_INTERVAL}s")
    
    async def stop(self):
        """Stop the poster"""
        self.is_running = False
        print("🛑 Group Poster stopped")

# ============================================================
# MAIN ENTRY POINT - FOR STANDALONE USE
# ============================================================

async def main():
    """Main entry point for the WhatsApp poster with data collection"""
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)
        context = await browser.new_context(
            viewport={'width': 1280, 'height': 800},
            user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        )
        page = await context.new_page()
        
        # Initialize poster (no login manager for standalone)
        # In production, you would pass a LoginManager instance here
        poster = GroupPoster(page, context)
        
        # Start the poster (starts background health monitor)
        await poster.start()
        
        # Navigate to WhatsApp Web
        await page.goto("https://web.whatsapp.com")
        print("📱 Please scan the QR code to login...")
        print("⏳ Waiting for WhatsApp to load...")
        
        # Wait for WhatsApp to load
        await page.wait_for_selector('div[data-testid="chat-list"]', timeout=120000)
        print("✅ WhatsApp loaded successfully!")
        
        try:
            # Post products with data collection
            await poster.post_random_products(count=1)
            
            # Generate analytics report
            poster.generate_report()
            
        except KeyboardInterrupt:
            print("\n\n⏹️ Stopped by user")
        except Exception as e:
            print(f"\n❌ Error: {e}")
            import traceback
            traceback.print_exc()
        
        finally:
            # Stop the poster
            await poster.stop()
            
            # Close database connection
            poster.db.close()
            
            print("\n📊 Data collection complete!")
            print(f"📁 Database stored at: {DB_FILE}")
            print(f"📊 Connection checks performed: {poster.connection_stats['checks_performed']}")
            print(f"   Disconnections detected: {poster.connection_stats['disconnections_detected']}")
            print(f"   Reconnections succeeded: {poster.connection_stats['reconnections_succeeded']}")
            
            # Keep browser open for a moment
            print("\n⏳ Press Ctrl+C to close browser...")
            await asyncio.sleep(10)
            await browser.close()

if __name__ == "__main__":
    asyncio.run(main())