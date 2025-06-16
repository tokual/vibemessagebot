import os
import json
import logging
from typing import Set, Optional
from datetime import datetime

logger = logging.getLogger(__name__)

class WhitelistManager:
    def __init__(self, whitelist_path: str):
        self.whitelist_path = whitelist_path
        self.whitelist_data = self._load_whitelist()
    
    def _load_whitelist(self) -> dict:
        """Load whitelist from JSON file."""
        try:
            if os.path.exists(self.whitelist_path):
                with open(self.whitelist_path, 'r') as f:
                    data = json.load(f)
                    # Ensure proper structure
                    if not isinstance(data, dict):
                        data = {"users": [], "last_updated": datetime.utcnow().isoformat()}
                    if "users" not in data:
                        data["users"] = []
                    if "last_updated" not in data:
                        data["last_updated"] = datetime.utcnow().isoformat()
                    return data
            else:
                # Create initial whitelist file
                initial_data = {
                    "users": [],
                    "last_updated": datetime.utcnow().isoformat(),
                    "description": "Whitelist for VibeMessageBot - Add user IDs to allow access"
                }
                self._save_whitelist(initial_data)
                return initial_data
        except Exception as e:
            logger.error(f"Error loading whitelist: {e}")
            return {"users": [], "last_updated": datetime.utcnow().isoformat()}
    
    def _save_whitelist(self, data: dict) -> bool:
        """Save whitelist to JSON file."""
        try:
            os.makedirs(os.path.dirname(self.whitelist_path), exist_ok=True)
            data["last_updated"] = datetime.utcnow().isoformat()
            with open(self.whitelist_path, 'w') as f:
                json.dump(data, f, indent=2)
            self.whitelist_data = data
            return True
        except Exception as e:
            logger.error(f"Error saving whitelist: {e}")
            return False
    
    def is_user_whitelisted(self, user_id: int) -> bool:
        """Check if user is in whitelist."""
        return user_id in self.whitelist_data.get("users", [])
    
    def add_user(self, user_id: int, username: Optional[str] = None) -> bool:
        """Add user to whitelist."""
        if user_id not in self.whitelist_data["users"]:
            self.whitelist_data["users"].append(user_id)
            # Store user info for reference (optional)
            if "user_info" not in self.whitelist_data:
                self.whitelist_data["user_info"] = {}
            if username:
                self.whitelist_data["user_info"][str(user_id)] = {
                    "username": username,
                    "added_at": datetime.utcnow().isoformat()
                }
            return self._save_whitelist(self.whitelist_data)
        return True
    
    def remove_user(self, user_id: int) -> bool:
        """Remove user from whitelist."""
        if user_id in self.whitelist_data["users"]:
            self.whitelist_data["users"].remove(user_id)
            # Remove user info if exists
            if "user_info" in self.whitelist_data and str(user_id) in self.whitelist_data["user_info"]:
                del self.whitelist_data["user_info"][str(user_id)]
            return self._save_whitelist(self.whitelist_data)
        return True
    
    def get_whitelisted_users(self) -> list:
        """Get list of whitelisted users."""
        return self.whitelist_data.get("users", [])
    
    def get_user_count(self) -> int:
        """Get number of whitelisted users."""
        return len(self.whitelist_data.get("users", []))
    
    def reload_whitelist(self):
        """Reload whitelist from file."""
        self.whitelist_data = self._load_whitelist()
        logger.info("Whitelist reloaded from file")
