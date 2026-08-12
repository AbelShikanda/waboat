"""
Contact Messenger Module
========================
Handles sending occasional messages to contacts:
- New Year wishes
- New Month greetings
- Holiday messages
- Birthday wishes
- Special promotions (very occasional)

USAGE: This module does NOT handle its own login.
       It receives page and context from the main bot.
"""

import json
import random
import asyncio
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Optional

# ============================================================
# IMPORT TARGET AUDIENCE
# ============================================================

from target_audience import INDIVIDUAL_CONTACTS, get_contacts_by_category

# ============================================================
# CONFIGURATION
# ============================================================

BASE_DIR = Path(__file__).parent
DATA_DIR = BASE_DIR / "data"
MESSAGE_HISTORY_FILE = DATA_DIR / "message_history.json"

# Create directories
DATA_DIR.mkdir(parents=True, exist_ok=True)

# ============================================================
# MESSAGE TEMPLATES
# ============================================================

class MessageTemplates:
    """Occasional message templates for different occasions"""
    
    @staticmethod
    def new_year(year: int = None) -> str:
        """New Year message template"""
        if year is None:
            year = datetime.now().year
        return f"""
🎉 *HAPPY NEW YEAR {year}!* 🎉

Wishing you a year filled with:
✨ Success in all your endeavors
💼 Growth in your business
❤️ Joy and happiness with loved ones

May this year bring you everything you've been working towards!

Thank you for being part of our community. Here's to an amazing year ahead! 🥂

#HappyNewYear #NewYear{year} #NewBeginnings
"""
    
    @staticmethod
    def new_month(month: str = None) -> str:
        """New Month message template"""
        if month is None:
            month = datetime.now().strftime("%B")
        return f"""
📅 *HAPPY NEW MONTH!* 📅

Welcome to {month}!

Wishing you:
💰 Abundance in your finances
🚀 Growth in your business
💪 Strength to achieve your goals
😊 Joy in your daily life

Remember, every month is a fresh start. Make this one count!

#HappyNewMonth #{month} #FreshStart #NewBeginnings
"""
    
    @staticmethod
    def holiday(holiday_name: str) -> str:
        """Holiday message template"""
        return f"""
🎊 *HAPPY {holiday_name.upper()}!* 🎊

Wishing you and your loved ones a wonderful celebration!

May this special day bring:
❤️ Love and warmth
😊 Laughter and joy
🌸 Peace and happiness

Enjoy every moment! 🎉

#Happy{holiday_name.replace(' ', '')} #Celebration #Joy
"""
    
    @staticmethod
    def special_occasion(occasion: str, custom_message: str = None) -> str:
        """Custom special occasion message"""
        if custom_message:
            return f"""
🎯 *{occasion.upper()}* 🎯

{custom_message}

Wishing you all the best!

#Occasion #{occasion.replace(' ', '')}
"""
        return f"""
🎯 *{occasion.upper()}* 🎯

Wishing you a wonderful occasion filled with joy and success!

#Occasion #{occasion.replace(' ', '')}
"""
    
    @staticmethod
    def birthday(name: str = "you") -> str:
        """Birthday message template"""
        return f"""
🎂 *HAPPY BIRTHDAY!* 🎂

🎁 Wishing {name} a fantastic day filled with:
🎉 Joy and laughter
💝 Love and blessings
✨ Everything you've been wishing for

May this year be your best one yet! 🥳

#HappyBirthday #BirthdayCelebration #SpecialDay
"""
    
    @staticmethod
    def christmas() -> str:
        """Christmas message template"""
        return """
🎄 *MERRY CHRISTMAS!* 🎄

Wishing you a blessed Christmas filled with:
⭐ Hope and peace
❤️ Love and joy
🎁 Giving and sharing
😊 Warmth and happiness

May the spirit of Christmas fill your home with love and laughter!

#MerryChristmas #Christmas2026 #PeaceOnEarth
"""
    
    @staticmethod
    def easter() -> str:
        """Easter message template"""
        return """
🐣 *HAPPY EASTER!* 🐣

Wishing you a blessed Easter celebration!

May this season bring:
🌸 Renewed hope
❤️ Abundant love
😊 Joy in abundance
✨ New beginnings

#HappyEaster #EasterCelebration #Blessings
"""
    
    @staticmethod
    def ramadan() -> str:
        """Ramadan message template"""
        return """
🌙 *RAMADAN MUBARAK!* 🌙

Wishing you a blessed month of:
🤲 Reflection and prayer
❤️ Compassion and giving
😊 Joy and peace
✨ Spiritual growth

Ramadan Kareem!

#RamadanKareem #RamadanMubarak #BlessedMonth
"""
    
    @staticmethod
    def thanksgiving() -> str:
        """Thanksgiving message template"""
        return """
🦃 *HAPPY THANKSGIVING!* 🦃

Today we give thanks for:
🌾 Our blessings and abundance
❤️ Our family and friends
😊 Our health and happiness
✨ Every good thing in our lives

Grateful for you!

#HappyThanksgiving #Gratitude #Thankful
"""

