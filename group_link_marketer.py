"""
Group Link Marketer Module
==========================
Strategically markets group links to other groups.
- Reads links from data/links/group_links.json
- Stores discovered links in data/links/new_group_links.json
- Matches group categories with target group categories
- Sends invitation messages with group links
- Tracks which links were shared to which groups
- Prevents duplicate sharing
- Avoids posting core links to core groups
- Scans groups for new links when entering
- Auto-resets when all groups have been posted to

FLOW: Open target group → Post link → Scan for new links → Store → Next

USAGE: This module does NOT handle its own login.
       It receives page and context from the main bot.
"""

import json
import random
import asyncio
import re
import shutil
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Optional, Set
from playwright.async_api import async_playwright

# ============================================================
# IMPORTS
# ============================================================

from target_groups import (
    CORE_GROUPS,
    MARKETING_GROUPS,
    TARGET_GROUPS,
    GROUP_CATEGORIES,
    get_groups_by_category
)

# ============================================================
# CONFIGURATION
# ============================================================

BASE_DIR = Path(__file__).parent
DATA_DIR = BASE_DIR / "data"
LINKS_DIR = DATA_DIR / "links"
GROUP_LINKS_FILE = LINKS_DIR / "group_links.json"
POSTED_LINKS_FILE = LINKS_DIR / "posted_links.json"
NEW_GROUP_LINKS_FILE = LINKS_DIR / "new_group_links.json"

# Create directories
DATA_DIR.mkdir(parents=True, exist_ok=True)
LINKS_DIR.mkdir(parents=True, exist_ok=True)

# ============================================================
# SCROLL CONFIGURATION
# ============================================================

# Number of times to scroll up when scanning for new links
# Higher = more messages scanned (10 = ~50-100 messages)
SCROLL_COUNT = 10

# Maximum scrolls per group (safety limit to prevent infinite loops)
MAX_SCROLL_LIMIT = 50

# ============================================================
# DELAY CONFIGURATION
# ============================================================

DELAYS = {
    "short": 1,
    "medium": 2,
    "long": 3,
    "extra": 3.5,
    "between_messages": 4,
}

# ============================================================
# CATEGORY MAPPING (Group Category → Target Group Categories)
# ============================================================

CATEGORY_TARGET_MAP = {
    "nairobi": ["general", "business", "communities"],
    "mombasa": ["general", "business"],
    "eldoret": ["general", "business"],
    "kakamega": ["general", "business"],
    "kisumu": ["general", "business"],
    "nakuru": ["general", "business"],
    "general": ["general", "business", "communities"],
    "blackmarket": ["general", "business", "blackmarket"],
    "automotive": ["general", "automotive", "business"],
    "property": ["general", "property", "business"],
    "fashion": ["general", "fashion", "business"],
    "electronics": ["general", "electronics", "business"],
    "furniture": ["general", "business"],
    "education": ["general", "education", "business"],
    "communities": ["communities", "general"],
    "business": ["general", "business"],
    "core": ["general", "business", "communities"],
    "marketing": ["general", "business", "communities"],
}

# ============================================================
# MESSAGE TEMPLATES
# ============================================================

