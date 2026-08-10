"""
Target Groups Configuration
===========================
This file contains all the groups that the bot should post to.
Update this list with your actual WhatsApp group names.
"""

# ============================================================
# TARGET GROUPS - Update with your actual groups
# ============================================================

TARGET_GROUPS = [
    "PRINT SHOP KENYA",
    "CARS AND TRUCKS",
    "AUTOMOBILE MARKET",
    "KENYA AUTO",
    "ELDORET BUSINESS",
    "KAKAMEGA ONLINE MARKET",
    "KLADIKA KENYA",
    "BUSINESS BLOCK",
    "KENYA MUMS MARKETING PLACE",
    "Kenyan Online Marketplace",
    "BUY AND SELL KENYA",
    "KENYA BUSINESS COMMUNITY 1",
    "SELL & BUY ONLINE MARKET",
    "HOUSING MARKETS",
    "PROPERTY KENYA",
    "LAND SALE AND RESALE",
    "GENERAL HOUSEHOLD SUPPLY",
    "HOME ESSENTIALS",
    "SOKO YETU",
    "PWANI ONLINE MARKET",
    "MOMBASA MARKET 3",
    "MOMBASA MARKET 1",
    "Mombasa Mums Market",
    "Buyers and Sellers Kenya",
    "FAMILY RETAIL STORE",
    "Online Buy and Sell",
    "SALES POINT KE",
    "Imara Daima Business Community",
    "Nairobi Southlands Market",
    "MOMBASA RD BUSINESS COMMUNITY",
    "SHOPPING MALL NRB",
    "Westlands Business Community",
    "NAIROBI BUYING AND SELLING",
    "CAR SHOWROOM",
    "SELLING AND BUYING NRB",
    "TECH BLOCK",
    "ELECTRONICS SALES",
    "DRESS CODE",
    "FASHION TRENDS BUSINESS GROUP",
    "WARDROBE",
    "Rongai Marketplace",
    "Langata Marketplace",
    "Runda Marketplace",
    "Kileleshwa Marketplace",
    "Karen Marketplace",
    "Lavington Marketplace",
    "Kilimani Marketplace",
    "Riverside Marketplace",
    "Ngong Road Marketplace",
    "Jogoo Road Marketplace",
]

# ============================================================
# GROUP CATEGORIES (Optional - for filtering)
# ============================================================

GROUP_CATEGORIES = {
    "nairobi": [
        "Nairobi Southlands Market",
        "Westlands Business Community",
        "NAIROBI BUYING AND SELLING",
        "Rongai Marketplace",
        "Langata Marketplace",
        "Runda Marketplace",
        "Kileleshwa Marketplace",
        "Karen Marketplace",
        "Lavington Marketplace",
        "Kilimani Marketplace",
        "Riverside Marketplace",
        "Ngong Road Marketplace",
        "Jogoo Road Marketplace",
        "SHOPPING MALL NRB",
        "SELLING AND BUYING NRB",
    ],
    "mombasa": [
        "MOMBASA MARKET 3",
        "MOMBASA MARKET 1",
        "Mombasa Mums Market",
        "PWANI ONLINE MARKET",
    ],
    "eldoret": [
        "ELDORET BUSINESS",
    ],
    "kakamega": [
        "KAKAMEGA ONLINE MARKET",
    ],
    "general": [
        "PRINT SHOP KENYA",
        "CARS AND TRUCKS",
        "AUTOMOBILE MARKET",
        "KENYA AUTO",
        "BUY AND SELL KENYA",
        "KENYA BUSINESS COMMUNITY 1",
        "SELL & BUY ONLINE MARKET",
        "HOUSING MARKETS",
        "PROPERTY KENYA",
        "LAND SALE AND RESALE",
        "GENERAL HOUSEHOLD SUPPLY",
        "HOME ESSENTIALS",
        "SOKO YETU",
    ],
    "fashion": [
        "DRESS CODE",
        "FASHION TRENDS BUSINESS GROUP",
        "WARDROBE",
    ],
    "electronics": [
        "TECH BLOCK",
        "ELECTRONICS SALES",
    ],
    "automotive": [
        "CARS AND TRUCKS",
        "AUTOMOBILE MARKET",
        "KENYA AUTO",
        "CAR SHOWROOM",
    ],
    "property": [
        "HOUSING MARKETS",
        "PROPERTY KENYA",
        "LAND SALE AND RESALE",
    ],
}

# ============================================================
# HELPER FUNCTIONS
# ============================================================

def get_groups_by_category(category: str) -> list:
    """Get all groups in a specific category"""
    return GROUP_CATEGORIES.get(category, [])

def get_all_groups() -> list:
    """Get all target groups"""
    return TARGET_GROUPS

def get_groups_for_testing() -> list:
    """Get a small subset of groups for testing"""
    return TARGET_GROUPS[:3]

def get_group_count() -> int:
    """Get total number of groups"""
    return len(TARGET_GROUPS)

def print_group_summary():
    """Print a summary of all groups by category"""
    print("\n" + "=" * 60)
    print("📊 GROUP SUMMARY")
    print("=" * 60)
    print(f"Total Groups: {len(TARGET_GROUPS)}")
    print("\nBy Category:")
    for category, groups in GROUP_CATEGORIES.items():
        print(f"  {category.upper()}: {len(groups)} groups")
        for g in groups[:5]:
            print(f"    - {g}")
        if len(groups) > 5:
            print(f"    ... and {len(groups) - 5} more")
    print("=" * 60)

# ============================================================
# USAGE EXAMPLE
# ============================================================

if __name__ == "__main__":
    print_group_summary()
    
    print("\n📋 Test Groups (first 3):")
    for group in get_groups_for_testing():
        print(f"  - {group}")
    
    print(f"\n📋 Nairobi Groups ({len(get_groups_by_category('nairobi'))}):")
    for group in get_groups_by_category('nairobi')[:5]:
        print(f"  - {group}")