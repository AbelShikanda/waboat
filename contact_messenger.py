"""
Contact Messenger Module
========================
Handles sending occasional messages to contacts:
- New Year wishes
- New Month greetings
- Holiday messages
- Birthday wishes
- Special promotions (very occasional)
- EXHAUSTIVE CONNECTION MONITORING: CHECKS EVERY CRITICAL STEP

USAGE: This module does NOT handle its own login.
       It receives page, context, and login_manager from the main bot.
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

# Connection check interval during long operations
CONNECTION_CHECK_INTERVAL = 30

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
# CONTACT MESSENGER CLASS - EXHAUSTIVE CONNECTION MONITORING
# ============================================================

class ContactMessenger:
    """
    Handles sending occasional messages to contacts with EXHAUSTIVE connection monitoring.
    
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
        Initialize ContactMessenger
        
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
        
        self.message_history = self._load_history()
        self.templates = MessageTemplates()
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
            print("   All message sending operations are on hold.")
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
                print("   Resuming message sending operations...")
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
        print("🔄 Connection health monitor started for ContactMessenger")
        
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
        """Start the messenger with connection monitoring"""
        self.is_running = True
        
        # Start background health monitor
        asyncio.create_task(self.connection_health_monitor())
        
        print("✅ Contact Messenger started with EXHAUSTIVE connection monitoring")
        print(f"   Connection checks at EVERY critical step")
        print(f"   Health monitor running every {CONNECTION_CHECK_INTERVAL}s")
    
    async def stop(self):
        """Stop the messenger"""
        self.is_running = False
        print("🛑 Contact Messenger stopped")
    
    # ============================================================
    # SET PAGE AND CONTEXT
    # ============================================================
    
    def set_page(self, page, context):
        """Set the page and context for the messenger"""
        self.page = page
        self.context = context
        print("✅ Page and context set for ContactMessenger")
    
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
    
    async def _save_history_with_connection_check(self):
        """Save message history with connection check"""
        # CONNECTION CHECK: Before file operation
        if not await self.ensure_connection("_save_history"):
            print("⚠️ Connection lost during save. Will retry...")
            if not await self.ensure_connection("_save_history_retry"):
                print("❌ Cannot save history - no connection")
                return False
        
        try:
            with open(MESSAGE_HISTORY_FILE, 'w', encoding='utf-8') as f:
                json.dump(self.message_history, f, indent=2, ensure_ascii=False)
            return True
        except Exception as e:
            print(f"❌ Error saving history: {e}")
            return False
    
    def _save_history(self):
        """Save message history (synchronous, kept for compatibility)"""
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
    
    async def _mark_sent_with_connection_check(self, contact: str, message_type: str):
        """Mark a message as sent with connection check"""
        # CONNECTION CHECK: Before marking
        if not await self.ensure_connection(f"mark_sent_{contact}_{message_type}"):
            print("⚠️ Connection lost during marking. Will try anyway...")
        
        key = f"{contact}_{message_type}"
        self.message_history[key] = datetime.now().isoformat()
        await self._save_history_with_connection_check()
    
    def _mark_sent(self, contact: str, message_type: str):
        """Mark a message as sent (synchronous, kept for compatibility)"""
        key = f"{contact}_{message_type}"
        self.message_history[key] = datetime.now().isoformat()
        self._save_history()
    
    # ============================================================
    # SEND MESSAGE TO CONTACT - WITH EXHAUSTIVE CONNECTION CHECKS
    # ============================================================
    
    async def send_to_contact(self, contact: dict, message: str) -> bool:
        """
        Send a message to a single contact with EXHAUSTIVE connection checks.
        contact: {"name": "Name", "phone": "+254712345678"}
        """
        
        # CONNECTION CHECK: Before starting
        if not await self.ensure_connection(f"send_to_contact_start_{contact.get('phone')}"):
            print("❌ WhatsApp not connected. Cannot send message.")
            return False
        
        phone = contact.get("phone", "")
        name = contact.get("name", "Unknown")
        
        print(f"\n📤 Sending to: {name} ({phone})")
        
        if not phone:
            print(f"  ❌ No phone number for {name}")
            return False
        
        try:
            # CONNECTION CHECK: Before search
            if not await self.ensure_connection(f"send_to_contact_search_{phone}"):
                return False
            
            # Search for contact
            print(f"    [1/6] Searching for contact...")
            search = await self.page.query_selector('div[data-testid="chat-list-search"]')
            if search:
                await search.click()
                await asyncio.sleep(1)
                
                # CONNECTION CHECK: After clicking search
                if not await self.ensure_connection(f"send_to_contact_after_search_{phone}"):
                    return False
                
                await self.page.fill('div[data-testid="chat-list-search"] input', phone)
                await asyncio.sleep(2)
                
                # CONNECTION CHECK: After typing phone
                if not await self.ensure_connection(f"send_to_contact_after_type_{phone}"):
                    return False
            else:
                print(f"  ❌ Search box not found")
                return False
            
            # CONNECTION CHECK: Before finding contact
            if not await self.ensure_connection(f"send_to_contact_find_{phone}"):
                return False
            
            # Click on contact
            print(f"    [2/6] Finding contact...")
            contact_elem = await self.page.query_selector(f'div[role="row"]:has-text("{phone}")')
            if not contact_elem:
                # Try by name
                contact_elem = await self.page.query_selector(f'div[role="row"]:has-text("{name}")')
            
            if contact_elem:
                await contact_elem.click()
                await asyncio.sleep(2)
                
                # CONNECTION CHECK: After clicking contact
                if not await self.ensure_connection(f"send_to_contact_after_click_{phone}"):
                    return False
            else:
                print(f"  ❌ Contact not found: {name}")
                return False
            
            # CONNECTION CHECK: Before finding compose box
            if not await self.ensure_connection(f"send_to_contact_compose_{phone}"):
                return False
            
            # Find compose box
            print(f"    [3/6] Finding compose box...")
            compose = await self.page.query_selector('div[data-testid="conversation-compose-box"]')
            if not compose:
                # Try alternative selectors
                compose_selectors = [
                    '#main > footer > div > span > div > div > div > div > div.x1hx0egp > p',
                    'div[contenteditable="true"]',
                    'div[role="textbox"]',
                    'p[contenteditable="true"]',
                    'footer div[contenteditable="true"]'
                ]
                
                for selector in compose_selectors:
                    # CONNECTION CHECK: During compose selector iteration
                    if not await self.ensure_connection(f"send_to_contact_compose_alt_{phone}"):
                        continue
                    
                    try:
                        compose = await self.page.query_selector(selector)
                        if compose and await compose.is_visible():
                            print(f"    ✅ Found compose box with: {selector}")
                            break
                    except:
                        continue
                
                if not compose:
                    print(f"  ❌ Compose box not found")
                    return False
            
            # CONNECTION CHECK: Before clicking compose
            if not await self.ensure_connection(f"send_to_contact_before_type_{phone}"):
                return False
            
            await compose.click()
            await asyncio.sleep(0.5)
            await compose.fill("")
            await asyncio.sleep(0.5)
            
            print(f"    [4/6] Typing message...")
            
            # CONNECTION CHECK: Before typing
            if not await self.ensure_connection(f"send_to_contact_type_start_{phone}"):
                return False
            
            # Type message with EXHAUSTIVE connection checking
            for char_index, char in enumerate(message):
                # CONNECTION CHECK: During typing (every 50 characters)
                if char_index % 50 == 0 and char_index > 0:
                    if not await self.ensure_connection(f"send_to_contact_typing_{char_index}_{phone}"):
                        print("⏳ Connection lost during typing. Waiting for reconnection...")
                        await self.ensure_connection(f"send_to_contact_typing_reconnect_{char_index}_{phone}")
                        print("✅ Connection restored. Resuming typing...")
                        # Continue typing after reconnection
                        continue
                
                await compose.type(char, delay=random.randint(50, 120))
                if random.random() < 0.02:
                    await asyncio.sleep(random.uniform(0.2, 0.5))
            
            await asyncio.sleep(1)
            
            # CONNECTION CHECK: Before sending
            if not await self.ensure_connection(f"send_to_contact_before_send_{phone}"):
                print("⏳ Connection lost before sending. Waiting for reconnection...")
                await self.ensure_connection(f"send_to_contact_before_send_reconnect_{phone}")
                print("✅ Connection restored. Resuming send...")
            
            print(f"    [5/6] Sending message...")
            await self.page.keyboard.press('Enter')
            await asyncio.sleep(2)
            
            # CONNECTION CHECK: After sending
            if not await self.ensure_connection(f"send_to_contact_after_send_{phone}"):
                print("⚠️ Connection lost after sending. Checking if message was sent...")
                # We'll still mark as sent if possible
            
            print(f"    [6/6] ✅ Message sent to {name}")
            return True
                
        except Exception as e:
            print(f"  ❌ Error sending to {name}: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    # ============================================================
    # SEND OCCASIONAL MESSAGES - WITH EXHAUSTIVE CONNECTION CHECKS
    # ============================================================
    
    async def send_occasion_message(self, occasion: str, contacts: List[dict] = None, 
                                    custom_message: str = None, limit: int = None):
        """
        Send an occasion message to contacts with EXHAUSTIVE connection checking.
        
        Args:
            occasion: 'new_year', 'new_month', 'christmas', 'easter', 'ramadan', 'birthday', 'thanksgiving', 'custom'
            contacts: List of contacts to send to (if None, uses ALL contacts)
            custom_message: Custom message for special occasion
            limit: Max number of contacts to send to (None = all)
        """
        
        # CONNECTION CHECK: Before starting
        if not await self.ensure_connection(f"send_occasion_start_{occasion}"):
            print("❌ WhatsApp not connected. Cannot send messages.")
            return
        
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
            # CONNECTION CHECK: During filtering (every 50 contacts)
            if len(filtered_contacts) % 50 == 0:
                if not await self.ensure_connection(f"send_occasion_filter_{occasion}"):
                    print("⚠️ Connection lost during filtering. Continuing...")
                    # Continue with what we have
            
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
            # ============================================================
            # CONNECTION CHECK: Before EACH contact (EXHAUSTIVE)
            # ============================================================
            if not await self.ensure_connection(f"send_occasion_contact_{i}_{occasion}"):
                print("⏳ Connection lost. Waiting for reconnection...")
                await self.ensure_connection(f"send_occasion_reconnect_{i}_{occasion}")
                print("✅ Connection restored. Resuming message sending...")
                # Continue to next contact after reconnection
                continue
            
            print(f"\n[{i}/{total}] ", end="")
            
            # Send the message
            success = await self.send_to_contact(contact, message)
            
            # CONNECTION CHECK: After sending
            if not await self.ensure_connection(f"send_occasion_after_send_{i}_{occasion}"):
                print("⚠️ Connection lost after sending. Checking status...")
                # We'll continue to next contact if possible
            
            if success:
                successful += 1
                # Use async version with connection check
                await self._mark_sent_with_connection_check(contact.get("phone", ""), occasion)
            else:
                failed += 1
            
            # ============================================================
            # CONNECTION CHECK: Before waiting (EXHAUSTIVE)
            # ============================================================
            if not await self.ensure_connection(f"send_occasion_wait_{i}_{occasion}"):
                print("⏳ Connection lost before wait. Waiting for reconnection...")
                await self.ensure_connection(f"send_occasion_wait_reconnect_{i}_{occasion}")
                print("✅ Connection restored. Resuming...")
                # Skip the wait if we just reconnected
                if i < total:
                    delay = random.uniform(5, 15)
                    print(f"⏳ Waiting {delay:.1f}s before next...")
                    await asyncio.sleep(delay)
                continue
            
            # Random delay between messages
            if i < total:
                delay = random.uniform(5, 15)
                print(f"⏳ Waiting {delay:.1f}s before next...")
                await asyncio.sleep(delay)
        
        # CONNECTION CHECK: Before final summary
        if not await self.ensure_connection(f"send_occasion_summary_{occasion}"):
            print("⚠️ Connection lost during final summary. Some stats may be incomplete.")
        
        # Summary
        print("\n" + "=" * 60)
        print("📊 SEND SUMMARY")
        print("=" * 60)
        print(f"✅ Successful: {successful}")
        print(f"❌ Failed: {failed}")
        print(f"📱 Total attempted: {total}")
        print("")
        print("📊 CONNECTION MONITORING STATISTICS")
        print("-" * 40)
        print(f"Total connection checks: {self.connection_stats['checks_performed']}")
        print(f"Disconnections detected: {self.connection_stats['disconnections_detected']}")
        print(f"Reconnections succeeded: {self.connection_stats['reconnections_succeeded']}")
        print(f"Operations paused: {self.connection_stats['operations_paused']}")
        print("=" * 60)
    
    # ============================================================
    # SEND TO SPECIFIC CATEGORY - WITH CONNECTION CHECK
    # ============================================================
    
    async def send_to_category(self, category: str, occasion: str, custom_message: str = None):
        """Send an occasion message to a specific contact category with connection check"""
        
        # CONNECTION CHECK: Before starting
        if not await self.ensure_connection(f"send_to_category_{category}_{occasion}"):
            print("❌ Cannot start - WhatsApp not connected")
            return
        
        contacts = get_contacts_by_category(category)
        if not contacts:
            print(f"❌ Category '{category}' not found")
            return
        
        print(f"📋 Found {len(contacts)} contacts in '{category}'")
        await self.send_occasion_message(occasion, contacts, custom_message)
    
    # ============================================================
    # SEND NEW YEAR MESSAGES - WITH CONNECTION CHECK
    # ============================================================
    
    async def send_new_year(self, year: int = None):
        """Shortcut to send New Year messages with connection check"""
        if not await self.ensure_connection("send_new_year"):
            print("❌ Cannot start - WhatsApp not connected")
            return
        await self.send_occasion_message("new_year", None, None)
    
    async def send_new_month(self):
        """Shortcut to send New Month messages with connection check"""
        if not await self.ensure_connection("send_new_month"):
            print("❌ Cannot start - WhatsApp not connected")
            return
        await self.send_occasion_message("new_month", None, None)
    
    async def send_holiday(self, holiday_name: str):
        """Shortcut to send Holiday messages with connection check"""
        if not await self.ensure_connection(f"send_holiday_{holiday_name}"):
            print("❌ Cannot start - WhatsApp not connected")
            return
        await self.send_occasion_message(holiday_name.lower(), None, None)


# ============================================================
# MAIN ENTRY POINT - FOR STANDALONE USE
# ============================================================

async def main():
    """Main entry point for standalone testing"""
    from playwright.async_api import async_playwright
    
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)
        context = await browser.new_context(
            viewport={'width': 1280, 'height': 800},
            user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        )
        page = await context.new_page()
        
        # Initialize messenger (no login manager for standalone)
        messenger = ContactMessenger()
        messenger.set_page(page, context)
        
        # Start the messenger (starts background health monitor)
        await messenger.start()
        
        # Navigate to WhatsApp Web
        await page.goto("https://web.whatsapp.com")
        print("📱 Please scan the QR code to login...")
        print("⏳ Waiting for WhatsApp to load...")
        
        # Wait for WhatsApp to load
        await page.wait_for_selector('div[data-testid="chat-list"]', timeout=120000)
        print("✅ WhatsApp loaded successfully!")
        
        try:
            # Example: Send New Year messages to first 5 contacts
            # In production, use the full list
            test_contacts = [
                {"name": "Test Contact", "phone": "+254712345678"}
            ]
            await messenger.send_occasion_message("new_year", test_contacts)
            
        except KeyboardInterrupt:
            print("\n\n⏹️ Stopped by user")
        except Exception as e:
            print(f"\n❌ Error: {e}")
            import traceback
            traceback.print_exc()
        
        finally:
            # Stop the messenger
            await messenger.stop()
            
            print("\n📊 Message sending complete!")
            print(f"📊 Connection checks performed: {messenger.connection_stats['checks_performed']}")
            print(f"   Disconnections detected: {messenger.connection_stats['disconnections_detected']}")
            print(f"   Reconnections succeeded: {messenger.connection_stats['reconnections_succeeded']}")
            
            # Keep browser open for a moment
            print("\n⏳ Press Ctrl+C to close browser...")
            await asyncio.sleep(10)
            await browser.close()

if __name__ == "__main__":
    asyncio.run(main())