"""
Database Logic Module
=====================
Handles all SQLite database operations for WhatsApp data.
Separated from group_poster.py for better organization.
"""

import sqlite3
import json
import re
from pathlib import Path
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Any

# ============================================================
# CONFIGURATION
# ============================================================

BASE_DIR = Path(__file__).parent
DATA_DIR = BASE_DIR / "data"
DB_FILE = DATA_DIR / "whatsapp_data.db"

# Create directory
DATA_DIR.mkdir(parents=True, exist_ok=True)

# ============================================================
# DATABASE MANAGER
# ============================================================

class DatabaseManager:
    """Manages SQLite database operations for WhatsApp data"""
    
    def __init__(self, db_path: Path = DB_FILE):
        self.db_path = db_path
        self.connection = None
        self.cursor = None
        self._initialize_database()
    
    def _initialize_database(self):
        """Initialize database with all required tables"""
        self.connection = sqlite3.connect(self.db_path)
        self.cursor = self.connection.cursor()
        
        # Create tables
        self.cursor.executescript("""
            -- Groups table
            CREATE TABLE IF NOT EXISTS groups (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                group_name TEXT UNIQUE NOT NULL,
                first_seen TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                last_active TIMESTAMP,
                total_messages INTEGER DEFAULT 0,
                total_posts_from_us INTEGER DEFAULT 0,
                is_active BOOLEAN DEFAULT 1,
                status TEXT DEFAULT 'active'
            );
            
            -- Messages table
            CREATE TABLE IF NOT EXISTS messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                group_id INTEGER,
                sender_name TEXT,
                sender_number TEXT,
                message_text TEXT,
                message_type TEXT,
                timestamp TIMESTAMP,
                is_from_us BOOLEAN DEFAULT 0,
                is_media BOOLEAN DEFAULT 0,
                media_type TEXT,
                collected_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (group_id) REFERENCES groups(id)
            );
            
            -- Products posted table
            CREATE TABLE IF NOT EXISTS products_posted (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                product_id TEXT NOT NULL,
                product_name TEXT,
                source TEXT,
                description TEXT,
                url TEXT,
                posted_to_group_id INTEGER,
                message_sent TEXT,
                posted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                engagement_indicators TEXT,
                FOREIGN KEY (posted_to_group_id) REFERENCES groups(id)
            );
            
            -- Word frequency table
            CREATE TABLE IF NOT EXISTS word_frequency (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                word TEXT NOT NULL,
                group_id INTEGER,
                frequency INTEGER DEFAULT 1,
                last_seen TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(word, group_id),
                FOREIGN KEY (group_id) REFERENCES groups(id)
            );
            
            -- Daily activity table
            CREATE TABLE IF NOT EXISTS daily_activity (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                group_id INTEGER,
                date DATE,
                hour INTEGER,
                message_count INTEGER DEFAULT 0,
                active_users INTEGER DEFAULT 0,
                FOREIGN KEY (group_id) REFERENCES groups(id)
            );
            
            -- Trending topics table
            CREATE TABLE IF NOT EXISTS trending_topics (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                topic TEXT NOT NULL,
                group_id INTEGER,
                mentions INTEGER DEFAULT 1,
                first_mentioned TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                last_mentioned TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (group_id) REFERENCES groups(id)
            );
            
            -- Indexes for performance
            CREATE INDEX IF NOT EXISTS idx_messages_timestamp ON messages(timestamp);
            CREATE INDEX IF NOT EXISTS idx_messages_group_id ON messages(group_id);
            CREATE INDEX IF NOT EXISTS idx_messages_is_from_us ON messages(is_from_us);
            CREATE INDEX IF NOT EXISTS idx_products_posted_group_id ON products_posted(posted_to_group_id);
            CREATE INDEX IF NOT EXISTS idx_products_posted_posted_at ON products_posted(posted_at);
            CREATE INDEX IF NOT EXISTS idx_word_frequency_group_id ON word_frequency(group_id);
            CREATE INDEX IF NOT EXISTS idx_daily_activity_group_id ON daily_activity(group_id);
            CREATE INDEX IF NOT EXISTS idx_daily_activity_date ON daily_activity(date);
            CREATE INDEX IF NOT EXISTS idx_trending_topics_group_id ON trending_topics(group_id);
        """)
        
        self.connection.commit()
        print("✅ Database initialized successfully")
    
    def get_connection(self):
        """Get database connection"""
        if self.connection is None:
            self._initialize_database()
        return self.connection
    
    def get_cursor(self):
        """Get database cursor"""
        if self.cursor is None:
            self._initialize_database()
        return self.cursor
    
    def close(self):
        """Close database connection"""
        if self.connection:
            self.connection.close()
            self.connection = None
            self.cursor = None
    
    def execute(self, query, params=None):
        """Execute a query and return cursor"""
        cursor = self.get_cursor()
        if params:
            cursor.execute(query, params)
        else:
            cursor.execute(query)
        return cursor
    
    def commit(self):
        """Commit changes"""
        if self.connection:
            self.connection.commit()
    
    # ============================================================
    # GROUP OPERATIONS
    # ============================================================
    
    def get_or_create_group(self, group_name: str) -> int:
        """Get group ID or create new group"""
        cursor = self.get_cursor()
        cursor.execute("SELECT id FROM groups WHERE group_name = ?", (group_name,))
        result = cursor.fetchone()
        
        if result:
            return result[0]
        else:
            cursor.execute(
                "INSERT INTO groups (group_name, first_seen, last_active) VALUES (?, ?, ?)",
                (group_name, datetime.now(), datetime.now())
            )
            self.commit()
            return cursor.lastrowid
    
    def update_group_activity(self, group_id: int, messages_count: int = 1, posts_from_us: int = 0):
        """Update group activity statistics"""
        cursor = self.get_cursor()
        cursor.execute("""
            UPDATE groups 
            SET last_active = ?, 
                total_messages = total_messages + ?,
                total_posts_from_us = total_posts_from_us + ?
            WHERE id = ?
        """, (datetime.now(), messages_count, posts_from_us, group_id))
        self.commit()
    
    # ============================================================
    # MESSAGE OPERATIONS
    # ============================================================
    
    def save_message(self, group_id: int, sender: str, message: str, 
                    timestamp: datetime, is_from_us: bool = False,
                    message_type: str = "text", sender_number: str = "",
                    is_media: bool = False, media_type: str = ""):
        """Save a message to database"""
        cursor = self.get_cursor()
        cursor.execute("""
            INSERT INTO messages 
            (group_id, sender_name, sender_number, message_text, message_type, 
             timestamp, is_from_us, is_media, media_type)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (group_id, sender, sender_number, message[:5000], message_type,
              timestamp, is_from_us, is_media, media_type))
        
        # Update word frequency
        words = self._extract_words(message)
        for word in words:
            cursor.execute("""
                INSERT INTO word_frequency (word, group_id, frequency, last_seen)
                VALUES (?, ?, 1, ?)
                ON CONFLICT(word, group_id) 
                DO UPDATE SET frequency = frequency + 1, last_seen = ?
            """, (word, group_id, datetime.now(), datetime.now()))
        
        # Update daily activity
        cursor.execute("""
            INSERT INTO daily_activity (group_id, date, hour, message_count)
            VALUES (?, ?, ?, 1)
            ON CONFLICT(group_id, date, hour) 
            DO UPDATE SET message_count = message_count + 1
        """, (group_id, timestamp.date().isoformat(), timestamp.hour))
        
        self.commit()
        return cursor.lastrowid
    
    def _extract_words(self, message: str) -> List[str]:
        """Extract meaningful words from message (exclude common words)"""
        # Clean message
        clean = re.sub(r'[^a-zA-Z\s]', ' ', message.lower())
        words = clean.split()
        
        # Filter common words and short words
        common_words = {'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 
                       'for', 'of', 'with', 'by', 'from', 'up', 'about', 'into', 'through',
                       'during', 'including', 'without', 'against', 'among', 'between',
                       'is', 'are', 'was', 'were', 'be', 'been', 'being', 'am', 'that',
                       'this', 'these', 'those', 'it', 'its', 'he', 'she', 'we', 'they',
                       'i', 'you', 'me', 'us', 'them', 'my', 'your', 'our', 'their',
                       'have', 'has', 'had', 'do', 'does', 'did', 'will', 'would', 'could',
                       'should', 'may', 'might', 'must', 'shall', 'can'}
        
        return [w for w in words if len(w) > 3 and w not in common_words][:50]
    
    # ============================================================
    # PRODUCT OPERATIONS
    # ============================================================
    
    def save_product_post(self, product: dict, group_id: int, message: str):
        """Save a product post to database"""
        cursor = self.get_cursor()
        cursor.execute("""
            INSERT INTO products_posted 
            (product_id, product_name, source, description, url, 
             posted_to_group_id, message_sent, posted_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            product.get('id', ''),
            product.get('product_name', ''),
            product.get('source', ''),
            product.get('description', '')[:500],
            product.get('url', ''),
            group_id,
            message[:5000],
            datetime.now()
        ))
        self.commit()
        return cursor.lastrowid
    
    def update_product_engagement(self, product_post_id: int, indicators: Dict):
        """Update product engagement indicators"""
        cursor = self.get_cursor()
        cursor.execute("""
            UPDATE products_posted 
            SET engagement_indicators = ?
            WHERE id = ?
        """, (json.dumps(indicators), product_post_id))
        self.commit()
    
    # ============================================================
    # TRENDING TOPICS
    # ============================================================
    
    def update_trending_topics(self, group_id: int, topics: List[str]):
        """Update trending topics for a group"""
        cursor = self.get_cursor()
        now = datetime.now()
        
        for topic in topics:
            clean_topic = topic.lower().strip()[:100]
            if len(clean_topic) < 3:
                continue
            
            cursor.execute("""
                INSERT INTO trending_topics (topic, group_id, mentions, first_mentioned, last_mentioned)
                VALUES (?, ?, 1, ?, ?)
                ON CONFLICT(topic, group_id) 
                DO UPDATE SET 
                    mentions = mentions + 1,
                    last_mentioned = ?
            """, (clean_topic, group_id, now, now, now))
        
        self.commit()
    
    # ============================================================
    # ANALYTICS QUERIES
    # ============================================================
    
    def get_most_active_groups(self, limit: int = 10) -> List[Dict]:
        """Get most active groups"""
        cursor = self.get_cursor()
        cursor.execute("""
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
        
        columns = [description[0] for description in cursor.description]
        return [dict(zip(columns, row)) for row in cursor.fetchall()]
    
    def get_most_active_times(self) -> List[Dict]:
        """Get most active times and days"""
        cursor = self.get_cursor()
        cursor.execute("""
            SELECT 
                hour,
                date,
                SUM(message_count) as total_messages,
                COUNT(DISTINCT group_id) as groups_active
            FROM daily_activity
            GROUP BY hour, date
            ORDER BY total_messages DESC
            LIMIT 20
        """)
        
        columns = [description[0] for description in cursor.description]
        return [dict(zip(columns, row)) for row in cursor.fetchall()]
    
    def get_most_popular_words(self, limit: int = 20) -> List[Dict]:
        """Get most popular words overall"""
        cursor = self.get_cursor()
        cursor.execute("""
            SELECT 
                word,
                SUM(frequency) as total_frequency,
                COUNT(DISTINCT group_id) as groups_mentioned
            FROM word_frequency
            GROUP BY word
            ORDER BY total_frequency DESC
            LIMIT ?
        """, (limit,))
        
        columns = [description[0] for description in cursor.description]
        return [dict(zip(columns, row)) for row in cursor.fetchall()]
    
    def get_most_popular_products(self, limit: int = 10) -> List[Dict]:
        """Get most popular products posted"""
        cursor = self.get_cursor()
        cursor.execute("""
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
        
        columns = [description[0] for description in cursor.description]
        return [dict(zip(columns, row)) for row in cursor.fetchall()]
    
    def get_trending_topics(self, days: int = 7, limit: int = 15) -> List[Dict]:
        """Get trending topics from the last N days"""
        cursor = self.get_cursor()
        cutoff_date = datetime.now() - timedelta(days=days)
        
        cursor.execute("""
            SELECT 
                topic,
                SUM(mentions) as total_mentions,
                COUNT(DISTINCT group_id) as groups_mentioned,
                MIN(first_mentioned) as first_seen,
                MAX(last_mentioned) as last_seen
            FROM trending_topics
            WHERE last_mentioned >= ?
            GROUP BY topic
            ORDER BY total_mentions DESC
            LIMIT ?
        """, (cutoff_date, limit))
        
        columns = [description[0] for description in cursor.description]
        return [dict(zip(columns, row)) for row in cursor.fetchall()]
    
    def get_group_analytics(self, group_name: str) -> Dict:
        """Get comprehensive analytics for a specific group"""
        cursor = self.get_cursor()
        
        # Get group ID
        cursor.execute("SELECT id FROM groups WHERE group_name = ?", (group_name,))
        result = cursor.fetchone()
        if not result:
            return {"error": "Group not found"}
        
        group_id = result[0]
        
        # Get general stats
        cursor.execute("""
            SELECT 
                COUNT(*) as total_messages,
                COUNT(DISTINCT sender_name) as unique_senders,
                SUM(CASE WHEN is_from_us = 1 THEN 1 ELSE 0 END) as messages_from_us,
                MIN(timestamp) as first_message,
                MAX(timestamp) as last_message
            FROM messages
            WHERE group_id = ?
        """, (group_id,))
        
        stats = dict(zip(
            ['total_messages', 'unique_senders', 'messages_from_us', 'first_message', 'last_message'],
            cursor.fetchone()
        ))
        
        # Get hourly activity
        cursor.execute("""
            SELECT 
                hour,
                SUM(message_count) as messages
            FROM daily_activity
            WHERE group_id = ?
            GROUP BY hour
            ORDER BY hour
        """, (group_id,))
        
        stats['hourly_activity'] = [dict(zip(['hour', 'messages'], row)) for row in cursor.fetchall()]
        
        # Get top words
        cursor.execute("""
            SELECT word, frequency
            FROM word_frequency
            WHERE group_id = ?
            ORDER BY frequency DESC
            LIMIT 10
        """, (group_id,))
        
        stats['top_words'] = [dict(zip(['word', 'frequency'], row)) for row in cursor.fetchall()]
        
        # Get products posted
        cursor.execute("""
            SELECT 
                product_name,
                COUNT(*) as post_count,
                MAX(posted_at) as last_posted
            FROM products_posted
            WHERE posted_to_group_id = ?
            GROUP BY product_name
            ORDER BY post_count DESC
            LIMIT 10
        """, (group_id,))
        
        stats['products_posted'] = [dict(zip(['product_name', 'post_count', 'last_posted'], row)) 
                                   for row in cursor.fetchall()]
        
        return stats
    
    def get_db_stats(self) -> Dict:
        """Get overall database statistics"""
        cursor = self.get_cursor()
        
        stats = {}
        
        cursor.execute("SELECT COUNT(*) FROM groups")
        stats['total_groups'] = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM messages")
        stats['total_messages'] = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM products_posted")
        stats['total_products_posted'] = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM word_frequency")
        stats['unique_words'] = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM trending_topics")
        stats['trending_topics'] = cursor.fetchone()[0]
        
        # Get date range
        cursor.execute("SELECT MIN(timestamp), MAX(timestamp) FROM messages")
        min_time, max_time = cursor.fetchone()
        stats['first_message_date'] = min_time
        stats['last_message_date'] = max_time
        
        return stats
    
    def generate_report(self) -> str:
        """Generate a comprehensive report"""
        report = []
        report.append("=" * 60)
        report.append("📊 WHATSAPP DATA ANALYTICS REPORT")
        report.append("=" * 60)
        report.append(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        report.append("")
        
        # Database stats
        stats = self.get_db_stats()
        report.append("📈 DATABASE STATISTICS")
        report.append("-" * 40)
        report.append(f"Total Groups Tracked: {stats['total_groups']}")
        report.append(f"Total Messages Collected: {stats['total_messages']}")
        report.append(f"Total Products Posted: {stats['total_products_posted']}")
        report.append(f"Unique Words Tracked: {stats['unique_words']}")
        report.append(f"Trending Topics Tracked: {stats['trending_topics']}")
        report.append(f"Data Range: {stats['first_message_date']} to {stats['last_message_date']}")
        report.append("")
        
        # Most active groups
        report.append("🏆 MOST ACTIVE GROUPS")
        report.append("-" * 40)
        active_groups = self.get_most_active_groups(5)
        for i, group in enumerate(active_groups, 1):
            report.append(f"{i}. {group['group_name']}")
            report.append(f"   Messages: {group['total_messages']}")
            report.append(f"   Unique Senders: {group['unique_senders']}")
            report.append(f"   Posts From Us: {group['total_posts_from_us']}")
        report.append("")
        
        # Most popular words
        report.append("🔤 MOST POPULAR WORDS")
        report.append("-" * 40)
        popular_words = self.get_most_popular_words(10)
        for i, word in enumerate(popular_words, 1):
            report.append(f"{i}. '{word['word']}' - {word['total_frequency']} mentions")
        report.append("")
        
        # Most popular products
        report.append("🛍️ MOST POPULAR PRODUCTS")
        report.append("-" * 40)
        popular_products = self.get_most_popular_products(5)
        for i, product in enumerate(popular_products, 1):
            report.append(f"{i}. {product['product_name']} ({product['source']})")
            report.append(f"   Posts: {product['total_posts']}, Groups: {product['groups_posted']}")
        report.append("")
        
        # Trending topics
        report.append("📰 TRENDING TOPICS")
        report.append("-" * 40)
        trending = self.get_trending_topics(7, 10)
        for i, topic in enumerate(trending, 1):
            report.append(f"{i}. '{topic['topic']}' - {topic['total_mentions']} mentions")
        report.append("")
        
        report.append("=" * 60)
        report.append("Report Generated by WhatsApp Data Collection System")
        report.append("=" * 60)
        
        return "\n".join(report)


# ============================================================
# FOR BACKWARD COMPATIBILITY - Keep old class name
# ============================================================

# This allows existing code that imports DatabaseManager to still work
# from db_logic import DatabaseManager