def get_message_template(category: str, group_name: str, link: str, description: str = "") -> str:
    """Generate marketing message based on category"""
    
    # Use description from the links file if available
    if description and description.strip():
        return description
    
    # Otherwise use category-specific templates
    templates = {
        "business": f"""💼 *BUSINESS NETWORKING* 💼

🚀 *{group_name}*

🔗 {link}

Connect with fellow entrepreneurs and business owners!
- 🤝 Networking opportunities
- 💡 Business insights
- 📈 Growth strategies

Join us today! 🚀

#BusinessNetworking #KenyaBusiness #Entrepreneurs
""",
        "property": f"""🏠 *REAL ESTATE & PROPERTY* 🏠

🏘️ *{group_name}*

🔗 {link}

Find your dream property or connect with:
- 🏡 Property listings
- 📍 Land deals
- 🏢 Commercial spaces
- 🤝 Real estate professionals

Join the conversation! 🏠

#RealEstate #PropertyKenya #Housing
""",
        "automotive": f"""🚗 *AUTOMOTIVE COMMUNITY* 🚗

🚘 *{group_name}*

🔗 {link}

Connect with car enthusiasts and professionals!
- 🚙 Cars for sale
- 🔧 Maintenance tips
- 🏎️ Industry news
- 🤝 Networking

Join us! 🚗

#Automotive #CarsKenya #CarCommunity
""",
        "fashion": f"""👗 *FASHION COMMUNITY* 👗

👘 *{group_name}*

🔗 {link}

Connect with fashion lovers and industry professionals!
- 👚 Latest trends
- 🛍️ Shopping deals
- 📸 Style inspiration
- 🤝 Networking

Join the fashion family! 👗

#FashionKenya #Style #Community
""",
        "electronics": f"""📱 *TECH & ELECTRONICS* 📱

💻 *{group_name}*

🔗 {link}

Connect with tech enthusiasts and professionals!
- 📱 Latest gadgets
- 💻 Tech tips
- 🔌 Electronics deals
- 🤝 Networking

Join the tech revolution! 📱

#TechKenya #Electronics #Gadgets
""",
        "education": f"""📚 *EDUCATION & LEARNING* 📚

🎓 *{group_name}*

🔗 {link}

Connect with learners and educators!
- 📖 Learning resources
- 🎓 Career guidance
- 💡 Knowledge sharing
- 🤝 Networking

Join the learning community! 📚

#EducationKenya #Learning #Community
""",
        "communities": f"""🌍 *COMMUNITY CONNECT* 🌍

🤝 *{group_name}*

🔗 {link}

Connect with your community!
- 👥 Meet new people
- 💬 Share ideas
- 🌱 Grow together
- 🤝 Build connections

Join the community! 🌍

#Community #Kenya #Networking
"""
    }
    
    template = templates.get(category, f"""📢 *JOIN OUR COMMUNITY!* 📢

🤝 *{group_name}*

🔗 {link}

Connect with like-minded individuals!
Share ideas, learn, and grow together! 🌱

📲 Click the link above to join!

#Community #Networking #Kenya
""")
    
    return template


# ============================================================
# POSTED LINKS MANAGER (WITH AUTO-RESET)
# ============================================================

