"""
Analytics Module for WhatsApp Bot
=================================
Separate module that handles all analytics functionality.
Can be called as a command from the main bot.
"""

import sqlite3
import json
import csv
import webbrowser
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Optional

# ============================================================
# CONFIGURATION
# ============================================================

BASE_DIR = Path(__file__).parent
DATA_DIR = BASE_DIR / "data"
DB_FILE = DATA_DIR / "whatsapp_data.db"
EXPORTS_DIR = DATA_DIR / "exports"

# Create directories
DATA_DIR.mkdir(parents=True, exist_ok=True)
EXPORTS_DIR.mkdir(parents=True, exist_ok=True)

# ============================================================
# DATABASE MANAGER
# ============================================================

class DatabaseManager:
    """Manages SQLite database operations for WhatsApp data"""
    
    def __init__(self, db_path: Path = DB_FILE):
        self.db_path = db_path
        self.connection = None
        self.cursor = None
        self._connect()
    
    def _connect(self):
        """Connect to database"""
        if not self.db_path.exists():
            print(f"❌ Database not found at: {self.db_path}")
            print("Run the bot with 'post' command first to collect data.")
            return
        
        self.connection = sqlite3.connect(self.db_path)
        self.connection.row_factory = sqlite3.Row
        self.cursor = self.connection.cursor()
    
    def close(self):
        """Close database connection"""
        if self.connection:
            self.connection.close()
            self.connection = None
            self.cursor = None
    
    def is_connected(self) -> bool:
        """Check if database is connected"""
        return self.connection is not None
    
    def get_db_stats(self) -> Dict:
        """Get overall database statistics"""
        if not self.is_connected():
            return {"error": "Database not connected"}
        
        stats = {}
        
        self.cursor.execute("SELECT COUNT(*) FROM groups")
        stats['total_groups'] = self.cursor.fetchone()[0]
        
        self.cursor.execute("SELECT COUNT(*) FROM messages")
        stats['total_messages'] = self.cursor.fetchone()[0]
        
        self.cursor.execute("SELECT COUNT(*) FROM products_posted")
        stats['total_products_posted'] = self.cursor.fetchone()[0]
        
        self.cursor.execute("SELECT COUNT(*) FROM word_frequency")
        stats['unique_words'] = self.cursor.fetchone()[0]
        
        self.cursor.execute("SELECT COUNT(*) FROM trending_topics")
        stats['trending_topics'] = self.cursor.fetchone()[0]
        
        self.cursor.execute("SELECT MIN(timestamp), MAX(timestamp) FROM messages")
        min_time, max_time = self.cursor.fetchone()
        stats['first_message_date'] = min_time
        stats['last_message_date'] = max_time
        
        return stats
    
    def get_most_active_groups(self, limit: int = 10) -> List[Dict]:
        """Get most active groups"""
        if not self.is_connected():
            return []
        
        self.cursor.execute("""
            SELECT 
                g.group_name,
                g.total_messages,
                g.total_posts_from_us,
                COUNT(DISTINCT m.sender_name) as unique_senders,
                MAX(m.timestamp) as last_active
            FROM groups g
            LEFT JOIN messages m ON g.id = m.group_id
            GROUP BY g.id
            ORDER BY g.total_messages DESC
            LIMIT ?
        """, (limit,))
        
        return [dict(row) for row in self.cursor.fetchall()]
    
    def get_most_active_times(self) -> List[Dict]:
        """Get most active times"""
        if not self.is_connected():
            return []
        
        self.cursor.execute("""
            SELECT 
                hour,
                SUM(message_count) as total_messages,
                COUNT(DISTINCT group_id) as groups_active
            FROM daily_activity
            GROUP BY hour
            ORDER BY hour
        """)
        
        return [dict(row) for row in self.cursor.fetchall()]
    
    def get_most_popular_words(self, limit: int = 20) -> List[Dict]:
        """Get most popular words"""
        if not self.is_connected():
            return []
        
        self.cursor.execute("""
            SELECT 
                word,
                SUM(frequency) as total_frequency,
                COUNT(DISTINCT group_id) as groups_mentioned
            FROM word_frequency
            GROUP BY word
            ORDER BY total_frequency DESC
            LIMIT ?
        """, (limit,))
        
        return [dict(row) for row in self.cursor.fetchall()]
    
    def get_most_popular_products(self, limit: int = 10) -> List[Dict]:
        """Get most popular products"""
        if not self.is_connected():
            return []
        
        self.cursor.execute("""
            SELECT 
                product_name,
                source,
                COUNT(DISTINCT posted_to_group_id) as groups_posted,
                COUNT(*) as total_posts,
                MIN(posted_at) as first_posted,
                MAX(posted_at) as last_posted
            FROM products_posted
            WHERE product_name != ''
            GROUP BY product_name, source
            ORDER BY total_posts DESC, groups_posted DESC
            LIMIT ?
        """, (limit,))
        
        return [dict(row) for row in self.cursor.fetchall()]
    
    def get_trending_topics(self, days: int = 7, limit: int = 15) -> List[Dict]:
        """Get trending topics"""
        if not self.is_connected():
            return []
        
        self.cursor.execute("""
            SELECT 
                topic,
                SUM(mentions) as total_mentions,
                COUNT(DISTINCT group_id) as groups_mentioned,
                MIN(first_mentioned) as first_seen,
                MAX(last_mentioned) as last_seen
            FROM trending_topics
            WHERE last_mentioned >= datetime('now', '-? days')
            GROUP BY topic
            ORDER BY total_mentions DESC
            LIMIT ?
        """, (days, limit))
        
        return [dict(row) for row in self.cursor.fetchall()]
    
    def get_recent_messages(self, limit: int = 20) -> List[Dict]:
        """Get recent messages"""
        if not self.is_connected():
            return []
        
        self.cursor.execute("""
            SELECT 
                g.group_name,
                m.sender_name,
                m.message_text,
                m.timestamp,
                m.is_from_us
            FROM messages m
            JOIN groups g ON m.group_id = g.id
            ORDER BY m.timestamp DESC
            LIMIT ?
        """, (limit,))
        
        return [dict(row) for row in self.cursor.fetchall()]
    
    def get_group_analytics(self, group_name: str) -> Dict:
        """Get analytics for a specific group"""
        if not self.is_connected():
            return {"error": "Database not connected"}
        
        self.cursor.execute("SELECT id FROM groups WHERE group_name = ?", (group_name,))
        result = self.cursor.fetchone()
        if not result:
            return {"error": "Group not found"}
        
        group_id = result[0]
        analytics = {}
        
        # General stats
        self.cursor.execute("""
            SELECT 
                COUNT(*) as total_messages,
                COUNT(DISTINCT sender_name) as unique_senders,
                SUM(CASE WHEN is_from_us = 1 THEN 1 ELSE 0 END) as messages_from_us,
                MIN(timestamp) as first_message,
                MAX(timestamp) as last_message
            FROM messages
            WHERE group_id = ?
        """, (group_id,))
        analytics['stats'] = dict(self.cursor.fetchone())
        
        # Hourly activity
        self.cursor.execute("""
            SELECT hour, SUM(message_count) as messages
            FROM daily_activity
            WHERE group_id = ?
            GROUP BY hour
            ORDER BY hour
        """, (group_id,))
        analytics['hourly_activity'] = [dict(row) for row in self.cursor.fetchall()]
        
        # Top words
        self.cursor.execute("""
            SELECT word, frequency
            FROM word_frequency
            WHERE group_id = ?
            ORDER BY frequency DESC
            LIMIT 10
        """, (group_id,))
        analytics['top_words'] = [dict(row) for row in self.cursor.fetchall()]
        
        # Products posted
        self.cursor.execute("""
            SELECT product_name, COUNT(*) as post_count, MAX(posted_at) as last_posted
            FROM products_posted
            WHERE posted_to_group_id = ?
            GROUP BY product_name
            ORDER BY post_count DESC
            LIMIT 10
        """, (group_id,))
        analytics['products_posted'] = [dict(row) for row in self.cursor.fetchall()]
        
        return analytics
    
    def get_all_groups(self) -> List[Dict]:
        """Get all groups with stats"""
        if not self.is_connected():
            return []
        
        self.cursor.execute("""
            SELECT group_name, total_messages, total_posts_from_us, last_active
            FROM groups
            ORDER BY total_messages DESC
        """)
        
        return [dict(row) for row in self.cursor.fetchall()]


