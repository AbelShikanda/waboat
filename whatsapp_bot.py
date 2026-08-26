"""
WhatsApp Bot - Main Entry Point
===============================
Imports LoginManager and GroupPoster (FIXED VERSION - Enter Key Only)
Supports:
- Normal product posting (with Enter key, no send button search)
- Group management (manage-groups)
- Group link marketing (link-market)
- Contact messaging (send-messages)
- CLI commands (cli)
- ANALYTICS commands (analytics, trending, groups, stats)
"""

import asyncio
import sys
from login_manager import LoginManager
from group_poster import GroupPoster
from group_manager import GroupManager
from group_link_marketer import GroupLinkMarketer
from contact_messenger import ContactMessenger

# ============================================================
# IMPORT ANALYTICS MODULE
# ============================================================

from analytics_module import (
    DatabaseManager,
    AnalyticsDisplay,
    AnalyticsExport,
    run_analytics_command,
    get_analytics_help
)

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
  python whatsapp_bot.py analytics            - Show analytics dashboard
  python whatsapp_bot.py analytics --html     - Generate HTML report
  python whatsapp_bot.py analytics --export   - Export data to CSV
  python whatsapp_bot.py analytics --group "Name" - Group analytics
  python whatsapp_bot.py trending             - Show trending topics
  python whatsapp_bot.py groups               - List all groups with stats
  python whatsapp_bot.py stats                - Show database statistics
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
📊 ANALYTICS COMMANDS
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  analytics                                   - Show full analytics dashboard
  analytics --html                            - Generate HTML report (opens in browser)
  analytics --export                          - Export all data to CSV
  analytics --group "Group Name"              - Show analytics for specific group
  analytics --list-groups                     - List all groups in database
  trending                                    - Show trending topics (last 7 days)
  trending --days 14                          - Show trending (last 14 days)
  trending --limit 20                         - Show top 20 trending topics
  groups                                      - List all groups with message counts
  groups --limit 10                           - Show top 10 groups
  stats                                       - Show database statistics

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
🔧 CLI COMMANDS
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  python whatsapp_bot.py cli list             - List pending products
  python whatsapp_bot.py cli queue            - Show queue status
  python whatsapp_bot.py cli add-test         - Add test product
  python whatsapp_bot.py cli groups           - List groups
  python whatsapp_bot.py cli products         - Show products
  python whatsapp_bot.py cli stats            - Show statistics
  python whatsapp_bot.py cli reset            - Reset all products to pending

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
📋 AVAILABLE MESSAGE CATEGORIES
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  customers  → Customer contacts
  business   → Business contacts  
  friends    → Personal friends
  (no category) → All contacts

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
💡 EXAMPLES
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  python whatsapp_bot.py post 3               # Post 3 products
  python whatsapp_bot.py manage-groups        # Collect all group links
  python whatsapp_bot.py link-market          # Market group links
  python whatsapp_bot.py send-messages new_year  # Send New Year messages
  python whatsapp_bot.py analytics --html     # Generate HTML report
  python whatsapp_bot.py trending             # Show trending topics
  python whatsapp_bot.py groups --limit 10    # Show top 10 groups
  python whatsapp_bot.py stats                # Show database stats
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
            # ✅ FIXED: Pass login_manager to GroupManager
            manager = GroupManager(login_manager=login)
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
            # ✅ FIXED: Pass login_manager to GroupLinkMarketer
            marketer = GroupLinkMarketer(login_manager=login)
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
            # ✅ FIXED: Pass login_manager to ContactMessenger
            messenger = ContactMessenger(login_manager=login)
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
# ANALYTICS COMMAND HANDLER
# ============================================================

def handle_analytics_command(args):
    """Route analytics commands to analytics_module"""
    run_analytics_command(args)

# ============================================================
# PRODUCT POSTING (Normal Mode) - USES FIXED GROUP POSTER
# ============================================================

async def run_product_poster():
    """Run normal product posting mode using FIXED GroupPoster (Enter key only)"""
    print("=" * 60)
    print("📢 PRODUCT POSTER (FIXED VERSION - Enter Key Only)")
    print("=" * 60)
    
    login = LoginManager()
    poster = None
    
    try:
        if await login.login():
            # ✅ FIXED: Pass login_manager to GroupPoster
            poster = GroupPoster(login.page, login.context, login_manager=login)
            
            print("\n" + "=" * 60)
            print("📢 Ready to post random products!")
            print("=" * 60)
            print("📝 Messages will preserve line breaks")
            print("⏳ Link previews will load before sending")
            print("⌨️  Using Enter key to send (NO send button search)")
            print("📊 Data collection enabled (stays in groups, collects chat history)")
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
            poster.db.close()
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
        
        # ============================================================
        # ANALYTICS COMMANDS
        # ============================================================
        elif command == "analytics":
            # Parse analytics arguments
            import argparse
            args = argparse.Namespace()
            args.command = "analytics"
            args.html = "--html" in sys.argv or "-H" in sys.argv
            args.export = "--export" in sys.argv or "-e" in sys.argv
            args.group = None
            args.list_groups = "--list-groups" in sys.argv
            
            # Parse --group argument
            for i, arg in enumerate(sys.argv):
                if arg == "--group" and i + 1 < len(sys.argv):
                    args.group = sys.argv[i + 1]
                    break
            
            args.days = 7
            args.limit = 10
            run_analytics_command(args)
            return
        
        elif command == "trending":
            import argparse
            args = argparse.Namespace()
            args.command = "trending"
            args.days = 7
            args.limit = 15
            
            # Parse --days and --limit
            for i, arg in enumerate(sys.argv):
                if arg == "--days" and i + 1 < len(sys.argv):
                    try:
                        args.days = int(sys.argv[i + 1])
                    except:
                        pass
                if arg == "--limit" and i + 1 < len(sys.argv):
                    try:
                        args.limit = int(sys.argv[i + 1])
                    except:
                        pass
            
            run_analytics_command(args)
            return
        
        elif command == "groups":
            import argparse
            args = argparse.Namespace()
            args.command = "groups"
            args.limit = None
            
            # Parse --limit
            for i, arg in enumerate(sys.argv):
                if arg == "--limit" and i + 1 < len(sys.argv):
                    try:
                        args.limit = int(sys.argv[i + 1])
                    except:
                        pass
            
            run_analytics_command(args)
            return
        
        elif command == "stats":
            import argparse
            args = argparse.Namespace()
            args.command = "stats"
            run_analytics_command(args)
            return
        
        elif command == "help" or command == "--help" or command == "-h":
            show_help()
            return
        
        else:
            print(f"❌ Unknown command: {command}")
            print("   Try: python whatsapp_bot.py help")
            return
    
    # ============================================================
    # NORMAL MODE: Product Posting using FIXED GroupPoster
    # ============================================================
    await run_product_poster()

if __name__ == "__main__":
    asyncio.run(main())