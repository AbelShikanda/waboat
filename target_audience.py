"""
Target Audience - Contacts Database
===================================
Organized contacts for marketing and outreach.
"""

# ============================================================
# INDIVIDUAL CONTACTS - Organized by Category
# ============================================================

INDIVIDUAL_CONTACTS = {
    # ============================================================
    # CORE / BUSINESS CONTACTS
    # ============================================================
    "core": [
        {"name": "Your Tshirt Guy", "phone": "+254771016527"},
        {"name": "Print Shop Eld", "phone": "+254728157164"},
        {"name": "Your T-shirt Guy", "phone": "+254745242246"},
        {"name": "Yourtshirtguy", "phone": "+254771016527"},
    ],
    
    # ============================================================
    # CUSTOMERS (A-Z)
    # ============================================================
    "customers": [
        {"name": "Ali Mashjary", "phone": "+254710542417"},
        {"name": "Carol IG", "phone": "+254724053072"},
        {"name": "Christine Oduor IG", "phone": "+254722449605"},
        {"name": "David Murathe", "phone": "+254721732921"},
        {"name": "De_mwesh IG", "phone": "+254799040649"},
        {"name": "Devoke IG", "phone": "+254734688644"},
        {"name": "Eagle Eye Link Solutions", "phone": "+254728014743"},
        {"name": "East West Records", "phone": "+254700273998"},
        {"name": "Emma Mumbua", "phone": "+254727867459"},
        {"name": "EsekonCephos", "phone": "+254705028512"},
        {"name": "EssieBlessed", "phone": "+254723920621"},
        {"name": "HeavyD", "phone": "+254724980238"},
        {"name": "JABIR BACHANI", "phone": "+254721716714"},
        {"name": "JohnEvansKisembe", "phone": "+254727277373"},
        {"name": "Kaveeta Kapoor", "phone": "+254738998555"},
        {"name": "Linda Kendi", "phone": "+254717090504"},
        {"name": "Mercy IG", "phone": "+254704551973"},
        {"name": "MiyawaStephen", "phone": "+254704860264"},
        {"name": "Protich FB", "phone": "+254723740925"},
        {"name": "SaadiaHussein", "phone": "+254712880805"},
        {"name": "Saysad", "phone": "+254725998256"},
        {"name": "Suhayla", "phone": "+254707380850"},
        {"name": "Swabrina IG", "phone": "+254753750656"},
        {"name": "Warda Soud", "phone": "+254706388299"},
        {"name": "Wards Msa", "phone": "+254729359551"},
        {"name": "Wawesh", "phone": "+254700279383"},
        {"name": "Waziri Moses", "phone": "+254720327456"},
        {"name": "YasminMohammed", "phone": "+254722701444"},
    ],
}

# ============================================================
# HELPER FUNCTIONS
# ============================================================

def get_all_contacts() -> list:
    """Get all contacts from all categories"""
    all_contacts = []
    for category, contacts in INDIVIDUAL_CONTACTS.items():
        all_contacts.extend(contacts)
    return all_contacts

def get_contacts_by_category(category: str) -> list:
    """Get contacts from a specific category"""
    return INDIVIDUAL_CONTACTS.get(category, [])

def get_contact_by_name(name: str) -> dict:
    """Search for a contact by name"""
    name_lower = name.lower()
    all_contacts = get_all_contacts()
    for contact in all_contacts:
        if name_lower in contact.get("name", "").lower():
            return contact
    return None

def search_contacts(keyword: str) -> list:
    """Search contacts by keyword"""
    keyword_lower = keyword.lower()
    results = []
    all_contacts = get_all_contacts()
    for contact in all_contacts:
        if keyword_lower in contact.get("name", "").lower():
            results.append(contact)
        elif keyword_lower in contact.get("phone", ""):
            results.append(contact)
    return results

def get_phone_numbers_only(category: str = None) -> list:
    """Get only phone numbers from a category or all"""
    if category:
        contacts = get_contacts_by_category(category)
    else:
        contacts = get_all_contacts()
    return [c["phone"] for c in contacts if c.get("phone")]

def get_contact_count() -> int:
    """Get total number of contacts"""
    return len(get_all_contacts())

def print_contact_summary():
    """Print a summary of all contacts"""
    print("\n" + "=" * 60)
    print("📊 CONTACT SUMMARY")
    print("=" * 60)
    print(f"Total Contacts: {get_contact_count()}")
    print("\nBy Category:")
    for category, contacts in INDIVIDUAL_CONTACTS.items():
        print(f"  {category.upper()}: {len(contacts)} contacts")
        for c in contacts[:5]:
            print(f"    - {c['name']}: {c['phone']}")
        if len(contacts) > 5:
            print(f"    ... and {len(contacts) - 5} more")
    print("=" * 60)

# ============================================================
# USAGE EXAMPLES
# ============================================================

if __name__ == "__main__":
    print_contact_summary()
    
    # Get all customers
    customers = get_contacts_by_category("customers")
    print(f"\n📋 Customers: {len(customers)}")
    
    # Search for a contact
    contact = get_contact_by_name("Print Shop")
    if contact:
        print(f"\n🔍 Found: {contact['name']} - {contact['phone']}")
    
    # Search by keyword
    results = search_contacts("Shop")
    print(f"\n🔍 Found {len(results)} contacts with 'Shop':")
    for r in results[:5]:
        print(f"  - {r['name']}: {r['phone']}")