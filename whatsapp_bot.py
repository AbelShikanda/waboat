"""
WhatsApp Bot - Main Entry Point
===============================
Imports LoginManager and GroupPoster
Supports:
- Normal product posting
- Group management (manage-groups)
- Group link marketing (link-market)
- Contact messaging (send-messages)
- CLI commands (cli)
"""

import asyncio
import sys
from login_manager import LoginManager
from group_poster import GroupPoster
from group_manager import GroupManager
from group_link_marketer import GroupLinkMarketer
from contact_messenger import ContactMessenger

# ============================================================
# HELP
# ============================================================

def show_help():
    print("""
📱 WHATSAPP BOT - Commands
===========================
  python whatsapp_bot.py                      - Run normal product posting
  python whatsapp_bot.py manage-groups        - Collect group links & update descriptions
  python whatsapp_bot.py link-market          - Market group links to other groups
  python whatsapp_bot.py send-messages        - Send occasional messages to contacts
  python whatsapp_bot.py cli [cmd]            - Run CLI commands
  python whatsapp_bot.py help                 - Show this help

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
📨 SEND-MESSAGES OPTIONS
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  send-messages new_year                      - Send New Year wishes
  send-messages new_month                     - Send New Month greetings
  send-messages christmas                     - Send Christmas wishes
  send-messages easter                        - Send Easter wishes
  send-messages ramadan                       - Send Ramadan wishes
  send-messages birthday                      - Send Birthday wishes
  send-messages thanksgiving                  - Send Thanksgiving wishes
  send-messages custom "Your message"         - Send custom message
  
  With category filter:
  send-messages [occasion] [category]         - Send to specific category
  Categories: customers, business, friends
  
  Examples:
  send-messages new_year customers            - New Year to customers only
  send-messages christmas friends             - Christmas to friends only
  send-messages birthday business             - Birthday wishes to business contacts

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
CLI Commands:
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  python whatsapp_bot.py cli list             - List pending products
  python whatsapp_bot.py cli queue            - Show queue status
  python whatsapp_bot.py cli add-test         - Add test product
  python whatsapp_bot.py cli groups           - List groups
  python whatsapp_bot.py cli products         - Show products
  python whatsapp_bot.py cli stats            - Show statistics
  python whatsapp_bot.py cli reset            - Reset all products to pending

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Available Message Categories:
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  customers  → Customer contacts
  business   → Business contacts  
  friends    → Personal friends
  (no category) → All contacts

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Examples:
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  python whatsapp_bot.py manage-groups        # Collect all group links
  python whatsapp_bot.py link-market          # Market group links
  python whatsapp_bot.py send-messages new_year  # Send New Year messages
  python whatsapp_bot.py send-messages christmas customers  # Christmas to customers
  python whatsapp_bot.py send-messages birthday friends  # Birthday to friends
  python whatsapp_bot.py cli list             # Show pending products
""")

# ============================================================
# COMMAND HANDLERS
# ============================================================

async def handle_manage_groups():
    """Run group manager to collect links and update descriptions"""
    print("=" * 60)
    print("🔧 GROUP MANAGER")
    print("=" * 60)
    
    login = LoginManager()
    try:
        if await login.login():
            manager = GroupManager()
            manager.page = login.page
            manager.context = login.context
            await manager.manage_all_groups()
        else:
            print("❌ Login failed")
    except KeyboardInterrupt:
        print("\n⏹️ Stopped by user")
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
    finally:
        await login.shutdown()

async def handle_link_market():
    """Run link marketer to post group links to other groups"""
    print("=" * 60)
    print("🔗 GROUP LINK MARKETER")
    print("=" * 60)
    
    login = LoginManager()
    try:
        if await login.login():
            marketer = GroupLinkMarketer()
            marketer.page = login.page
            marketer.context = login.context
            await marketer.market_group_links("all")
        else:
            print("❌ Login failed")
    except KeyboardInterrupt:
        print("\n⏹️ Stopped by user")
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
    finally:
        await login.shutdown()

