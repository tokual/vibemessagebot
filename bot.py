#!/usr/bin/env python3

import os
import sys
import logging
from datetime import datetime
from typing import Dict, List
import asyncio

# Add src directory to path
sys.path.append(os.path.join(os.path.dirname(__file__), 'src'))

from telegram import Update, InlineQuery, InlineQueryResultArticle, InputTextMessageContent
from telegram.ext import Application, InlineQueryHandler, ContextTypes
from telegram.constants import ParseMode
from dotenv import load_dotenv
import uuid

from database import DatabaseManager
from ai_service import AIService
from whitelist import WhitelistManager

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(
    level=getattr(logging, os.getenv('LOG_LEVEL', 'INFO')),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(os.getenv('LOG_FILE', './logs/bot.log')),
        logging.StreamHandler(sys.stdout)
    ]
)

logger = logging.getLogger(__name__)

class VibeMessageBot:
    def __init__(self):
        # Load configuration
        self.token = os.getenv('TELEGRAM_BOT_TOKEN')
        self.bot_username = os.getenv('BOT_USERNAME', 'vibemessagebot')
        self.google_ai_key = os.getenv('GOOGLE_AI_API_KEY')
        self.model_name = os.getenv('GOOGLE_AI_MODEL', 'gemini-2.0-flash-lite')
        
        # API Rate limiting (project-level)
        self.api_requests_per_minute = int(os.getenv('API_REQUESTS_PER_MINUTE', 10))
        self.api_requests_per_day = int(os.getenv('API_REQUESTS_PER_DAY', 1000))
        
        # Message configuration
        self.min_message_length = int(os.getenv('MIN_MESSAGE_LENGTH', 300))
        self.max_message_length = int(os.getenv('MAX_MESSAGE_LENGTH', 400))
        
        # Debouncing configuration
        self.debounce_delay = float(os.getenv('DEBOUNCE_DELAY_SECONDS', 2.0))
        self.pending_queries = {}  # Store pending queries for debouncing
        
        # Debouncing configuration
        self.debounce_delay = float(os.getenv('DEBOUNCE_DELAY_SECONDS', 2.0))
        
        # Database path
        self.db_path = os.getenv('DATABASE_PATH', './data/bot.db')
        
        # Whitelist configuration
        self.whitelist_enabled = os.getenv('WHITELIST_ENABLED', 'true').lower() == 'true'
        self.whitelist_path = os.getenv('WHITELIST_PATH', './data/whitelist.json')
        
        # Validate required environment variables
        if not self.token:
            raise ValueError("TELEGRAM_BOT_TOKEN is required")
        if not self.google_ai_key:
            raise ValueError("GOOGLE_AI_API_KEY is required")
        
        # Initialize services
        self.db = DatabaseManager(self.db_path)
        self.ai_service = AIService(self.google_ai_key, self.model_name)
        self.whitelist = WhitelistManager(self.whitelist_path) if self.whitelist_enabled else None
        
        # Debouncing: Track pending queries per user
        self.pending_queries = {}
        
        # Create application
        self.application = Application.builder().token(self.token).build()
        
        # Add handlers
        self.application.add_handler(InlineQueryHandler(self.handle_inline_query))
        
        # Add job queue for cleanup task
        self.application.job_queue.run_repeating(
            self.cleanup_job, interval=24*60*60, first=60  # Run every 24 hours, start after 1 minute
        )
        
        logger.info("VibeMessageBot initialized successfully")
    
    async def handle_inline_query(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle inline queries with debouncing."""
        query = update.inline_query
        user_id = query.from_user.id
        search_query = query.query.strip()
        query_id = query.id
        
        logger.info(f"Received inline query from user {user_id}: '{search_query}' (ID: {query_id})")
        
        # Cancel previous pending query for this user
        if user_id in self.pending_queries:
            old_task = self.pending_queries[user_id]
            if not old_task.done():
                old_task.cancel()
                logger.debug(f"Cancelled previous query for user {user_id}")
        
        # Create new debounced task
        task = asyncio.create_task(
            self._process_debounced_query(query, user_id, search_query, query_id)
        )
        self.pending_queries[user_id] = task
        
        try:
            await task
        except asyncio.CancelledError:
            logger.debug(f"Query cancelled for user {user_id}")
        except Exception as e:
            logger.error(f"Error in debounced query: {e}")
        finally:
            # Clean up completed task
            if user_id in self.pending_queries and self.pending_queries[user_id] == task:
                del self.pending_queries[user_id]
    
    async def _process_debounced_query(self, query, user_id: int, search_query: str, query_id: str):
        """Process query after debounce delay."""
        # Wait for debounce delay
        await asyncio.sleep(self.debounce_delay)
        
        logger.info(f"Processing debounced query from user {user_id}: '{search_query}'")
        
        # Check whitelist if enabled
        if self.whitelist_enabled and self.whitelist:
            if not self.whitelist.is_user_whitelisted(user_id):
                results = [
                    InlineQueryResultArticle(
                        id=str(uuid.uuid4()),
                        title="🚫 Access Denied",
                        description="You are not authorized to use this bot",
                        input_message_content=InputTextMessageContent(
                            message_text="Sorry, you are not authorized to use this bot. Please contact the administrator for access."
                        )
                    )
                ]
                await query.answer(results, cache_time=300)
                logger.warning(f"Unauthorized access attempt from user {user_id}")
                return
        
        # If query is empty, show help
        if not search_query:
            results = [
                InlineQueryResultArticle(
                    id=str(uuid.uuid4()),
                    title="💡 How to use VibeMessageBot",
                    description="Type a topic or message to generate content",
                    input_message_content=InputTextMessageContent(
                        message_text="Usage: @vibemessagebot <topic>\nExample: @vibemessagebot IPv6\nOr: @vibemessagebot I think IPv6 is great because..."
                    )
                )
            ]
            await query.answer(results, cache_time=300)
            return
        
        # Check API rate limits (project-level, not user-level)
        can_proceed, error_message = await self.db.check_api_rate_limit(
            self.api_requests_per_minute, self.api_requests_per_day
        )
        
        if not can_proceed:
            results = [
                InlineQueryResultArticle(
                    id=str(uuid.uuid4()),
                    title="⚠️ API Rate Limit Exceeded",
                    description=error_message,
                    input_message_content=InputTextMessageContent(
                        message_text=f"API rate limit exceeded. Please try again later.\n\n{error_message}"
                    )
                )
            ]
            await query.answer(results, cache_time=60)
            return
        
        # Check if topic is appropriate
        if not self.ai_service.is_appropriate_topic(search_query):
            results = [
                InlineQueryResultArticle(
                    id=str(uuid.uuid4()),
                    title="❌ Inappropriate Content",
                    description="This topic is not suitable for content generation",
                    input_message_content=InputTextMessageContent(
                        message_text="Sorry, I cannot generate content for this topic. Please try a different subject."
                    )
                )
            ]
            await query.answer(results, cache_time=300)
            return
        
        try:
            # Record the API request attempt
            await self.db.record_api_request(success=False)  # Start as failed, update on success
            
            # Generate message
            logger.info(f"Generating message for topic: '{search_query}'")
            generated_message = self.ai_service.generate_message(
                search_query, self.min_message_length, self.max_message_length
            )
            
            if generated_message:
                # Update to successful API request
                await self.db.record_api_request(success=True)
                
                # Log successful usage
                self.db.log_usage(user_id, search_query, len(generated_message), True)
                
                results = [
                    InlineQueryResultArticle(
                        id=str(uuid.uuid4()),
                        title="✨ Generated Message",
                        description=f"{generated_message[:100]}..." if len(generated_message) > 100 else generated_message,
                        input_message_content=InputTextMessageContent(
                            message_text=generated_message
                        )
                    )
                ]
                
                logger.info(f"Successfully generated message for user {user_id}")
            else:
                # Log failed usage
                self.db.log_usage(user_id, search_query, 0, False)
                
                results = [
                    InlineQueryResultArticle(
                        id=str(uuid.uuid4()),
                        title="❌ Generation Failed",
                        description="Unable to generate message. Please try again.",
                        input_message_content=InputTextMessageContent(
                            message_text="Sorry, I couldn't generate a message for that topic. Please try again with a different topic."
                        )
                    )
                ]
                
                logger.warning(f"Failed to generate message for user {user_id}")
            
        except Exception as e:
            logger.error(f"Error processing inline query: {str(e)}")
            
            # Log failed usage
            self.db.log_usage(user_id, search_query, 0, False)
            
            results = [
                InlineQueryResultArticle(
                    id=str(uuid.uuid4()),
                    title="❌ Error",
                    description="An error occurred. Please try again.",
                    input_message_content=InputTextMessageContent(
                        message_text="Sorry, an error occurred while processing your request. Please try again."
                    )
                )
            ]
        
        await query.answer(results, cache_time=30)
    
    async def cleanup_job(self, context: ContextTypes.DEFAULT_TYPE):
        """Periodic cleanup job."""
        try:
            # Clean up old database records
            self.db.cleanup_old_records()
            logger.info("Completed periodic database cleanup")
        except Exception as e:
            logger.error(f"Error in cleanup job: {str(e)}")
    
    async def cleanup_task(self):
        """Periodic cleanup task (legacy - replaced by cleanup_job)."""
        while True:
            try:
                # Wait 24 hours
                await asyncio.sleep(24 * 60 * 60)
                
                # Clean up old database records
                self.db.cleanup_old_records()
                logger.info("Completed periodic database cleanup")
                
            except Exception as e:
                logger.error(f"Error in cleanup task: {str(e)}")
    
    def run(self):
        """Run the bot."""
        logger.info("Starting VibeMessageBot...")
        
        # Run the bot with cleanup task
        self.application.run_polling(
            allowed_updates=Update.ALL_TYPES,
            drop_pending_updates=True
        )

def main():
    """Main entry point."""
    try:
        # Ensure directories exist
        os.makedirs('./data', exist_ok=True)
        os.makedirs('./logs', exist_ok=True)
        
        # Create and run bot
        bot = VibeMessageBot()
        bot.run()
        
    except KeyboardInterrupt:
        logger.info("Bot stopped by user")
    except Exception as e:
        logger.error(f"Fatal error: {str(e)}")
        sys.exit(1)

if __name__ == '__main__':
    main()
