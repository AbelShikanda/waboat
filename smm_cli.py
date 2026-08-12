"""
SMM CLI Tool
============
Command line interface for managing products and groups
"""

import sys
from group_poster import ProductLoader
from target_groups import TARGET_GROUPS

class SMM_CLI:
    def __init__(self):
        self.product_loader = ProductLoader()
    
    def show_help(self):
        print("""
📢 SMM CLI TOOL
================
Commands:
  list              - List pending products
  stats             - Show product statistics
  reset             - Reset all products to pending
  groups            - List groups
  help              - Show this help

Examples:
  python whatsapp_bot.py cli list
  python whatsapp_bot.py cli stats
  python whatsapp_bot.py cli reset
  python whatsapp_bot.py cli groups
""")
    
    def list_pending(self):
        """List all pending products"""
        products = self.product_loader.load_all_products(status="pending")
        if not products:
            print("\n📭 No pending products")
            return
        
        print(f"\n📦 PENDING PRODUCTS ({len(products)})")
        print("=" * 60)
        for i, p in enumerate(products[:20], 1):
            source = p.get("source", "unknown")
            name = p.get("product_name") or p.get("id", "Unknown")
            print(f"  {i:2}. [{source:10}] {name[:40]}")
        if len(products) > 20:
            print(f"  ... and {len(products) - 20} more")
        print("=" * 60)
    
    def show_stats(self):
        """Show product statistics by status and source"""
        products = self.product_loader.load_all_products(status=None)
        
        print("\n📊 PRODUCT STATISTICS")
        print("=" * 60)
        
        statuses = {}
        sources = {}
        
        for p in products:
            s = p.get("status", "unknown")
            statuses[s] = statuses.get(s, 0) + 1
            
            src = p.get("source", "unknown")
            sources[src] = sources.get(src, 0) + 1
        
        print("\n📋 By Status:")
        for s, count in statuses.items():
            print(f"  - {s}: {count}")
        
        print("\n📋 By Source:")
        for src, count in sources.items():
            print(f"  - {src}: {count}")
        
        total = len(products)
        print(f"\n📦 Total Products: {total}")
        print("=" * 60)
    
    def reset_products(self):
        """Reset all products to pending"""
        loader = ProductLoader()
        loader.reset_all_products()
    
    def list_groups(self):
        """List all target groups"""
        print(f"\n📢 GROUPS ({len(TARGET_GROUPS)} total)")
        print("=" * 50)
        for i, group in enumerate(TARGET_GROUPS, 1):
            print(f"{i:3}. {group}")
        print("=" * 50)

def main():
    cli = SMM_CLI()
    
    if len(sys.argv) < 2:
        cli.show_help()
        return
    
    command = sys.argv[1].lower()
    
    if command == "help":
        cli.show_help()
    elif command == "list":
        cli.list_pending()
    elif command == "stats":
        cli.show_stats()
    elif command == "reset":
        cli.reset_products()
    elif command == "groups":
        cli.list_groups()
    else:
        print(f"❌ Unknown command: {command}")
        cli.show_help()

if __name__ == "__main__":
    main()