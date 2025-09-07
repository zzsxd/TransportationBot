import json

class ConfigParser:
    def __init__(self, config_file='secrets.json'):
        self.config_file = config_file
        self.config = self._load_config()
    
    def _load_config(self):
        try:
            with open(self.config_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        except FileNotFoundError:
            raise Exception(f"Config file {self.config_file} not found")
        except json.JSONDecodeError:
            raise Exception(f"Invalid JSON in config file {self.config_file}")
    
    def get_bot_token(self):
        return self.config.get('bot_token')
    
    def get_admin_ids(self):
        return self.config.get('admin_ids', [])
    
    def get_admin_usernames(self):
        return self.config.get('admin_usernames', [])
    
    def is_admin(self, user_id: int, username: str) -> bool:
        username = username.lower() if username else ""
        return (user_id in self.get_admin_ids() or 
                username in [u.lower() for u in self.get_admin_usernames()])