# ============================================================
# CONTACT MESSENGER CLASS
# ============================================================

class ContactMessenger:
    """
    Handles sending occasional messages to contacts.
    
    NOTE: This class receives page and context from the main bot.
          It does NOT handle its own login.
    """
    
    def __init__(self):
        self.page = None
        self.context = None
        self.message_history = self._load_history()
        self.templates = MessageTemplates()
    
    # ============================================================
    # DATA MANAGEMENT
    # ============================================================
    
    def _load_history(self) -> dict:
        """Load message history"""
        if MESSAGE_HISTORY_FILE.exists():
            try:
                with open(MESSAGE_HISTORY_FILE, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except:
                return {}
        return {}
    
    def _save_history(self):
        """Save message history"""
        with open(MESSAGE_HISTORY_FILE, 'w', encoding='utf-8') as f:
            json.dump(self.message_history, f, indent=2, ensure_ascii=False)
    
    def _has_sent_recently(self, contact: str, message_type: str, days: int = 30) -> bool:
        """Check if a message was sent to this contact recently"""
        key = f"{contact}_{message_type}"
        if key in self.message_history:
            last_sent = datetime.fromisoformat(self.message_history[key])
            if (datetime.now() - last_sent).days < days:
                return True
        return False
    
    def _mark_sent(self, contact: str, message_type: str):
        """Mark a message as sent to a contact"""
        key = f"{contact}_{message_type}"
        self.message_history[key] = datetime.now().isoformat()
        self._save_history()
    
    # ============================================================
    # SEND MESSAGE TO CONTACT
    # ============================================================
    
    async def send_to_contact(self, contact: dict, message: str) -> bool:
        """
        Send a message to a single contact
        contact: {"name": "Name", "phone": "+254712345678"}
        """
        phone = contact.get("phone", "")
        name = contact.get("name", "Unknown")
        
        print(f"\n📤 Sending to: {name} ({phone})")
        
        if not phone:
            print(f"  ❌ No phone number for {name}")
            return False
        
        try:
            # Search for contact
            search = await self.page.query_selector('div[data-testid="chat-list-search"]')
            if search:
                await search.click()
                await asyncio.sleep(1)
                await self.page.fill('div[data-testid="chat-list-search"] input', phone)
                await asyncio.sleep(2)
            else:
                print(f"  ❌ Search box not found")
                return False
            
            # Click on contact
            contact_elem = await self.page.query_selector(f'div[role="row"]:has-text("{phone}")')
            if not contact_elem:
                # Try by name
                contact_elem = await self.page.query_selector(f'div[role="row"]:has-text("{name}")')
            
            if contact_elem:
                await contact_elem.click()
                await asyncio.sleep(2)
            else:
                print(f"  ❌ Contact not found: {name}")
                return False
            
            # Find compose box
            compose = await self.page.query_selector('div[data-testid="conversation-compose-box"]')
            if not compose:
                print(f"  ❌ Compose box not found")
                return False
            
            await compose.click()
            await asyncio.sleep(0.5)
            await compose.fill("")
            await asyncio.sleep(0.5)
            
            # Type message
            for char in message:
                await compose.type(char, delay=random.randint(50, 120))
                if random.random() < 0.02:
                    await asyncio.sleep(random.uniform(0.2, 0.5))
            
            await asyncio.sleep(1)
            
            # Send
            send = await self.page.query_selector('button[data-testid="compose-btn-send"]')
            if send:
                await send.click()
                await asyncio.sleep(2)
                print(f"  ✅ Message sent to {name}")
                return True
            else:
                print(f"  ❌ Send button not found")
                return False
                
        except Exception as e:
            print(f"  ❌ Error sending to {name}: {e}")
            return False
    
    # ============================================================
    # SEND OCCASIONAL MESSAGES
    # ============================================================
    
    async def send_occasion_message(self, occasion: str, contacts: List[dict] = None, 
                                    custom_message: str = None, limit: int = None):
        """
        Send an occasion message to contacts
        
        Args:
            occasion: 'new_year', 'new_month', 'christmas', 'easter', 'ramadan', 'birthday', 'thanksgiving', 'custom'
            contacts: List of contacts to send to (if None, uses ALL contacts)
            custom_message: Custom message for special occasion
            limit: Max number of contacts to send to (None = all)
        """
        print("\n" + "=" * 60)
        print(f"📨 SENDING {occasion.upper()} MESSAGES")
        print("=" * 60)
        
        # Get message template
        if occasion == "new_year":
            message = self.templates.new_year()
        elif occasion == "new_month":
            message = self.templates.new_month()
        elif occasion == "christmas":
            message = self.templates.christmas()
        elif occasion == "easter":
            message = self.templates.easter()
        elif occasion == "ramadan":
            message = self.templates.ramadan()
        elif occasion == "thanksgiving":
            message = self.templates.thanksgiving()
        elif occasion == "birthday":
            message = self.templates.birthday()
        elif occasion == "custom":
            if not custom_message:
                print("❌ Custom message required for 'custom' occasion")
                return
            message = custom_message
        else:
            print(f"❌ Unknown occasion: {occasion}")
            return
        
        # Get contacts
        if contacts is None:
            # Get all contacts from all categories
            all_contacts = []
            for category, contact_list in INDIVIDUAL_CONTACTS.items():
                all_contacts.extend(contact_list)
            contacts = all_contacts
        
        # Filter contacts who haven't received this message recently
        filtered_contacts = []
        for contact in contacts:
            phone = contact.get("phone", "")
            if not phone:
                continue
            if self._has_sent_recently(phone, occasion, days=30):
                continue
            filtered_contacts.append(contact)
        
        # Limit contacts
        if limit and len(filtered_contacts) > limit:
            filtered_contacts = random.sample(filtered_contacts, limit)
        
        total = len(filtered_contacts)
        print(f"📋 Contacts to send: {total}")
        
        if total == 0:
            print("📭 No contacts to send to (all already received recently)")
            return
        
        successful = 0
        failed = 0
        
        for i, contact in enumerate(filtered_contacts, 1):
            print(f"\n[{i}/{total}] ", end="")
            
            success = await self.send_to_contact(contact, message)
            
            if success:
                successful += 1
                self._mark_sent(contact.get("phone", ""), occasion)
            else:
                failed += 1
            
            # Random delay between messages
            if i < total:
                delay = random.uniform(5, 15)
                print(f"⏳ Waiting {delay:.1f}s before next...")
                await asyncio.sleep(delay)
        
        # Summary
        print("\n" + "=" * 60)
        print("📊 SEND SUMMARY")
        print("=" * 60)
        print(f"✅ Successful: {successful}")
        print(f"❌ Failed: {failed}")
        print(f"📱 Total attempted: {total}")
        print("=" * 60)
    
    # ============================================================
    # SEND TO SPECIFIC CATEGORY
    # ============================================================
    
    async def send_to_category(self, category: str, occasion: str, custom_message: str = None):
        """Send an occasion message to a specific contact category"""
        contacts = get_contacts_by_category(category)
        if not contacts:
            print(f"❌ Category '{category}' not found")
            return
        
        print(f"📋 Found {len(contacts)} contacts in '{category}'")
        await self.send_occasion_message(occasion, contacts, custom_message)
    
    # ============================================================
    # SEND NEW YEAR MESSAGES (Special shortcut)
    # ============================================================
    
    async def send_new_year(self, year: int = None):
        """Shortcut to send New Year messages"""
        await self.send_occasion_message("new_year", None, None)
    
    async def send_new_month(self):
        """Shortcut to send New Month messages"""
        await self.send_occasion_message("new_month", None, None)
    
    async def send_holiday(self, holiday_name: str):
        """Shortcut to send Holiday messages"""
        await self.send_occasion_message(holiday_name.lower(), None, None)

# ============================================================
# REMOVED: start(), launch_browser(), _wait_for_login(), 
#          shutdown(), run(), main()
# These are now handled by whatsapp_bot.py and LoginManager
# ============================================================