# ============================================================
# DISPLAY FUNCTIONS
# ============================================================

class AnalyticsDisplay:
    """Handles display of analytics data"""
    
    @staticmethod
    def show_dashboard(db: DatabaseManager):
        """Display main dashboard"""
        if not db.is_connected():
            print("❌ Database not available. Run 'post' command first.")
            return
        
        print("\n" + "=" * 80)
        print("📊 WHATSAPP ANALYTICS DASHBOARD".center(80))
        print("=" * 80)
        print(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print("=" * 80)
        
        # Stats
        stats = db.get_db_stats()
        print("\n📈 DATABASE STATISTICS")
        print("━" * 40)
        print(f"  📱 Groups: {stats['total_groups']}")
        print(f"  💬 Messages: {stats['total_messages']:,}")
        print(f"  📦 Products Posted: {stats['total_products_posted']}")
        print(f"  🔤 Unique Words: {stats['unique_words']:,}")
        print(f"  📰 Trending Topics: {stats['trending_topics']}")
        print(f"  📅 Data from: {stats['first_message_date']}")
        print(f"     to: {stats['last_message_date']}")
        
        # Active Groups
        print("\n🏆 MOST ACTIVE GROUPS")
        print("━" * 40)
        groups = db.get_most_active_groups(10)
        for i, g in enumerate(groups, 1):
            print(f"  {i:2}. {g['group_name'][:30]:30} Messages: {g['total_messages']:>8,}  Senders: {g['unique_senders'] or 0}")
        
        # Active Times
        print("\n⏰ PEAK ACTIVITY TIMES")
        print("━" * 40)
        times = db.get_most_active_times()
        if times:
            max_messages = max([t['total_messages'] for t in times])
            for t in times:
                hour = f"{t['hour']:02d}:00"
                bars = "█" * int((t['total_messages'] / max_messages) * 20)
                print(f"  {hour}: {t['total_messages']:>6,} messages {bars}")
        
        # Popular Words
        print("\n🔤 MOST POPULAR WORDS")
        print("━" * 40)
        words = db.get_most_popular_words(15)
        for i, w in enumerate(words, 1):
            print(f"  {i:2}. {w['word']:15} Mentions: {w['total_frequency']:>8,}  Groups: {w['groups_mentioned']}")
        
        # Trending Topics
        print("\n📰 TRENDING TOPICS")
        print("━" * 40)
        topics = db.get_trending_topics(7, 10)
        for i, t in enumerate(topics, 1):
            print(f"  {i:2}. #{t['topic']:20} Mentions: {t['total_mentions']:>6}  Groups: {t['groups_mentioned']}")
    
    @staticmethod
    def show_trending(db: DatabaseManager, days: int = 7, limit: int = 15):
        """Display trending topics"""
        if not db.is_connected():
            print("❌ Database not available. Run 'post' command first.")
            return
        
        topics = db.get_trending_topics(days, limit)
        
        print(f"\n📰 TRENDING TOPICS (Last {days} days)")
        print("=" * 60)
        print(f"{'#':<4} {'Topic':<30} {'Mentions':>10} {'Groups':>8}")
        print("-" * 60)
        for i, t in enumerate(topics, 1):
            print(f"{i:<4} #{t['topic'][:28]:<30} {t['total_mentions']:>10} {t['groups_mentioned']:>8}")
    
    @staticmethod
    def show_groups(db: DatabaseManager, limit: int = None):
        """Display groups"""
        if not db.is_connected():
            print("❌ Database not available. Run 'post' command first.")
            return
        
        if limit:
            groups = db.get_most_active_groups(limit)
            print(f"\n📱 TOP {limit} GROUPS")
        else:
            groups = db.get_all_groups()
            print(f"\n📱 ALL GROUPS ({len(groups)})")
        
        print("=" * 60)
        print(f"{'Group Name':<40} {'Messages':>12} {'From Us':>8}")
        print("-" * 60)
        for g in groups:
            print(f"{g['group_name'][:40]:<40} {g['total_messages']:>12,} {g['total_posts_from_us']:>8}")
    
    @staticmethod
    def show_group_details(db: DatabaseManager, group_name: str):
        """Display detailed analytics for a specific group"""
        if not db.is_connected():
            print("❌ Database not available. Run 'post' command first.")
            return
        
        print(f"\n📊 DETAILED ANALYTICS FOR: {group_name}")
        print("=" * 80)
        
        analytics = db.get_group_analytics(group_name)
        if "error" in analytics:
            print(f"❌ {analytics['error']}")
            return
        
        stats = analytics['stats']
        print(f"\n📈 GROUP STATISTICS")
        print("━" * 40)
        print(f"  Total Messages: {stats['total_messages']:,}")
        print(f"  Unique Senders: {stats['unique_senders']}")
        print(f"  Messages from Us: {stats['messages_from_us']}")
        print(f"  First Message: {stats['first_message']}")
        print(f"  Last Message: {stats['last_message']}")
        
        if analytics['hourly_activity']:
            print(f"\n⏰ HOURLY ACTIVITY")
            print("━" * 40)
            max_msgs = max([h['messages'] for h in analytics['hourly_activity']])
            for h in analytics['hourly_activity']:
                hour = f"{h['hour']:02d}:00"
                bars = "█" * int((h['messages'] / max_msgs) * 20)
                print(f"  {hour}: {h['messages']:>6,} {bars}")
        
        if analytics['top_words']:
            print(f"\n🔤 TOP WORDS IN THIS GROUP")
            print("━" * 40)
            for w in analytics['top_words']:
                print(f"  {w['word']:15} Frequency: {w['frequency']:,}")
        
        if analytics['products_posted']:
            print(f"\n🛍️ PRODUCTS POSTED TO THIS GROUP")
            print("━" * 40)
            for p in analytics['products_posted']:
                print(f"  {p['product_name'][:30]:30} Posts: {p['post_count']}  Last: {p['last_posted']}")
    
    @staticmethod
    def show_stats(db: DatabaseManager):
        """Show database statistics"""
        if not db.is_connected():
            print("❌ Database not available. Run 'post' command first.")
            return
        
        stats = db.get_db_stats()
        print("\n📊 DATABASE STATISTICS")
        print("=" * 60)
        print(f"  Total Groups: {stats['total_groups']}")
        print(f"  Total Messages: {stats['total_messages']:,}")
        print(f"  Products Posted: {stats['total_products_posted']}")
        print(f"  Unique Words: {stats['unique_words']:,}")
        print(f"  Trending Topics: {stats['trending_topics']}")
        print(f"  Data Range: {stats['first_message_date']} to {stats['last_message_date']}")


# ============================================================
# EXPORT FUNCTIONS
# ============================================================

class AnalyticsExport:
    """Handles exporting analytics data"""
    
    @staticmethod
    def export_to_csv(db: DatabaseManager, output_dir: Path = None):
        """Export data to CSV files"""
        if not db.is_connected():
            print("❌ Database not available. Run 'post' command first.")
            return
        
        if output_dir is None:
            output_dir = EXPORTS_DIR
        output_dir.mkdir(exist_ok=True)
        
        print(f"\n📤 Exporting data to CSV...")
        print(f"   Output directory: {output_dir}")
        
        # Export groups
        db.cursor.execute("SELECT * FROM groups")
        groups_data = db.cursor.fetchall()
        if groups_data:
            with open(output_dir / "groups.csv", 'w', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                writer.writerow([desc[0] for desc in db.cursor.description])
                writer.writerows(groups_data)
            print(f"  ✅ Exported {len(groups_data)} groups")
        
        # Export messages (limited)
        db.cursor.execute("SELECT * FROM messages ORDER BY timestamp DESC LIMIT 1000")
        messages_data = db.cursor.fetchall()
        if messages_data:
            with open(output_dir / "messages_last_1000.csv", 'w', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                writer.writerow([desc[0] for desc in db.cursor.description])
                writer.writerows(messages_data)
            print(f"  ✅ Exported {len(messages_data)} recent messages")
        
        # Export analytics summaries
        groups = db.get_most_active_groups(50)
        if groups:
            with open(output_dir / "most_active_groups.csv", 'w', newline='', encoding='utf-8') as f:
                writer = csv.DictWriter(f, fieldnames=groups[0].keys())
                writer.writeheader()
                writer.writerows(groups)
            print(f"  ✅ Exported {len(groups)} active groups")
        
        words = db.get_most_popular_words(100)
        if words:
            with open(output_dir / "popular_words.csv", 'w', newline='', encoding='utf-8') as f:
                writer = csv.DictWriter(f, fieldnames=words[0].keys())
                writer.writeheader()
                writer.writerows(words)
            print(f"  ✅ Exported {len(words)} popular words")
        
        topics = db.get_trending_topics(30, 50)
        if topics:
            with open(output_dir / "trending_topics.csv", 'w', newline='', encoding='utf-8') as f:
                writer = csv.DictWriter(f, fieldnames=topics[0].keys())
                writer.writeheader()
                writer.writerows(topics)
            print(f"  ✅ Exported {len(topics)} trending topics")
        
        print(f"\n✅ All exports completed to: {output_dir}")
    
    @staticmethod
    def generate_html_report(db: DatabaseManager):
        """Generate HTML report"""
        if not db.is_connected():
            print("❌ Database not available. Run 'post' command first.")
            return
        
        try:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            output_file = EXPORTS_DIR / f"analytics_report_{timestamp}.html"
            output_file.parent.mkdir(exist_ok=True)
            
            # Collect data
            stats = db.get_db_stats()
            groups = db.get_most_active_groups(10)
            times = db.get_most_active_times()
            words = db.get_most_popular_words(20)
            topics = db.get_trending_topics(7, 15)
            
            # Build HTML (simplified version - you can expand this)
            html = f"""
<!DOCTYPE html>
<html>
<head>
    <title>WhatsApp Analytics Report</title>
    <style>
        body {{ font-family: Arial, sans-serif; margin: 20px; background: #f0f2f5; }}
        .header {{ background: #25D366; color: white; padding: 20px; border-radius: 10px; }}
        .stats {{ display: grid; grid-template-columns: repeat(5, 1fr); gap: 15px; margin: 20px 0; }}
        .stat-card {{ background: white; padding: 15px; border-radius: 8px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }}
        .stat-card .number {{ font-size: 24px; font-weight: bold; color: #128C7E; }}
        .stat-card .label {{ color: #666; }}
        table {{ width: 100%; border-collapse: collapse; background: white; border-radius: 8px; overflow: hidden; }}
        th, td {{ padding: 12px; text-align: left; border-bottom: 1px solid #eee; }}
        th {{ background: #f8f9fa; }}
        tr:hover {{ background: #f8f9fa; }}
        .section {{ margin: 20px 0; }}
        .section h2 {{ color: #333; }}
    </style>
</head>
<body>
    <div class="header">
        <h1>📊 WhatsApp Analytics Report</h1>
        <p>Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>
        <p>Data Range: {stats.get('first_message_date', 'N/A')} to {stats.get('last_message_date', 'N/A')}</p>
    </div>
    
    <div class="stats">
        <div class="stat-card"><div class="number">{stats.get('total_groups', 0)}</div><div class="label">📱 Groups</div></div>
        <div class="stat-card"><div class="number">{stats.get('total_messages', 0):,}</div><div class="label">💬 Messages</div></div>
        <div class="stat-card"><div class="number">{stats.get('total_products_posted', 0)}</div><div class="label">📦 Products</div></div>
        <div class="stat-card"><div class="number">{stats.get('unique_words', 0):,}</div><div class="label">🔤 Words</div></div>
        <div class="stat-card"><div class="number">{stats.get('trending_topics', 0)}</div><div class="label">📰 Topics</div></div>
    </div>
    
    <div class="section">
        <h2>🏆 Most Active Groups</h2>
        <table>
            <tr><th>#</th><th>Group</th><th>Messages</th><th>Senders</th></tr>
            {''.join([f"<tr><td>{i}</td><td>{g['group_name']}</td><td>{g['total_messages']:,}</td><td>{g.get('unique_senders', 0)}</td></tr>" for i, g in enumerate(groups, 1)]) if groups else "<tr><td colspan='4'>No data available</td></tr>"}
        </table>
    </div>
    
    <div class="section">
        <h2>📰 Trending Topics</h2>
        <table>
            <tr><th>#</th><th>Topic</th><th>Mentions</th><th>Groups</th></tr>
            {''.join([f"<tr><td>{i}</td><td>#{t['topic']}</td><td>{t['total_mentions']}</td><td>{t['groups_mentioned']}</td></tr>" for i, t in enumerate(topics, 1)]) if topics else "<tr><td colspan='4'>No data available</td></tr>"}
        </table>
    </div>
</body>
</html>
"""
            
            with open(output_file, 'w', encoding='utf-8') as f:
                f.write(html)
            
            print(f"\n✅ HTML report generated: {output_file}")
            webbrowser.open(str(output_file))
            
        except Exception as e:
            print(f"❌ Error generating HTML: {e}")


# ============================================================
# MAIN FUNCTION FOR COMMAND LINE
# ============================================================

def run_analytics_command(args):
    """
    Main function called from the bot with command arguments
    """
    db = DatabaseManager()
    
    try:
        if not db.is_connected():
            print("❌ Database not found. Run 'post' command first to collect data.")
            return
        
        # Route to appropriate display function
        if args.command == "stats":
            AnalyticsDisplay.show_stats(db)
        
        elif args.command == "groups":
            AnalyticsDisplay.show_groups(db, args.limit)
        
        elif args.command == "trending":
            AnalyticsDisplay.show_trending(db, args.days or 7, args.limit or 15)
        
        elif args.command == "analytics":
            if args.html:
                AnalyticsExport.generate_html_report(db)
            elif args.export:
                AnalyticsExport.export_to_csv(db)
            elif args.group:
                AnalyticsDisplay.show_group_details(db, args.group)
            elif args.list_groups:
                AnalyticsDisplay.show_groups(db, None)
            else:
                AnalyticsDisplay.show_dashboard(db)
        
        else:
            print(f"❌ Unknown analytics command: {args.command}")
    
    except Exception as e:
        print(f"❌ Error running analytics: {e}")
        import traceback
        traceback.print_exc()
    finally:
        db.close()


# ============================================================
# HELP FUNCTIONS
# ============================================================

def get_analytics_help() -> Dict:
    """Get help information for analytics commands"""
    return {
        "analytics": {
            "help": "Show analytics dashboard",
            "usage": "analytics [--html] [--export] [--group NAME] [--list-groups]",
            "examples": [
                "analytics                    # Show dashboard",
                "analytics --html             # Generate HTML report",
                "analytics --export           # Export to CSV",
                "analytics --group 'Group Name'  # Group details",
                "analytics --list-groups      # List all groups"
            ]
        },
        "trending": {
            "help": "Show trending topics",
            "usage": "trending [--days N] [--limit N]",
            "examples": [
                "trending                 # Last 7 days",
                "trending --days 14       # Last 14 days",
                "trending --limit 20      # Show 20 topics"
            ]
        },
        "groups": {
            "help": "List all groups with activity stats",
            "usage": "groups [--limit N]",
            "examples": [
                "groups              # Show all groups",
                "groups --limit 10   # Show top 10"
            ]
        },
        "stats": {
            "help": "Show database statistics",
            "usage": "stats",
            "examples": ["stats"]
        }
    }


if __name__ == "__main__":
    # For testing the analytics module directly
    import argparse
    
    parser = argparse.ArgumentParser(description='Analytics Module Test')
    parser.add_argument('command', choices=['analytics', 'trending', 'groups', 'stats'],
                       help='Command to execute')
    parser.add_argument('--html', '-H', action='store_true', help='Generate HTML report')
    parser.add_argument('--export', '-e', action='store_true', help='Export to CSV')
    parser.add_argument('--group', type=str, help='Show analytics for specific group')
    parser.add_argument('--list-groups', action='store_true', help='List all groups')
    parser.add_argument('--days', '-d', type=int, default=7, help='Days for trending')
    parser.add_argument('--limit', '-l', type=int, default=10, help='Limit for results')
    
    args = parser.parse_args()
    run_analytics_command(args)