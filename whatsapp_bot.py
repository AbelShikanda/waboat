"""
WhatsApp Bot - Main Entry Point
===============================
Imports LoginManager and GroupPoster
"""

import asyncio
import sys
from login_manager import LoginManager
from group_poster import GroupPoster

async def main():
    # Check if CLI mode
    if len(sys.argv) > 1 and sys.argv[1] == "cli":
        # Import and run CLI
        from smm_cli import main as cli_main
        sys.argv.pop(1)
        cli_main()
        return
    
    # Normal bot mode
    login = LoginManager()
    poster = None
    
    try:
        # Login
        if await login.login():
            # Create poster with page and context
            poster = GroupPoster(login.page, login.context)
            
            # Run posting
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

if __name__ == "__main__":
    asyncio.run(main())