"""
Group Poster Module
===================
Handles all WhatsApp group posting functionality:
- Loading products from JSON files
- Opening groups
- Posting messages with line breaks
- Link preview waiting
- Product status management
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

# Product files
WA_PRODUCTS_FILE = PRODUCTS_DIR / "wa_products.json"
INSTAGRAM_POSTS_FILE = PRODUCTS_DIR / "instagram_posts.json"
FACEBOOK_POSTS_FILE = PRODUCTS_DIR / "facebook_posts.json"

# Create directories
PRODUCTS_DIR.mkdir(parents=True, exist_ok=True)

# ============================================================
# TIMING CONFIGURATION
# ============================================================

# Typing delays (milliseconds per character - SLOW & HUMAN)
HUMAN_TYPING_DELAY_MIN = 100
HUMAN_TYPING_DELAY_MAX = 250

# Page interaction delays
SEARCH_WAIT = 5
OPEN_WAIT = 5
FIND_COMPOSE_WAIT = 4
AFTER_TYPING_WAIT = 5
SEND_CONFIRM_WAIT = 6
BETWEEN_GROUPS_WAIT = 6
BETWEEN_PRODUCTS_WAIT = 8
RETRY_DELAY = 5

# Link preview delay (seconds)
LINK_PREVIEW_DELAY = 15

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
    
    def get_product_message(self, product: dict) -> str:
        """Create a marketing message from product data"""
        name = product.get("product_name") or product.get("id") or "Product"
        description = product.get("description") or product.get("caption") or ""
        url = product.get("url") or ""
        source = product.get("source", "unknown")
        
        if not description:
            description = f"Check out this {source} post!"
        
        templates = [
            f"""
🛍️ *NEW CONTENT* 🛍️

✨ *{name}* ✨

📝 {description}

🔗 {url}

Check it out! 🏃‍♂️

📲 DM for inquiries

#KenyaDeals #{name.replace(' ', '')} #Tulia
""",
            f"""
🔥 *HOT CONTENT* 🔥

✨ *{name}* ✨

{description}

🔗 {url}

Don't miss out! 🏃

💬 Inbox for inquiries

#Kenya #{name.replace(' ', '')} #Nunua
""",
            f"""
🎯 *CHECK THIS OUT* 🎯

*{name}*

{description}

📎 {url}

Limited time! 😊

📲 DM for inquiries

#KenyanBusiness #{name.replace(' ', '')} #MarketPlace
"""
        ]
        
        return random.choice(templates)
    
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
        self.is_running = False
    
    # ============================================================
    # GROUP OPENING
    # ============================================================
    
    async def open_group(self, group_name: str) -> bool:
        print(f"  🔍 Opening: {group_name}")
        
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
                                await search_input.type(char, delay=random.randint(80, 150))
                            await asyncio.sleep(SEARCH_WAIT + random.uniform(0, 2))
                            typed = True
                            print(f"    ✅ Typed: {group_name}")
                            break
                    except:
                        continue
                
                if not typed:
                    await self.page.keyboard.type(group_name, delay=100)
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
                    return True
                else:
                    print(f"    ❌ Compose box not found")
                    if attempt < 2:
                        print(f"    🔄 Retrying in {RETRY_DELAY}-{RETRY_DELAY+3}s...")
                        await asyncio.sleep(RETRY_DELAY + random.uniform(0, 3))
                        continue
                    else:
                        return False
                
            except Exception as e:
                print(f"    ❌ Error: {e}")
                if attempt < 2:
                    print(f"    🔄 Retrying in {RETRY_DELAY}-{RETRY_DELAY+3}s...")
                    await asyncio.sleep(RETRY_DELAY + random.uniform(0, 3))
        
        print(f"  ❌ Failed to open: {group_name}")
        return False
    
    # ============================================================
    # POST TO GROUP
    # ============================================================
    
    async def post_to_group(self, group_name: str, message: str) -> bool:
        """
        Post a message to a group
        - Types with line breaks preserved
        - Waits for link preview to load BEFORE sending
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
            
            if self.product_loader.has_url(message):
                print(f"  [7.5/9] ⏳ Waiting for link preview to load...")
                print(f"    ⏳ WhatsApp needs ~15 seconds to generate the preview")
                
                preview_found = False
                preview_selectors = [
                    'div[data-testid="link-preview"]',
                    'div[data-testid="link"]',
                    'div[aria-label="Link preview"]',
                    'div.link-preview',
                    'div[class*="link"]'
                ]
                
                for attempt in range(LINK_PREVIEW_DELAY):
                    await asyncio.sleep(1)
                    
                    for selector in preview_selectors:
                        try:
                            preview = await self.page.query_selector(selector)
                            if preview:
                                is_visible = await preview.is_visible()
                                if is_visible:
                                    preview_found = True
                                    print(f"    ✅ Link preview loaded! (took {attempt+1}s)")
                                    break
                        except:
                            continue
                    
                    if preview_found:
                        break
                    
                    if attempt % 5 == 0 and attempt > 0:
                        print(f"    ⏳ Still loading... ({attempt+1}/{LINK_PREVIEW_DELAY}s)")
                
                if not preview_found:
                    print(f"    ⚠️ Link preview didn't appear, waiting extra 5s...")
                    await asyncio.sleep(5)
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
            return False
    
    # ============================================================
    # POST RANDOM PRODUCTS
    # ============================================================
    
    async def post_random_products(self, count: int = None, groups: List[str] = None):
        """Post random products from the pool"""
        if groups is None:
            groups = TARGET_GROUPS
        
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
        
        if count is None or count > pending_count:
            count = pending_count
        
        print(f"📢 Will post {count} random products")
        
        selected = random.sample(pending_products, count)
        
        print(f"📋 Selected products:")
        for i, p in enumerate(selected, 1):
            source = p.get("source", "unknown")
            name = p.get("product_name") or p.get("id", "Unknown")
            print(f"  {i}. [{source}] {name}")
        
        print(f"\n▶️ Posting to {len(groups)} groups...")
        print("=" * 60)
        
        successful = 0
        failed = 0
        
        for i, product in enumerate(selected, 1):
            product_name = product.get("product_name") or product.get("id", "Product")
            source = product.get("source", "unknown")
            
            print(f"\n{'='*60}")
            print(f"📦 [{i}/{len(selected)}] {source.upper()}: {product_name}")
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
            
            if successful_groups:
                self.product_loader.mark_as_posted(product)
                successful += 1
                print(f"\n✅ Product '{product_name}' posted to {len(successful_groups)} groups")
            else:
                failed += 1
                print(f"\n❌ Product '{product_name}' failed to post")
            
            if failed_groups:
                print(f"⚠️ Failed groups: {failed_groups}")
            
            if i < len(selected):
                print(f"\n⏳ Waiting {BETWEEN_PRODUCTS_WAIT}s before next product...")
                await asyncio.sleep(BETWEEN_PRODUCTS_WAIT + random.uniform(0, 2))
        
        stats = self.product_loader.get_stats()
        print("\n" + "=" * 60)
        print("📊 POSTING SUMMARY")
        print("=" * 60)
        print(f"✅ Successful: {successful}")
        print(f"❌ Failed: {failed}")
        print(f"📱 Groups used: {len(groups)}")
        print(f"📦 Pending remaining: {stats['pending']}")
        print("=" * 60)
        
        if stats['pending'] == 0:
            print("\n🎉 All products are posted!")
            print("🔄 Auto-resetting all products to pending for fresh start...")
            self.product_loader.reset_all_products()
            print("✅ Products reset! Ready for next round.")