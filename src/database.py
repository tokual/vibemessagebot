import os
import sqlite3
from datetime import datetime, timedelta
from typing import Optional, Tuple
import logging
import asyncio

logger = logging.getLogger(__name__)

class DatabaseManager:
    def __init__(self, db_path: str):
        self.db_path = db_path
        self.init_database()
        self._request_times = []  # In-memory tracking for API rate limits
        self._lock = asyncio.Lock()
    
    def init_database(self):
        """Initialize database and create tables if they don't exist."""
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            
            # Create API rate limiting table (project-level)
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS api_requests (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TEXT,
                    success BOOLEAN
                )
            ''')
            
            # Create usage logs table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS usage_logs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER,
                    query TEXT,
                    response_length INTEGER,
                    timestamp TEXT,
                    success BOOLEAN
                )
            ''')
            
            # Create index for faster queries
            cursor.execute('''
                CREATE INDEX IF NOT EXISTS idx_api_requests_timestamp 
                ON api_requests(timestamp)
            ''')
            
            cursor.execute('''
                CREATE INDEX IF NOT EXISTS idx_usage_logs_user_timestamp 
                ON usage_logs(user_id, timestamp)
            ''')
            
            conn.commit()
    
    async def check_api_rate_limit(self, requests_per_minute: int, requests_per_day: int) -> Tuple[bool, str]:
        """Check if API rate limits are exceeded (project-level)."""
        async with self._lock:
            now = datetime.utcnow()
            minute_ago = now - timedelta(minutes=1)
            day_ago = now - timedelta(days=1)
            
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                # Check per-minute limit
                cursor.execute('''
                    SELECT COUNT(*) FROM api_requests 
                    WHERE timestamp > ? AND success = 1
                ''', (minute_ago.isoformat(),))
                
                minute_count = cursor.fetchone()[0]
                
                if minute_count >= requests_per_minute:
                    return False, f"API rate limit exceeded: {requests_per_minute} requests per minute. Please try again later."
                
                # Check per-day limit
                cursor.execute('''
                    SELECT COUNT(*) FROM api_requests 
                    WHERE timestamp > ? AND success = 1
                ''', (day_ago.isoformat(),))
                
                day_count = cursor.fetchone()[0]
                
                if day_count >= requests_per_day:
                    return False, f"Daily API limit exceeded: {requests_per_day} requests per day. Please try again tomorrow."
                
                return True, ""
    
    async def record_api_request(self, success: bool = True):
        """Record an API request for rate limiting."""
        async with self._lock:
            now = datetime.utcnow()
            
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    INSERT INTO api_requests (timestamp, success) 
                    VALUES (?, ?)
                ''', (now.isoformat(), success))
                conn.commit()
    
    def log_usage(self, user_id: int, query: str, response_length: int, success: bool):
        """Log usage for analytics."""
        now = datetime.utcnow()
        
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO usage_logs (user_id, query, response_length, timestamp, success) 
                VALUES (?, ?, ?, ?, ?)
            ''', (user_id, query, response_length, now.isoformat(), success))
            conn.commit()
    
    def cleanup_old_records(self, days_to_keep: int = 30):
        """Clean up old records to keep database size manageable."""
        cutoff_date = datetime.utcnow() - timedelta(days=days_to_keep)
        
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            
            # Clean up API request records (keep shorter period for rate limiting)
            api_cutoff = datetime.utcnow() - timedelta(days=7)  # Keep 1 week for rate limiting
            cursor.execute('''
                DELETE FROM api_requests 
                WHERE timestamp < ?
            ''', (api_cutoff.isoformat(),))
            
            # Clean up usage logs (keep them longer, maybe 90 days)
            usage_cutoff = datetime.utcnow() - timedelta(days=90)
            cursor.execute('''
                DELETE FROM usage_logs 
                WHERE timestamp < ?
            ''', (usage_cutoff.isoformat(),))
            
            conn.commit()
            
            logger.info(f"Cleaned up records older than {days_to_keep} days")
