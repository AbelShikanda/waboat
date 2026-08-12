"""
Group Poster Module
===================
Handles all WhatsApp group posting functionality:
- Loading products from JSON files
- Opening groups
- Posting messages with line breaks
- Smart link preview waiting (detects when preview loads)
- Product status management
- Posts ONE product per run (configurable)
- Tracks failed groups and auto-removes after 10 failures
"""

import json
import random
import asyncio
from pathlib import Path
from datetime import datetime
from typing import List, Optional, Dict
from playwright.async_api import async_playwright

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
HUMAN_TYPING_DELAY_MIN = 20
HUMAN_TYPING_DELAY_MAX = 40

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

# Number of products to post per run (1 = post one product to all groups)
POSTS_PER_RUN = 1

# Group failure threshold (auto-remove after this many failures)
MAX_GROUP_FAILURES = 100

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
                "status": "active"  # active, pending_removal, removed
            }
        
        self.failed_groups[group_name]["failures"] += 1
        self.failed_groups[group_name]["last_failure"] = datetime.now().isoformat()
        
        # Check if threshold is reached
        if self.failed_groups[group_name]["failures"] >= MAX_GROUP_FAILURES:
            self.failed_groups[group_name]["status"] = "pending_removal"
            print(f"  ⚠️ Group '{group_name}' has failed {self.failed_groups[group_name]['failures']} times. Marked for removal.")
        
        self._save_failed_groups()
    
    def record_success(self, group_name: str):
        """Record a success for a group (reset failures)"""
        if group_name in self.failed_groups:
            # Reset failure count on success
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
        """Remove a group from the failed groups list (after deletion from target groups)"""
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
    
    import random

    def get_product_message(self, product: dict, contact_name: str = "") -> str:
        """Create a marketing message with optional personalization"""
        name = product.get("product_name") or product.get("id") or "Product"
        description = product.get("description") or product.get("caption") or ""
        url = product.get("url") or ""
        source = product.get("source", "unknown")
        
        if not description:
            description = f"Check out this {source} post!"
        
        # Variety pools
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
        
        # Clean hashtag: remove special chars and spaces
        hashtag_name = ''.join(c for c in name if c.isalnum())
        
        # Build message with conditional greeting
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
# GROUP POSTER CLASS
# ============================================================

