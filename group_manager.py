"""
Group Manager Module
====================
Handles advanced group management:
1. Navigate to core groups
2. Get invite links
3. Update group descriptions with standardized message
4. Save/update links in data/links/group_links.json with proper category

USAGE: This module does NOT handle its own login.
       It receives page and context from the main bot.
"""

import json
import asyncio
import random
import re
import pyperclip
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
    "short": 1,          # Quick pauses between actions
    "medium": 2,         # Standard wait for elements to load
    "long": 3,           # Wait for panels to open/close
    "extra": 3,          # Wait for clipboard, saves, etc.
    "scroll": 2,         # Wait after scrolling
    "click": 1,          # Wait after clicking
    "type": 0.1,           # Wait between typing characters
    "between_groups": 3.0, # Wait between processing groups
}

# Typing delays (in milliseconds)
TYPING_DELAYS = {
    "min": 5,   # Minimum ms between keystrokes
    "max": 15,  # Maximum ms between keystrokes
}

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
# DESCRIPTION GENERATOR (WITH STRATEGIC SPACING)
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
# GROUP MANAGER CLASS (FULLY FIXED)
# ============================================================

class GroupManager:
    def __init__(self):
        self.page = None
        self.context = None
        self.blacklist = load_blacklist()
        self.links_manager = GroupLinksManager()
    
    # ============================================================
    # 1. OPEN GROUP
    # ============================================================
    
    async def open_group(self, group_name: str) -> bool:
        """Open a group by name"""
        print(f"  🔍 Opening: {group_name}")
        
        if group_name in self.blacklist.get("groups", []):
            print(f"  ⚠️ Group '{group_name}' is blacklisted. Skipping.")
            return False
        
        for attempt in range(2):
            try:
                # Click search
                search_selectors = [
                    'div[data-testid="chat-list-search"]',
                    'button[aria-label="Search"]',
                    'div[role="textbox"]'
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
                    'div[data-testid="chat-list-search"] input'
                ]
                
                typed = False
                for selector in input_selectors:
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
                            await asyncio.sleep(DELAYS["long"])
                            group_found = True
                            print(f"  ✅ Opened: {group_name}")
                            return True
                    except:
                        continue
                
                if not group_found:
                    chats = await self.page.query_selector_all('div[role="row"]')
                    for chat in chats:
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
    # 2. OPEN GROUP INFO
    # ============================================================
    
    async def open_group_info(self) -> bool:
        """Open group info by clicking the group name in header"""
        print(f"    🔍 Opening group info...")
        
        # Try clicking the header
        try:
            header = await self.page.query_selector('header[data-testid="conversation-header"]')
            if header:
                await header.click()
                await asyncio.sleep(DELAYS["long"])
                print(f"    ✅ Opened group info by clicking header")
                return True
        except:
            pass
        
        # Try clicking the group name
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
    # 3. GO BACK FROM INVITE SECTION
    # ============================================================
    
    async def go_back_from_invite(self) -> bool:
        """Go back from invite section using the provided selectors"""
        print(f"    🔍 Going back from invite section...")
        
        # BEST: Uses aria-label
        # GOOD: Uses button with aria-label
        # GOOD: Uses data-tab
        back_selectors = [
            '[aria-label="Back"]',                    # BEST
            'button[aria-label="Back"]',              # GOOD
            '[data-tab="2"][aria-label="Back"]',      # GOOD
            'header button:first-child'               # FALLBACK
        ]
        
        for selector in back_selectors:
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
        
        # Try clicking the header as fallback
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
    # 4. GET GROUP LINK (WITH PYPERCLIP)
    # ============================================================
    
    async def get_group_link(self, group_name: str) -> Optional[str]:
        """Get the invite link for a group using pyperclip"""
        print(f"  🔗 Getting link for: {group_name}")
        
        try:
            # STEP 1: Open group info
            if not await self.open_group_info():
                return None
            
            await asyncio.sleep(DELAYS["long"])
            
            # STEP 2: Scroll down to find invite section
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
            
            # STEP 3: Find and click "Invite to group via link"
            invite_found = False
            
            invite_selectors = [
                '[data-testid="cell-frame-container"]:has-text("Invite to group via link")',
                'div[role="button"]:has-text("Invite to group via link")',
                'div:has-text("Invite to group via link")',
                'button:has-text("Invite")'
            ]
            
            for selector in invite_selectors:
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
            
            # STEP 4: Click Copy Link button
            print(f"    🔍 Clicking copy link...")
            
            copy_selectors = [
                '[data-testid="li-copy-link"]',
                '[aria-label="Copy link"]',
                'button:has-text("Copy link")'
            ]
            
            copy_clicked = False
            for selector in copy_selectors:
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
            
            # ============================================================
            # STEP 5: GET LINK FROM CLIPBOARD USING PYPERCLIP
            # ============================================================
            
            print(f"    📋 Reading link from clipboard...")
            
            link_text = None
            for attempt in range(3):
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
            
            # ============================================================
            # FALLBACK: Ctrl+V verification
            # ============================================================
            
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
            
            # ============================================================
            # FALLBACK: Scan page
            # ============================================================
            
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
    # 5. UPDATE GROUP DESCRIPTION (SUPER SIMPLE - FIXED SAVE)
    # ============================================================

    async def update_group_description(self, group_name: str, description: str) -> bool:
        """Update the group description - click edit, wait 2s, type, save"""
        print(f"  📝 Updating description for: {group_name}")
        
        try:
            # ============================================================
            # STEP 1: GO BACK FROM INVITE SECTION
            # ============================================================
            print(f"    🔍 Going back from invite section...")
            
            back_selectors = [
                '[aria-label="Back"]',                    # BEST
                'button[aria-label="Back"]',              # GOOD
                '[data-tab="2"][aria-label="Back"]',      # GOOD
                'header button:first-child'               # FALLBACK
            ]
            
            went_back = False
            for selector in back_selectors:
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
            
            # Brief wait for panel to settle
            await asyncio.sleep(2)
            
            # ============================================================
            # STEP 2: FIND AND CLICK EDIT BUTTON
            # ============================================================
            print(f"    🔍 Looking for edit button...")
            
            edit_clicked = False
            
            # Try edit button selectors
            edit_selectors = [
                '[aria-label="Edit group description"]',                 # BEST
                'button[aria-label="Edit group description"]',           # GOOD
                '[data-testid="pencil-refreshed"]',                     # GOOD
                '[data-testid="group-info-drawer-description-title-input-empty-placeholder"]'  # ADD DESCRIPTION
            ]
            
            for selector in edit_selectors:
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
            
            # If no edit button, try clicking the description section
            if not edit_clicked:
                print(f"    🔍 Edit button not found, clicking description section...")
                desc_selectors = [
                    '[data-testid="group-info-drawer-description-container"]',
                    '[data-testid="group-description"]'
                ]
                
                for selector in desc_selectors:
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
            
            # ============================================================
            # STEP 3: WAIT 2 SECONDS FOR EDIT MODE
            # ============================================================
            print(f"    ⏳ Waiting 2 seconds for edit mode...")
            await asyncio.sleep(2)
            
            # ============================================================
            # STEP 4: CLEAR AND TYPE (cursor is already there)
            # ============================================================
            print(f"    🔍 Clearing existing content...")
            await self.page.keyboard.press('Control+A')
            await asyncio.sleep(0.5)
            await self.page.keyboard.press('Backspace')
            await asyncio.sleep(0.5)
            print(f"    ✅ Cleared existing content")
            
            print(f"    📝 Typing description...")
            for char in description:
                await self.page.keyboard.type(char, delay=random.randint(5, 15))
            
            await asyncio.sleep(0.5)
            print(f"    ✅ Description typed")
            
            # ============================================================
            # STEP 5: SAVE WITH ENTER (NOT CTRL+ENTER)
            # ============================================================
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
    # 6. PROCESS SINGLE GROUP
    # ============================================================
    
    async def process_group(self, group_name: str) -> dict:
        """Process a single group - get link and update description"""
        result = {
            "group": group_name,
            "success": False,
            "link": None,
            "description_updated": False,
            "category": "core"
        }
        
        try:
            # 1. Open the group
            if not await self.open_group(group_name):
                print(f"  ❌ Failed to open group: {group_name}")
                return result
            
            await asyncio.sleep(DELAYS["short"])
            
            # 2. Get invite link
            link = await self.get_group_link(group_name)
            if not link:
                print(f"  ❌ No link found for: {group_name}")
                return result
            
            result["link"] = link
            print(f"  ✅ Link retrieved successfully")
            
            # 3. Generate description with the new link
            description = generate_group_description(group_name, link)
            
            # 4. Update group description
            if await self.update_group_description(group_name, description):
                result["description_updated"] = True
                print(f"  ✅ Description updated")
            else:
                print(f"  ⚠️ Description update failed")
            
            # 5. Determine category and save
            category = get_group_category(group_name)
            result["category"] = category
            platform = get_group_platform(group_name)
            
            # 6. Save to JSON
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
    # 7. MANAGE ALL GROUPS
    # ============================================================
    
    async def manage_all_groups(self):
        """Run all management tasks on all core groups"""
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
            print(f"\n{'='*60}")
            print(f"📱 Processing: {group_name}")
            print(f"{'='*60}")
            
            result = await self.process_group(group_name)
            
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
                delay = random.uniform(2, DELAYS["between_groups"] + 2)
                print(f"⏳ Waiting {delay:.1f}s before next group...")
                await asyncio.sleep(delay)
        
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
        print("=" * 60)
        
        all_groups = self.links_manager.get_all_groups()
        print(f"\n📋 Total groups in data/links/group_links.json: {len(all_groups)}")
        for g in all_groups[:5]:
            print(f"  - [{g.get('category', 'core')}] {g.get('name')}: {g.get('url')[:40]}...")
        if len(all_groups) > 5:
            print(f"  ... and {len(all_groups) - 5} more")
        print("=" * 60)
        
        return results