class PostedLinksManager:
    """Manages posted links to prevent duplicates with auto-reset"""
    
    def __init__(self, max_groups_per_source: int = 3):
        self.max_groups_per_source = max_groups_per_source
        self.posted_links = self._load()
    
    def _load(self) -> dict:
        """Load posted links from file"""
        if POSTED_LINKS_FILE.exists():
            try:
                with open(POSTED_LINKS_FILE, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except:
                return {"posted": [], "last_updated": None, "reset_count": 0}
        return {"posted": [], "last_updated": None, "reset_count": 0}
    
    def _save(self):
        """Save posted links to file"""
        self.posted_links["last_updated"] = datetime.now().isoformat()
        with open(POSTED_LINKS_FILE, 'w', encoding='utf-8') as f:
            json.dump(self.posted_links, f, indent=2, ensure_ascii=False)
    
    def mark_posted(self, source_group: str, target_group: str, link: str):
        """Mark a link as posted to a group"""
        entry = {
            "source_group": source_group,
            "target_group": target_group,
            "link": link,
            "posted_at": datetime.now().isoformat()
        }
        self.posted_links["posted"].append(entry)
        self._save()
    
    def is_already_posted(self, source_group: str, target_group: str) -> bool:
        """Check if a link has already been posted to a group"""
        for entry in self.posted_links["posted"]:
            if entry["source_group"] == source_group and entry["target_group"] == target_group:
                return True
        return False
    
    def get_all_posted(self) -> List[dict]:
        """Get all posted links"""
        return self.posted_links["posted"]
    
    def get_all_links(self) -> Set[str]:
        """Get all posted links as a set"""
        return {entry["link"] for entry in self.posted_links["posted"]}
    
    def get_posted_count_by_source(self, source_group: str) -> int:
        """Get count of groups posted to by a specific source"""
        return len([entry for entry in self.posted_links["posted"] if entry["source_group"] == source_group])
    
    def get_target_groups_for_source(self, source_group: str) -> Set[str]:
        """Get all target groups already posted to by a source"""
        return {entry["target_group"] for entry in self.posted_links["posted"] if entry["source_group"] == source_group}
    
    def reset_for_source(self, source_group: str) -> int:
        """
        Reset posted links for a specific source (keep only latest max_groups_per_source)
        Returns number of entries removed
        """
        # Get entries for this source
        source_entries = [e for e in self.posted_links["posted"] if e["source_group"] == source_group]
        
        if not source_entries:
            return 0
        
        # Keep only the latest max_groups_per_source
        keep_count = min(len(source_entries), self.max_groups_per_source)
        entries_to_keep = sorted(source_entries, key=lambda x: x["posted_at"], reverse=True)[:keep_count]
        
        # Filter out entries not in keep list
        new_posted = []
        removed_count = 0
        
        for entry in self.posted_links["posted"]:
            if entry["source_group"] == source_group:
                if entry in entries_to_keep:
                    new_posted.append(entry)
                else:
                    removed_count += 1
            else:
                new_posted.append(entry)
        
        self.posted_links["posted"] = new_posted
        self.posted_links["reset_count"] = self.posted_links.get("reset_count", 0) + 1
        self._save()
        
        return removed_count
    
    def reset_all(self) -> int:
        """Reset ALL posted links"""
        count = len(self.posted_links["posted"])
        self.posted_links["posted"] = []
        self.posted_links["reset_count"] = self.posted_links.get("reset_count", 0) + 1
        self._save()
        return count
    
    def get_summary(self) -> dict:
        """Get summary of posted links"""
        posted = self.posted_links["posted"]
        sources = set(entry["source_group"] for entry in posted)
        
        summary = {
            "total_posted": len(posted),
            "unique_sources": len(sources),
            "reset_count": self.posted_links.get("reset_count", 0),
            "last_updated": self.posted_links.get("last_updated"),
            "sources": {}
        }
        
        for source in sources:
            source_entries = [e for e in posted if e["source_group"] == source]
            summary["sources"][source] = {
                "count": len(source_entries),
                "targets": [e["target_group"] for e in source_entries]
            }
        
        return summary


# ============================================================
# GROUP LINK MARKETER CLASS
# ============================================================

class GroupLinkMarketer:
    """
    Strategically markets group links to other groups.
    
    NOTE: This class receives page and context from the main bot.
          It does NOT handle its own login.
    """
    
    def __init__(self, scroll_count: int = SCROLL_COUNT):
        self.page = None
        self.context = None
        self.scroll_count = scroll_count
        self.group_links = self._load_group_links()
        self.new_group_links = self._load_new_links()
        self.posted_manager = PostedLinksManager(max_groups_per_source=3)
    
    # ============================================================
    # DATA LOADING
    # ============================================================
    
    def _load_group_links(self) -> dict:
        """Load group links from group_links.json"""
        if GROUP_LINKS_FILE.exists():
            try:
                with open(GROUP_LINKS_FILE, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except:
                return {"groups": []}
        return {"groups": []}
    
    def _load_new_links(self) -> dict:
        """Load new links from new_group_links.json"""
        if NEW_GROUP_LINKS_FILE.exists():
            try:
                with open(NEW_GROUP_LINKS_FILE, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except:
                return {"groups": []}
        return {"groups": []}
    
    def _link_exists_in_system(self, link: str) -> bool:
        """Check if a link already exists in either file"""
        # Check in main group_links.json
        for group in self.group_links.get("groups", []):
            if group.get("url") == link:
                return True
        
        # Check in new_group_links.json
        for group in self.new_group_links.get("groups", []):
            if group.get("url") == link:
                return True
        
        return False
    
    def _save_new_links(self):
        """Save new links to file"""
        self.new_group_links["total_groups"] = len(self.new_group_links.get("groups", []))
        self.new_group_links["last_updated"] = datetime.now().isoformat()
        
        with open(NEW_GROUP_LINKS_FILE, 'w', encoding='utf-8') as f:
            json.dump(self.new_group_links, f, indent=2, ensure_ascii=False)
    
    # ============================================================
    # OPEN GROUP
    # ============================================================
    
    async def _open_group(self, group_name: str) -> bool:
        """Open a group"""
        print(f"    🔍 Opening: {group_name}")
        
        try:
            # Click search
            search_selectors = [
                'div[data-testid="chat-list-search"]',
                'div[role="textbox"]',
                'button[aria-label="Search"]',
            ]
            
            search_clicked = False
            for selector in search_selectors:
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
            
            # Type group name
            input_selectors = [
                'input[type="text"]',
                'div[data-testid="chat-list-search"] input',
            ]
            
            for selector in input_selectors:
                try:
                    search_input = await self.page.query_selector(selector)
                    if search_input:
                        await search_input.click()
                        await search_input.fill("")
                        await asyncio.sleep(DELAYS["short"])
                        await search_input.type(group_name, delay=80)
                        await asyncio.sleep(DELAYS["medium"])
                        break
                except:
                    continue
            
            # Click group
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
                        await asyncio.sleep(DELAYS["medium"])
                        group_found = True
                        print(f"    ✅ Opened: {group_name}")
                        break
                except:
                    continue
            
            if not group_found:
                # Try scanning all chats
                chats = await self.page.query_selector_all('div[role="row"]')
                for chat in chats:
                    try:
                        text = await chat.inner_text()
                        if group_name.lower() in text.lower():
                            await chat.click()
                            await asyncio.sleep(DELAYS["medium"])
                            print(f"    ✅ Opened: {group_name}")
                            return True
                    except:
                        continue
                
                print(f"    ❌ Group not found: {group_name}")
                return False
            
            return True
            
        except Exception as e:
            print(f"    ❌ Error opening: {e}")
            return False
    
    # ============================================================
    # SCAN GROUP FOR NEW LINKS (WITH CONFIGURABLE SCROLL)
    # ============================================================
    
    async def _scan_group_for_new_links(self, group_name: str) -> List[str]:
        """
        Scan a group for new links - scrolls up with balanced timing.
        """
        new_links = []
        found_links = set()
        
        try:
            # Brief initial wait
            await asyncio.sleep(DELAYS["short"])
            
            print(f"        📜 Scanning messages for links (scrolling {self.scroll_count} times)...")
            
            # Get initial message count
            messages = await self.page.query_selector_all('div[data-testid="message-container"]')
            current_count = len(messages)
            previous_count = current_count
            no_change_count = 0
            
            for scroll_count in range(1, self.scroll_count + 1):
                # ============================================================
                # STEP 1: SCROLL UP (multiple methods)
                # ============================================================
                try:
                    # Method 1: JavaScript scroll
                    await self.page.evaluate('''
                        () => {
                            const container = document.querySelector('div[data-testid="message-container"]');
                            if (container) {
                                container.scrollTop = Math.max(0, container.scrollTop - 500);
                            }
                        }
                    ''')
                except:
                    pass
                
                try:
                    # Method 2: PageUp key
                    await self.page.keyboard.press('PageUp')
                except:
                    pass
                
                try:
                    # Method 3: Arrow Up multiple times
                    for _ in range(3):
                        await self.page.keyboard.press('ArrowUp')
                        await asyncio.sleep(0.05)
                except:
                    pass
                
                # ============================================================
                # STEP 2: BRIEF WAIT FOR MESSAGES TO LOAD
                # ============================================================
                # Just enough time for WhatsApp to load messages
                await asyncio.sleep(0.8)  # 0.8 seconds per scroll
                
                # ============================================================
                # STEP 3: CHECK IF NEW MESSAGES LOADED
                # ============================================================
                messages = await self.page.query_selector_all('div[data-testid="message-container"]')
                current_count = len(messages)
                
                # Show progress every 5 scrolls
                if scroll_count % 5 == 0 or scroll_count == 1:
                    print(f"        📜 Scrolled {scroll_count}/{self.scroll_count} times, loaded {current_count} messages")
                
                # If no new messages for 3 consecutive scrolls, we're at the top
                if current_count == previous_count:
                    no_change_count += 1
                    if no_change_count >= 3:
                        print(f"        ✅ Reached top of chat")
                        break
                else:
                    no_change_count = 0
                    previous_count = current_count
            
            # ============================================================
            # STEP 4: SCAN ALL MESSAGES
            # ============================================================
            print(f"        🔍 Scanning {current_count} messages for links...")
            
            messages = await self.page.query_selector_all('div[data-testid="message-container"]')
            
            for msg in messages:
                try:
                    text = await msg.text_content()
                    if text and "whatsapp.com" in text:
                        link_match = re.search(r'https?://[^\s]+whatsapp\.com[^\s]*', text)
                        if link_match:
                            link = link_match.group(0)
                            
                            if not self._link_exists_in_system(link) and link not in found_links:
                                found_links.add(link)
                                new_links.append(link)
                                print(f"        ✅ Found new link: {link[:50]}...")
                except:
                    continue
            
            print(f"        📊 Found {len(new_links)} new links in {group_name}")
            return new_links
            
        except Exception as e:
            print(f"    ⚠️ Error scanning: {e}")
            return new_links
    
    # ============================================================
    # STORE NEW LINKS
    # ============================================================
    
    def _store_new_links(self, group_name: str, new_links: List[str], category: str = "general"):
        """Store new links found in a group to new_group_links.json"""
        if not new_links:
            return
        
        print(f"    💾 Storing {len(new_links)} new link(s) from {group_name} in new_group_links.json")
        
        for link in new_links:
            # Check if link already exists (avoid duplicates)
            if self._link_exists_in_system(link):
                print(f"        ⏭️ Link already exists: {link[:40]}...")
                continue
            
            # Add to new_group_links.json
            self.new_group_links["groups"].append({
                "name": f"Found in {group_name}",
                "url": link,
                "category": category,
                "status": "pending",
                "source_group": group_name,
                "discovered_at": datetime.now().isoformat(),
                "description": f"Auto-discovered link from {group_name}",
                "posted_date": None,
                "posted_time": None,
                "last_updated": datetime.now().isoformat()
            })
            
            print(f"        ✅ Stored new link: {link[:40]}...")
        
        # Save the updated data
        self._save_new_links()
    
    # ============================================================
    # SEND LINK TO GROUP (WITH WORKING SELECTORS)
    # ============================================================
    
    async def send_link_to_group(self, source_group: str, target_group: str, 
                                  link: str, message: str) -> bool:
        """
        Send a group link to another group
        Uses working compose box selectors from group_poster.py
        """
        print(f"\n    📤 Posting link to: {target_group}")
        
        try:
            # Find compose box using working selectors
            print(f"    🔍 Finding compose box...")
            
            compose_selectors = [
                '#main > footer > div > span > div > div > div > div > div.x1hx0egp > p',
                'div[contenteditable="true"]',
                'div[role="textbox"]',
                'footer div[contenteditable="true"]',
                'p[contenteditable="true"]',
                'div[data-testid="conversation-compose-box"]',
                'div[aria-label="Type a message"]'
            ]
            
            compose = None
            for attempt in range(3):
                for selector in compose_selectors:
                    try:
                        compose = await self.page.query_selector(selector)
                        if compose:
                            is_visible = await compose.is_visible()
                            if is_visible:
                                print(f"    ✅ Compose box found: {selector}")
                                break
                    except:
                        continue
                
                if compose:
                    break
                
                print(f"    ⏳ Waiting for compose box... (attempt {attempt+1}/3)")
                await asyncio.sleep(DELAYS["medium"])
            
            if not compose:
                print(f"    ❌ Compose box not found")
                return False
            
            # Click and clear
            await compose.click()
            await asyncio.sleep(DELAYS["short"])
            await compose.fill("")
            await asyncio.sleep(DELAYS["short"])
            
            # Type message with line breaks using Shift+Enter
            print(f"    📝 Typing message...")
            lines = message.split('\n')
            
            for line_index, line in enumerate(lines):
                for char in line:
                    await compose.type(char, delay=random.randint(40, 100))
                    if random.random() < 0.02:
                        await asyncio.sleep(random.uniform(0.2, 0.5))
                
                if line_index < len(lines) - 1:
                    await self.page.keyboard.press('Shift+Enter')
                    await asyncio.sleep(random.uniform(0.1, 0.3))
            
            await asyncio.sleep(DELAYS["medium"])
            print(f"    ✅ Message typed with {len(lines)} lines")
            
            # ============================================================
            # SMART LINK PREVIEW DETECTION
            # ============================================================
            if "http" in message or "www." in message:
                print(f"    ⏳ Waiting for link preview to load...")
                
                preview_loaded = False
                
                for attempt in range(5):  # Max 5 seconds
                    await asyncio.sleep(1)
                    
                    try:
                        # Check for preview elements
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
                                    print(f"    ✅ Link preview loaded! (took {attempt+1}s)")
                                    break
                            except:
                                continue
                        
                        if preview_loaded:
                            break
                        
                    except Exception as e:
                        pass
                
                if not preview_loaded:
                    print(f"    ⚠️ Link preview didn't appear, proceeding anyway...")
            
            # ============================================================
            # SEND WITH WORKING SELECTOR
            # ============================================================
            print(f"    🔍 Finding send button...")
            
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
                        print(f"    ✅ Send button found: {selector}")
                        break
                except:
                    continue
            
            if not send:
                print(f"    ❌ Send button not found")
                return False
            
            await send.click()
            await asyncio.sleep(DELAYS["long"])
            print(f"    ✅ Link posted to {target_group}")
            
            # Mark as posted
            self.posted_manager.mark_posted(source_group, target_group, link)
            return True
                
        except Exception as e:
            print(f"    ❌ Error posting to {target_group}: {e}")
            return False
    
    # ============================================================
    # STRATEGIC MARKETING (WITH AUTO-RESET)
    # ============================================================
    
    async def market_group_links(self, group_filter: str = "core"):
        """
        Strategically market group links to other groups.
        FLOW: Open group → Post link → Scan for new links → Store → Next
        Auto-resets when all groups have been posted to.
        
        Args:
            group_filter: 'core', 'all', or specific category
        """
        print("\n" + "=" * 60)
        print("📢 MARKETING GROUP LINKS")
        print("=" * 60)
        print(f"📜 Scroll count for scanning: {self.scroll_count}")
        print("=" * 60)
        
        # Get all groups with links from group_links.json
        groups_with_links = []
        for group in self.group_links.get("groups", []):
            group_name = group.get("name")
            url = group.get("url")
            category = group.get("category", "general")
            description = group.get("description", "")
            
            if url and "whatsapp.com" in url:
                groups_with_links.append({
                    "name": group_name,
                    "url": url,
                    "category": category,
                    "description": description
                })
        
        print(f"📋 Groups with links: {len(groups_with_links)}")
        
        if not groups_with_links:
            print("❌ No groups with links found. Run group_manager.py first.")
            return
        
        # Filter based on group_filter
        if group_filter == "core":
            source_groups = [g for g in groups_with_links if g["name"] in CORE_GROUPS]
            filter_name = "Core Groups"
        elif group_filter == "all":
            source_groups = groups_with_links
            filter_name = "All Groups"
        else:
            source_groups = [g for g in groups_with_links if g["category"] == group_filter]
            filter_name = f"{group_filter.upper()} Groups"
        
        print(f"📋 {filter_name} with links: {len(source_groups)}")
        
        if not source_groups:
            print(f"❌ No {filter_name.lower()} with links found.")
            return
        
        successful = 0
        failed = 0
        skipped = 0
        new_links_found = 0
        total_reset_entries = 0
        
        for source in source_groups:
            source_group = source["name"]
            link = source["url"]
            category = source["category"]
            description = source["description"]
            
            print(f"\n{'='*60}")
            print(f"📱 Marketing: {source_group} ({category})")
            print(f"{'='*60}")
            
            # Get target group categories
            target_categories = CATEGORY_TARGET_MAP.get(category, ["general"])
            
            # Get target groups from those categories
            target_groups = []
            for target_cat in target_categories:
                target_groups.extend(get_groups_by_category(target_cat))
            
            # Remove duplicates and exclude core groups
            target_groups = list(set(target_groups))
            
            # EXCLUDE CORE GROUPS - don't post core links to core groups
            target_groups = [tg for tg in target_groups if tg not in CORE_GROUPS]
            
            # Exclude the source group itself
            target_groups = [tg for tg in target_groups if tg != source_group]
            
            # Get already posted targets
            already_posted_targets = self.posted_manager.get_target_groups_for_source(source_group)
            total_available = len(target_groups)
            already_posted_count = len(already_posted_targets)
            
            print(f"🎯 Target groups: {total_available} total, {already_posted_count} already posted")
            
            # ============================================================
            # AUTO-RESET CHECK: If all groups have been posted to
            # ============================================================
            if total_available > 0 and already_posted_count >= total_available:
                print(f"\n🔄 All {total_available} target groups have been posted to by {source_group}!")
                print(f"   Resetting to allow re-posting (keeping latest {self.posted_manager.max_groups_per_source})...")
                
                removed = self.posted_manager.reset_for_source(source_group)
                total_reset_entries += removed
                print(f"   ✅ Removed {removed} old entries, keeping latest {self.posted_manager.max_groups_per_source}")
                
                # Update already_posted_count after reset
                already_posted_targets = self.posted_manager.get_target_groups_for_source(source_group)
                already_posted_count = len(already_posted_targets)
                print(f"   📊 Now {already_posted_count} entries remain for {source_group}")
            
            # Filter out already posted
            filtered_targets = []
            for tg in target_groups:
                if not self.posted_manager.is_already_posted(source_group, tg):
                    filtered_targets.append(tg)
                else:
                    print(f"    ⏭️ Already posted to: {tg}")
                    skipped += 1
            
            print(f"🎯 Target groups ready: {len(filtered_targets)} (after filtering)")
            
            # If no targets available, skip this source
            if not filtered_targets:
                print(f"   ℹ️ No new targets for {source_group}, skipping...")
                continue
            
            # Randomize order
            random.shuffle(filtered_targets)
            
            # Generate message with description
            message = get_message_template(category, source_group, link, description)
            
            # Process each target group (limit to 3 per source)
            for target_group in filtered_targets[:3]:
                print(f"\n{'='*50}")
                print(f"📌 Processing target: {target_group}")
                print(f"{'='*50}")
                
                # ============================================================
                # STEP 1: Open the target group
                # ============================================================
                print(f"    🔍 Opening target group...")
                if not await self._open_group(target_group):
                    print(f"    ❌ Could not open {target_group}, skipping...")
                    failed += 1
                    continue
                
                # ============================================================
                # STEP 2: POST/MARKET THE LINK FIRST
                # ============================================================
                print(f"\n    📤 Posting link to {target_group}...")
                
                # Double-check not already posted (race condition check)
                if self.posted_manager.is_already_posted(source_group, target_group):
                    print(f"    ⏭️ Already posted (double-check), skipping")
                    skipped += 1
                    continue
                
                success = await self.send_link_to_group(
                    source_group, 
                    target_group, 
                    link, 
                    message
                )
                
                if success:
                    successful += 1
                    print(f"    ✅ Link posted successfully to {target_group}")
                else:
                    failed += 1
                    print(f"    ❌ Failed to post to {target_group}")
                    continue
                
                # ============================================================
                # STEP 3: SCAN FOR NEW LINKS IN THE GROUP
                # ============================================================
                print(f"\n    🔍 Scanning {target_group} for new links...")
                new_links = await self._scan_group_for_new_links(target_group)
                
                if new_links:
                    print(f"    ✅ Found {len(new_links)} new link(s) in {target_group}")
                    self._store_new_links(target_group, new_links, category)
                    new_links_found += len(new_links)
                else:
                    print(f"    ℹ️ No new links found in {target_group}")
                
                # ============================================================
                # STEP 4: RANDOM DELAY BEFORE NEXT GROUP
                # ============================================================
                delay = random.uniform(DELAYS["between_messages"], DELAYS["between_messages"] + 5)
                print(f"\n    ⏳ Waiting {delay:.1f}s before next target...")
                await asyncio.sleep(delay)
        
        # Summary
        print("\n" + "=" * 60)
        print("📊 MARKETING SUMMARY")
        print("=" * 60)
        print(f"✅ Links posted successfully: {successful}")
        print(f"❌ Failed to post: {failed}")
        print(f"⏭️ Skipped (already posted): {skipped}")
        print(f"🆕 New links discovered: {new_links_found}")
        print(f"🔄 Reset entries removed: {total_reset_entries}")
        print(f"📱 Groups marketed: {len(source_groups)}")
        print(f"📋 Total posted: {len(self.posted_manager.get_all_posted())}")
        print(f"📜 Scroll count used: {self.scroll_count}")
        print("=" * 60)
        
        # Show posted links
        posted = self.posted_manager.get_all_posted()
        if posted:
            print(f"\n📋 Recently posted links:")
            for entry in posted[-10:]:  # Show last 10
                print(f"  - {entry['source_group']} → {entry['target_group']}")
        
        return {
            "successful": successful,
            "failed": failed,
            "skipped": skipped,
            "new_links_found": new_links_found,
            "reset_entries": total_reset_entries,
            "total_posted": len(posted)
        }
    
    # ============================================================
    # MARKET SPECIFIC CATEGORY
    # ============================================================
    
    async def market_category(self, category: str):
        """Market links from a specific category to other groups"""
        print(f"\n🎯 Marketing {category.upper()} category groups")
        await self.market_group_links(category)
    
    # ============================================================
    # MARKET CORE GROUPS
    # ============================================================
    
    async def market_core_groups(self):
        """Market only core group links to other groups"""
        print("\n⭐ Marketing CORE groups")
        await self.market_group_links("core")
    
    # ============================================================
    # MARKET ALL GROUPS
    # ============================================================
    
    async def market_all_groups(self):
        """Market all group links to other groups"""
        print("\n🌍 Marketing ALL groups")
        await self.market_group_links("all")
    
    # ============================================================
    # RESET POSTED LINKS (MANUAL)
    # ============================================================
    
    def reset_posted_links(self):
        """Manually reset all posted links tracking"""
        print(f"\n🔄 Manually resetting all posted links...")
        
        # Back up the current file
        if POSTED_LINKS_FILE.exists():
            backup_file = POSTED_LINKS_FILE.with_suffix('.json.bak')
            shutil.copy(POSTED_LINKS_FILE, backup_file)
            print(f"   ✅ Backed up to: {backup_file}")
        
        # Reset
        removed = self.posted_manager.reset_all()
        print(f"   ✅ Removed {removed} entries. Ready for fresh start!")
        return removed