class GroupPoster:
    """Handles all group posting operations"""
    
    def __init__(self, page, context):
        self.page = page
        self.context = context
        self.product_loader = ProductLoader()
        self.failed_tracker = FailedGroupsTracker()
        self.is_running = False
    
    # ============================================================
    # GROUP OPENING (with failure tracking)
    # ============================================================
    
    async def open_group(self, group_name: str) -> bool:
        """Open a group with failure tracking"""
        print(f"  🔍 Opening: {group_name}")
        
        # Check if group is already marked for removal
        if group_name in self.failed_tracker.get_groups_to_remove():
            print(f"  ⚠️ Group '{group_name}' is marked for removal. Skipping.")
            return False
        
        for attempt in range(3):
            try:
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
                
                print(f"    [2/5] Typing: {group_name}")
                
                input_selectors = [
                    'input[type="text"]',
                    'div[data-testid="chat-list-search"] input',
                    'div[role="textbox"]'
                ]
                
                typed = False
                for selector in input_selectors:
                    try:
                        search_input = await self.page.query_selector(selector)
                        if search_input:
                            await search_input.click()
                            await search_input.fill("")
                            await asyncio.sleep(0.5)
                            
                            for char in group_name:
                                await search_input.type(char, delay=random.randint(HUMAN_TYPING_DELAY_MIN, HUMAN_TYPING_DELAY_MAX))
                            await asyncio.sleep(SEARCH_WAIT + random.uniform(0, 2))
                            typed = True
                            print(f"    ✅ Typed: {group_name}")
                            break
                    except:
                        continue
                
                if not typed:
                    await self.page.keyboard.type(group_name, delay=random.randint(HUMAN_TYPING_DELAY_MIN, HUMAN_TYPING_DELAY_MAX))
                    await asyncio.sleep(SEARCH_WAIT + random.uniform(0, 2))
                    print(f"    ✅ Typed via keyboard")
                
                print(f"    [3/5] Finding group...")
                
                group_selectors = [
                    f'div[role="row"]:has-text("{group_name}")',
                    f'span[data-testid="chat-name"]:has-text("{group_name}")'
                ]
                
                group_found = False
                for selector in group_selectors:
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
                    for chat in chats:
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
                
            except Exception as e:
                print(f"    ❌ Error: {e}")
                self.failed_tracker.record_failure(group_name)
                if attempt < 2:
                    print(f"    🔄 Retrying in {RETRY_DELAY}-{RETRY_DELAY+3}s...")
                    await asyncio.sleep(RETRY_DELAY + random.uniform(0, 3))
        
        print(f"  ❌ Failed to open: {group_name}")
        return False
    
    # ============================================================
    # POST TO GROUP (SMART LINK PREVIEW DETECTION)
    # ============================================================
    
    async def post_to_group(self, group_name: str, message: str) -> bool:
        """
        Post a message to a group
        - Types with line breaks preserved
        - Smart link preview waiting (detects when preview loads)
        """
        print(f"\n📤 Posting to: {group_name}")
        
        try:
            if not await self.open_group(group_name):
                print(f"  ❌ Could not open group: {group_name}")
                return False
            
            print(f"  [6/9] Finding compose box...")
            
            compose_selectors = [
                '#main > footer > div > span > div > div > div > div > div.x1hx0egp > p',
                'div[contenteditable="true"]',
                'div[role="textbox"]',
                'footer div[contenteditable="true"]',
                'p[contenteditable="true"]'
            ]
            
            compose = None
            for attempt in range(3):
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
            
            print(f"  [7/9] Typing message with formatting...")
            
            await compose.click()
            await asyncio.sleep(0.5)
            await compose.fill("")
            await asyncio.sleep(0.5)
            
            lines = message.split('\n')
            
            for line_index, line in enumerate(lines):
                for char in line:
                    await compose.type(char, delay=random.randint(HUMAN_TYPING_DELAY_MIN, HUMAN_TYPING_DELAY_MAX))
                    if random.random() < 0.02:
                        await asyncio.sleep(random.uniform(0.1, 0.3))
                
                if line_index < len(lines) - 1:
                    await self.page.keyboard.press('Shift+Enter')
                    await asyncio.sleep(random.uniform(0.1, 0.3))
            
            print(f"    ✅ Message typed with {len(lines)} lines")
            
            # ============================================================
            # SMART LINK PREVIEW DETECTION
            # ============================================================
            if self.product_loader.has_url(message):
                print(f"  [7.5/9] ⏳ Waiting for link preview to load...")
                print(f"    ⏳ WhatsApp needs up to {LINK_PREVIEW_DELAY}s to generate the preview")
                
                preview_loaded = False
                url_selector = 'div[data-testid="message-text"]'
                
                for attempt in range(LINK_PREVIEW_DELAY):
                    await asyncio.sleep(1)
                    
                    try:
                        # Check if URL is still visible as plain text
                        message_text = await self.page.evaluate(f'''
                            (selector) => {{
                                const el = document.querySelector(selector);
                                return el ? el.textContent : '';
                            }}
                        ''', url_selector)
                        
                        # If URL is no longer in the message text, preview has replaced it
                        if message_text and not self.product_loader.has_url(message_text):
                            preview_loaded = True
                            print(f"    ✅ Link preview loaded! (took {attempt+1}s)")
                            break
                        
                        # Also check for preview elements
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
                        # If we can't check, continue waiting
                        pass
                    
                    # Show progress every 5 seconds
                    if (attempt + 1) % 5 == 0:
                        print(f"    ⏳ Still loading... ({attempt+1}/{LINK_PREVIEW_DELAY}s)")
                
                # If preview didn't load, wait a bit longer
                if not preview_loaded:
                    print(f"    ⚠️ Link preview didn't appear, waiting extra 2s...")
                    await asyncio.sleep(2)
                    print(f"    ✅ Proceeding with send")
            else:
                print(f"  [7.5/9] ⏳ No link detected, proceeding...")
            
            print(f"  [8/9] Final pause before sending...")
            await asyncio.sleep(AFTER_TYPING_WAIT + random.uniform(0, 2))
            
            print(f"  [9/9] Sending message...")
            
            send_selectors = [
                'button[data-testid="compose-btn-send"]',
                'button[aria-label="Send"]',
                'button[type="submit"]'
            ]
            
            send = None
            for selector in send_selectors:
                try:
                    send = await self.page.query_selector(selector)
                    if send:
                        break
                except:
                    continue
            
            if not send:
                print(f"  ❌ Send button not found")
                return False
            
            await send.click()
            print(f"    📤 Send clicked")
            
            print(f"  [10/9] Waiting for send confirmation...")
            await asyncio.sleep(SEND_CONFIRM_WAIT + random.uniform(0, 4))
            
            try:
                last_msg = await self.page.query_selector('div[data-testid="msg-container"]:last-child')
                if last_msg:
                    is_own = await last_msg.query_selector('div[data-testid="msg-own"]')
                    if is_own:
                        print(f"    ✅ Message confirmed in chat!")
                    else:
                        print(f"    ⚠️ Message sent (not confirmed)")
                else:
                    print(f"    ✅ Message sent")
            except:
                print(f"    ✅ Message sent")
            
            print(f"  ✅ Posted to: {group_name}")
            return True
            
        except Exception as e:
            print(f"  ❌ Error posting: {e}")
            self.failed_tracker.record_failure(group_name)
            return False
    
    # ============================================================
    # FILTER GROUPS (remove failed ones)
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
        
        # Return groups that are not in removal list
        return [g for g in groups if g not in groups_to_remove]
    
    # ============================================================
    # POST RANDOM PRODUCTS
    # ============================================================
    
    async def post_random_products(self, count: int = None, groups: List[str] = None):
        """
        Post random products - DEFAULT: Posts ONE product to ALL groups and stops
        
        Args:
            count: Number of products to post. Default is 1 (POSTS_PER_RUN)
            groups: List of groups to post to. Default is TARGET_GROUPS
        """
        if groups is None:
            groups = TARGET_GROUPS
        
        # Filter out failed groups
        groups = self.filter_groups(groups)
        
        if not groups:
            print("\n❌ No groups available to post to!")
            self.failed_tracker.print_summary()
            return
        
        # Load all pending products
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
        
        # Check for groups pending removal
        pending_removal = self.failed_tracker.get_groups_to_remove()
        if pending_removal:
            print(f"⚠️ {len(pending_removal)} groups are pending removal (will be removed after this run)")
        
        # Default: Post ONE product
        if count is None:
            count = POSTS_PER_RUN
        
        if count > pending_count:
            print(f"⚠️ Requested {count} products but only {pending_count} pending. Posting {pending_count}.")
            count = pending_count
        
        # Select random product(s)
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
        
        for i, product in enumerate(selected, 1):
            product_name = product.get("product_name") or product.get("id", "Product")
            source = product.get("source", "unknown")
            has_link = bool(product.get("url"))
            
            print(f"\n{'='*60}")
            print(f"📦 [{i}/{len(selected)}] {source.upper()}: {product_name}")
            print(f"   Link: {'Yes' if has_link else 'No'}")
            print(f"{'='*60}")
            
            message = self.product_loader.get_product_message(product)
            
            successful_groups = []
            failed_groups = []
            
            for j, group in enumerate(groups, 1):
                print(f"\n--- Group {j}/{len(groups)} ---")
                
                success = await self.post_to_group(group, message)
                
                if success:
                    successful_groups.append(group)
                else:
                    failed_groups.append(group)
                
                if j < len(groups):
                    print(f"⏳ Waiting {BETWEEN_GROUPS_WAIT}s before next group...")
                    await asyncio.sleep(BETWEEN_GROUPS_WAIT + random.uniform(0, 2))
            
            # Mark product as posted if at least one group succeeded
            if successful_groups:
                self.product_loader.mark_as_posted(product)
                successful_products += 1
                print(f"\n✅ Product '{product_name}' posted to {len(successful_groups)} groups")
            else:
                failed_products += 1
                print(f"\n❌ Product '{product_name}' failed to post")
            
            if failed_groups:
                print(f"⚠️ Failed groups: {failed_groups}")
            
            # Only wait between products if posting more than 1
            if i < len(selected) and len(selected) > 1:
                print(f"\n⏳ Waiting {BETWEEN_PRODUCTS_WAIT}s before next product...")
                await asyncio.sleep(BETWEEN_PRODUCTS_WAIT + random.uniform(0, 2))
        
        # Summary
        stats = self.product_loader.get_stats()
        print("\n" + "=" * 60)
        print("📊 POSTING SUMMARY")
        print("=" * 60)
        print(f"✅ Successful products: {successful_products}")
        print(f"❌ Failed products: {failed_products}")
        print(f"📱 Groups used: {len(groups)}")
        print(f"📦 Pending remaining: {stats['pending']}")
        print(f"⏳ Link preview max delay: {LINK_PREVIEW_DELAY}s")
        print("=" * 60)
        
        # Print failed groups summary
        self.failed_tracker.print_summary()
        
        # Auto-reset when all products are posted
        if stats['pending'] == 0:
            print("\n🎉 All products are posted!")
            print("🔄 Auto-resetting all products to pending for fresh start...")
            self.product_loader.reset_all_products()
            print("✅ Products reset! Ready for next round.")
        
        print(f"\n✅ Posting complete! {successful_products} product(s) posted.")