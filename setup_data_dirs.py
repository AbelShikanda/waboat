#!/usr/bin/env python3
"""
Setup data directories and create example product files
Run this once after cloning the repository
"""

import json
import shutil
from pathlib import Path

BASE_DIR = Path(__file__).parent
DATA_DIR = BASE_DIR / "data"
PRODUCTS_DIR = DATA_DIR / "products"

# Product files and their structures
PRODUCT_TEMPLATES = {
    "wa_products.json": {
        "products": [
            {
                "id": "wa_001",
                "product_name": "Example WhatsApp Product",
                "description": "This is an example product description",
                "url": "https://example.com/product",
                "status": "pending",
                "posted_date": None,
                "posted_time": None
            }
        ],
        "total_pending": 1,
        "total_posted": 0
    },
    "instagram_posts.json": {
        "posts": [
            {
                "id": "ig_001",
                "caption": "Example Instagram post",
                "description": "This is an example Instagram post",
                "url": "https://instagram.com/p/example",
                "status": "pending",
                "posted_date": None,
                "posted_time": None
            }
        ],
        "reels": [
            {
                "id": "ig_reel_001",
                "caption": "Example Instagram Reel",
                "description": "This is an example Instagram Reel",
                "url": "https://instagram.com/reel/example",
                "status": "pending",
                "posted_date": None,
                "posted_time": None
            }
        ],
        "total_pending": 2,
        "total_posted": 0
    },
    "facebook_posts.json": {
        "posts": [
            {
                "id": "fb_001",
                "caption": "Example Facebook post",
                "description": "This is an example Facebook post",
                "url": "https://facebook.com/posts/example",
                "status": "pending",
                "posted_date": None,
                "posted_time": None
            }
        ],
        "total_pending": 1,
        "total_posted": 0
    },
    "linkedin_posts.json": {
        "posts": [
            {
                "id": "li_001",
                "caption": "Example LinkedIn post",
                "description": "This is an example LinkedIn post",
                "url": "https://linkedin.com/posts/example",
                "status": "pending",
                "posted_date": None,
                "posted_time": None
            }
        ],
        "total_pending": 1,
        "total_posted": 0
    },
    "telegram_posts.json": {
        "posts": [
            {
                "id": "tg_001",
                "caption": "Example Telegram post",
                "description": "This is an example Telegram post",
                "url": "https://t.me/example",
                "status": "pending",
                "posted_date": None,
                "posted_time": None
            }
        ],
        "total_pending": 1,
        "total_posted": 0
    },
    "website_products.json": {
        "products": [
            {
                "id": "web_001",
                "product_name": "Example Website Product",
                "description": "This is an example website product",
                "url": "https://example.com/shop/product",
                "status": "pending",
                "posted_date": None,
                "posted_time": None
            }
        ],
        "total_pending": 1,
        "total_posted": 0
    },
    "x_posts.json": {
        "posts": [
            {
                "id": "x_001",
                "caption": "Example X/Twitter post",
                "description": "This is an example X/Twitter post",
                "url": "https://x.com/example/status/123",
                "status": "pending",
                "posted_date": None,
                "posted_time": None
            }
        ],
        "total_pending": 1,
        "total_posted": 0
    }
}

def setup_directories():
    """Create all necessary directories"""
    directories = [
        DATA_DIR,
        PRODUCTS_DIR,
        DATA_DIR / "analytics",
        DATA_DIR / "exports",
        DATA_DIR / "links",
        DATA_DIR / "marketing",
        BASE_DIR / "logs",
        BASE_DIR / "images",
        BASE_DIR / "notes",
    ]
    
    for dir_path in directories:
        dir_path.mkdir(parents=True, exist_ok=True)
        print(f"✅ Created: {dir_path}")
        
        # Create .gitkeep file
        gitkeep = dir_path / ".gitkeep"
        gitkeep.touch(exist_ok=True)

def create_example_products():
    """Create example product files"""
    for filename, structure in PRODUCT_TEMPLATES.items():
        file_path = PRODUCTS_DIR / filename
        
        # Create the actual file with example data
        with open(file_path, 'w') as f:
            json.dump(structure, f, indent=2)
        print(f"✅ Created: {file_path}")
        
        # Create example version (to be tracked in git)
        example_path = PRODUCTS_DIR / filename.replace('.json', '.example.json')
        if not example_path.exists():
            shutil.copy(file_path, example_path)
            print(f"✅ Created example: {example_path}")

def create_initial_data_files():
    """Create initial empty data files"""
    initial_files = {
        "pending_queue.json": [],
        "posted_history.json": [],
        "failed_groups.json": {},
        "blacklist.json": [],
        "blogs.json": [],
        "blogs_sent.json": [],
        "retry_queue.json": []
    }
    
    for filename, structure in initial_files.items():
        file_path = DATA_DIR / filename
        if not file_path.exists():
            with open(file_path, 'w') as f:
                json.dump(structure, f, indent=2)
            print(f"✅ Created: {file_path}")

def create_readme_files():
    """Create README files for data directories"""
    readmes = {
        DATA_DIR / "README.md": "# Data Directory\n\nThis directory contains dynamic data files generated by the WhatsApp bot.\n\n## Structure\n\n- `analytics/` - Analytics data and reports\n- `exports/` - Exported data files\n- `links/` - Group link data\n- `marketing/` - Marketing campaign data\n- `products/` - Product data files\n\n## File Types\n\n- `*.db` - SQLite databases\n- `*.json` - JSON data files\n- `*.csv` - CSV export files\n- `*.log` - Log files\n\n**Note:** All files in this directory are ignored by git except templates and examples.",
        
        PRODUCTS_DIR / "README.md": "# Products Directory\n\nProduct data files for the WhatsApp bot.\n\n## Files\n\n- `*.example.json` - Template files (tracked in git)\n- `*.json` - Runtime files (ignored by git)\n\n## Sources\n\n- `wa_products.json` - WhatsApp products\n- `instagram_posts.json` - Instagram posts\n- `facebook_posts.json` - Facebook posts\n- `linkedin_posts.json` - LinkedIn posts\n- `telegram_posts.json` - Telegram posts\n- `website_products.json` - Website products\n- `x_posts.json` - X/Twitter posts\n\n## Usage\n\n1. Copy `*.example.json` to `*.json`\n2. Add your products\n3. Run the bot\n\nThe bot will update the status fields automatically."
    }
    
    for file_path, content in readmes.items():
        if not file_path.exists():
            with open(file_path, 'w') as f:
                f.write(content)
            print(f"✅ Created: {file_path}")

def main():
    print("=" * 60)
    print("🔧 Setting up data directories...")
    print("=" * 60)
    
    setup_directories()
    create_example_products()
    create_initial_data_files()
    create_readme_files()
    
    print("\n" + "=" * 60)
    print("✅ Setup complete!")
    print("=" * 60)
    print("\n📁 Data directories created:")
    print("   - data/products/ (with example files)")
    print("   - data/analytics/")
    print("   - data/exports/")
    print("   - data/links/")
    print("   - data/marketing/")
    print("   - logs/")
    print("   - images/")
    print("   - notes/")
    print("\n📝 Next steps:")
    print("   1. Copy example files to actual files")
    print("   2. Add your products to the JSON files")
    print("   3. Run the bot!")

if __name__ == "__main__":
    main()