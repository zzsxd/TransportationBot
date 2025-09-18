import sqlite3
import json
from datetime import datetime
from typing import List, Dict, Any, Optional

class Database:
    def __init__(self, db_name='db.sqlite3'):
        self.db_name = db_name
        self._init_db()
    
    def _init_db(self):
        with sqlite3.connect(self.db_name) as conn:
            cursor = conn.cursor()
            
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS users (
                    user_id INTEGER PRIMARY KEY,
                    username TEXT,
                    first_name TEXT,
                    last_name TEXT,
                    phone TEXT,
                    role TEXT DEFAULT 'user',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS groups (
                    group_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    group_name TEXT NOT NULL UNIQUE,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS drivers (
                    user_id INTEGER PRIMARY KEY,
                    full_name TEXT NOT NULL,
                    phone TEXT NOT NULL,
                    group_id INTEGER,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (user_id) REFERENCES users (user_id),
                    FOREIGN KEY (group_id) REFERENCES groups (group_id)
                )
            ''')
            
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS orders (
                    order_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    admin_id INTEGER NOT NULL,
                    description TEXT NOT NULL,
                    group_id INTEGER,
                    photos TEXT,
                    topic_name TEXT,
                    topic_id INTEGER,  -- ID топика в группе
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (admin_id) REFERENCES users (user_id),
                    FOREIGN KEY (group_id) REFERENCES groups (group_id)
                )
            ''')
            
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS driver_offers (
                    offer_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    order_id INTEGER NOT NULL,
                    driver_id INTEGER NOT NULL,
                    price REAL NOT NULL,
                    comment TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (order_id) REFERENCES orders (order_id),
                    FOREIGN KEY (driver_id) REFERENCES drivers (user_id)
                )
            ''')
            
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS order_responses (
                    response_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    order_id INTEGER NOT NULL,
                    driver_id INTEGER NOT NULL,
                    accepted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (order_id) REFERENCES orders (order_id),
                    FOREIGN KEY (driver_id) REFERENCES drivers (user_id),
                    UNIQUE(order_id, driver_id)
                )
            ''')
            
            conn.commit()
    
    def execute(self, query: str, params: tuple = ()) -> sqlite3.Cursor:
        with sqlite3.connect(self.db_name) as conn:
            cursor = conn.cursor()
            cursor.execute(query, params)
            conn.commit()
            return cursor
    
    def fetch_one(self, query: str, params: tuple = ()) -> Optional[Dict]:
        with sqlite3.connect(self.db_name) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute(query, params)
            result = cursor.fetchone()
            return dict(result) if result else None
    
    def fetch_all(self, query: str, params: tuple = ()) -> List[Dict]:
        with sqlite3.connect(self.db_name) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute(query, params)
            return [dict(row) for row in cursor.fetchall()]
    
    def add_user(self, user_id: int, username: str, first_name: str, last_name: str, phone: str = None, role: str = 'user'):
        self.execute(
            "INSERT OR REPLACE INTO users (user_id, username, first_name, last_name, phone, role) VALUES (?, ?, ?, ?, ?, ?)",
            (user_id, username, first_name, last_name, phone, role)
        )
    
    def update_user_phone(self, user_id: int, phone: str):
        self.execute(
            "UPDATE users SET phone = ? WHERE user_id = ?",
            (phone, user_id)
        )
    
    def get_user(self, user_id: int) -> Optional[Dict]:
        return self.fetch_one("SELECT * FROM users WHERE user_id = ?", (user_id,))
    
    def get_all_users(self) -> List[Dict]:
        return self.fetch_all("SELECT * FROM users")
    
    def add_driver(self, user_id: int, full_name: str, phone: str, group_id: int):
        user = self.get_user(user_id)
        if not user:
            pass
        
        self.execute(
            "INSERT OR REPLACE INTO drivers (user_id, full_name, phone, group_id) VALUES (?, ?, ?, ?)",
            (user_id, full_name, phone, group_id)
        )
        self.execute("UPDATE users SET role = 'driver' WHERE user_id = ?", (user_id,))
    
    def get_driver(self, user_id: int) -> Optional[Dict]:
        return self.fetch_one(
            "SELECT d.*, u.username FROM drivers d JOIN users u ON d.user_id = u.user_id WHERE d.user_id = ?",
            (user_id,)
        )
    
    def get_user_by_phone(self, phone: str) -> Optional[Dict]:
        return self.fetch_one("SELECT * FROM users WHERE phone = ?", (phone,))
    
    def get_all_drivers(self) -> List[Dict]:
        return self.fetch_all(
            "SELECT d.*, u.username FROM drivers d JOIN users u ON d.user_id = u.user_id"
        )

    def add_order(self, admin_id: int, description: str, group_id: int, photos: List[str], topic_name: str = None, topic_id: int = None) -> int:
        photos_json = json.dumps(photos)
        cursor = self.execute(
            "INSERT INTO orders (admin_id, description, group_id, photos, topic_name, topic_id) VALUES (?, ?, ?, ?, ?, ?)",
            (admin_id, description, group_id, photos_json, topic_name, topic_id)
        )
        return cursor.lastrowid
    
    def get_order(self, order_id: int) -> Optional[Dict]:
        order = self.fetch_one("SELECT * FROM orders WHERE order_id = ?", (order_id,))
        if order and order.get('photos'):
            order['photos'] = json.loads(order['photos'])
        return order
    
    def add_driver_offer(self, order_id: int, driver_id: int, price: float, comment: str = None):
        self.execute(
            "INSERT INTO driver_offers (order_id, driver_id, price, comment) VALUES (?, ?, ?, ?)",
            (order_id, driver_id, price, comment)
        )
    
    def get_order_offers(self, order_id: int) -> List[Dict]:
        return self.fetch_all(
            """SELECT o.*, d.full_name, d.phone, u.username 
               FROM driver_offers o 
               JOIN drivers d ON o.driver_id = d.user_id 
               JOIN users u ON d.user_id = u.user_id 
               WHERE o.order_id = ? ORDER BY o.created_at DESC""",
            (order_id,)
        )
    
    def accept_driver_offer(self, offer_id: int):
        # Получаем информацию о предложении
        offer = self.fetch_one("SELECT * FROM driver_offers WHERE offer_id = ?", (offer_id,))
        if not offer:
            return False
        
        # Добавляем водителя к заказу
        self.execute(
            "INSERT INTO order_responses (order_id, driver_id) VALUES (?, ?)",
            (offer['order_id'], offer['driver_id'])
        )
        
        # Удаляем остальные предложения для этого заказа
        self.execute(
            "DELETE FROM driver_offers WHERE order_id = ? AND offer_id != ?",
            (offer['order_id'], offer_id)
        )
        
        return True
    
    def get_order_responses(self, order_id: int) -> List[Dict]:
        return self.fetch_all(
            """SELECT r.*, d.full_name, d.phone, u.username 
               FROM order_responses r 
               JOIN drivers d ON r.driver_id = d.user_id 
               JOIN users u ON d.user_id = u.user_id 
               WHERE r.order_id = ?""",
            (order_id,)
        )
    
    def get_driver_orders(self, driver_id: int, limit: int = 10) -> List[Dict]:
        return self.fetch_all(
            """SELECT o.*, r.accepted_at 
               FROM orders o 
               JOIN order_responses r ON o.order_id = r.order_id 
               WHERE r.driver_id = ? 
               ORDER BY r.accepted_at DESC 
               LIMIT ?""",
            (driver_id, limit)
        )
    
    def add_group(self, group_name: str) -> int:
        cursor = self.execute(
            "INSERT INTO groups (group_name) VALUES (?)",
            (group_name,)
        )
        return cursor.lastrowid

    def get_group(self, group_id: int) -> Optional[Dict]:
        return self.fetch_one("SELECT * FROM groups WHERE group_id = ?", (group_id,))

    def get_group_by_name(self, group_name: str) -> Optional[Dict]:
        return self.fetch_one("SELECT * FROM groups WHERE group_name = ?", (group_name,))

    def get_all_groups(self) -> List[Dict]:
        return self.fetch_all("SELECT * FROM groups ORDER BY group_name")

    def delete_group(self, group_id: int):
        self.execute("DELETE FROM groups WHERE group_id = ?", (group_id,))

    def update_driver_group(self, user_id: int, group_id: int):
        self.execute(
            "UPDATE drivers SET group_id = ? WHERE user_id = ?",
            (group_id, user_id)
        )

    def get_drivers_by_group(self, group_id: int) -> List[Dict]:
        return self.fetch_all(
            "SELECT d.*, u.username FROM drivers d JOIN users u ON d.user_id = u.user_id WHERE d.group_id = ?",
            (group_id,)
        )