async def handle_send_messages(occasion: str = None, category: str = None, custom_message: str = None):
    """
    Send occasional messages to contacts
    
    Args:
        occasion: 'new_year', 'new_month', 'christmas', 'easter', 'ramadan', 
                  'birthday', 'thanksgiving', 'custom'
        category: Optional category to filter contacts ('customers', 'business', 'friends')
        custom_message: Custom message for 'custom' occasion
    """
    print("=" * 60)
    print("📱 CONTACT MESSENGER")
    print("=" * 60)
    
    # If no occasion specified, show options
    if occasion is None:
        print("""
📨 Available Occasions:
  new_year      - New Year wishes
  new_month     - New Month greetings
  christmas     - Christmas wishes
  easter        - Easter wishes
  ramadan       - Ramadan wishes
  birthday      - Birthday wishes
  thanksgiving  - Thanksgiving wishes
  custom        - Custom message

📋 Available Categories:
  customers     - Customer contacts
  business      - Business contacts
  friends       - Personal friends

💡 Usage Examples:
  python whatsapp_bot.py send-messages new_year
  python whatsapp_bot.py send-messages christmas customers
  python whatsapp_bot.py send-messages birthday friends
  python whatsapp_bot.py send-messages custom "Your custom message here"
""")
        return
    
    login = LoginManager()
    try:
        if await login.login():
            messenger = ContactMessenger()
            messenger.page = login.page
            messenger.context = login.context
            
            # Handle custom message
            if occasion == "custom" and custom_message:
                print(f"\n📨 Sending custom message...")
                if category:
                    print(f"📋 Target category: {category}")
                    await messenger.send_to_category(category, "custom", custom_message)
                else:
                    await messenger.send_occasion_message("custom", custom_message=custom_message)
            else:
                print(f"\n📨 Sending {occasion.upper()} messages...")
                
                if category:
                    print(f"📋 Target category: {category}")
                    await messenger.send_to_category(category, occasion)
                else:
                    await messenger.send_occasion_message(occasion)
        else:
            print("❌ Login failed")
    except KeyboardInterrupt:
        print("\n⏹️ Stopped by user")
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
    finally:
        await login.shutdown()

# ============================================================
# PRODUCT POSTING (Normal Mode)
# ============================================================

async def run_product_poster():
    """Run normal product posting mode"""
    print("=" * 60)
    print("📢 PRODUCT POSTER")
    print("=" * 60)
    
    login = LoginManager()
    poster = None
    
    try:
        if await login.login():
            poster = GroupPoster(login.page, login.context)
            
            print("\n" + "=" * 60)
            print("📢 Ready to post random products!")
            print("=" * 60)
            print("📝 Messages will preserve line breaks")
            print("⏳ Link previews will load before sending")
            print("=" * 60)
            
            await poster.post_random_products(count=None)
            
            print("\n✅ All posting complete!")
            print("⏳ Browser will stay open for 30 seconds...")
            await asyncio.sleep(30)
        
    except KeyboardInterrupt:
        print("\n⏹️ Bot stopped by user")
    except Exception as e:
        print(f"❌ Fatal error: {e}")
        import traceback
        traceback.print_exc()
    finally:
        if poster:
            await poster.product_loader.load_all_products(status=None)
        await login.shutdown()

# ============================================================
# MAIN ENTRY POINT
# ============================================================

async def main():
    # ============================================================
    # CLI MODE: Run commands via cli subcommand
    # ============================================================
    if len(sys.argv) > 1 and sys.argv[1] == "cli":
        from smm_cli import main as cli_main
        sys.argv.pop(1)
        cli_main()
        return
    
    # ============================================================
    # DIRECT COMMANDS (without "cli" prefix)
    # ============================================================
    if len(sys.argv) > 1:
        command = sys.argv[1].lower()
        
        if command == "manage-groups":
            await handle_manage_groups()
            return
        
        elif command == "link-market":
            await handle_link_market()
            return
        
        elif command == "send-messages":
            # Parse arguments
            occasion = sys.argv[2] if len(sys.argv) > 2 else None
            category_or_message = sys.argv[3] if len(sys.argv) > 3 else None
            
            # Handle custom message with spaces
            if occasion == "custom" and len(sys.argv) > 3:
                # Join all remaining arguments as custom message
                custom_message = " ".join(sys.argv[3:])
                await handle_send_messages("custom", None, custom_message)
            elif category_or_message and category_or_message in ["customers", "business", "friends"]:
                await handle_send_messages(occasion, category_or_message)
            elif occasion == "custom" and category_or_message:
                await handle_send_messages("custom", None, category_or_message)
            else:
                await handle_send_messages(occasion)
            return
        
        elif command == "help" or command == "--help" or command == "-h":
            show_help()
            return
        
        else:
            print(f"❌ Unknown command: {command}")
            print("   Try: python whatsapp_bot.py help")
            return
    
    # ============================================================
    # NORMAL MODE: Product Posting
    # ============================================================
    await run_product_poster()

if __name__ == "__main__":
    asyncio.run(main())