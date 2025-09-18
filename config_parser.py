import json
import os
from typing import List, Optional

class ConfigParser:
    def __init__(self, config_file='secrets.json'):
        self.config_file = config_file
        self.config = self._load_config()
    
    def _load_config(self):
        if not os.path.exists(self.config_file):
            raise FileNotFoundError(f"Config file {self.config_file} not found")
        
        with open(self.config_file, 'r', encoding='utf-8') as f:
            return json.load(f)
    
    def get_bot_token(self) -> Optional[str]:
        return self.config.get('bot_token')
    
    def get_admin_ids(self) -> List[int]:
        return self.config.get('admin_ids', [])
    
    def get_admin_usernames(self) -> List[str]:
        return self.config.get('admin_usernames', [])
    
    def get_group_id(self) -> Optional[int]:
        group_id = self.config.get('group_id')
        if isinstance(group_id, str):
            try:
                return int(group_id)
            except ValueError:
                return None
        return group_id
    
    def is_admin(self, user_id: int, username: str) -> bool:
        username = username.lower() if username else ""
        return (user_id in self.get_admin_ids() or 
                username in [u.lower() for u in self.get_admin_usernames()])