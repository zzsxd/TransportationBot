from telebot import TeleBot, types
from backend import Backend
from config_parser import ConfigParser
from typing import List, Dict, Any
import json
from datetime import datetime
import os

class Frontend:
    def __init__(self, bot: TeleBot):
        self.bot = bot
        self.backend = Backend()
        self.config = ConfigParser()
        self.admin_ids = self.config.get_admin_ids()
        
        self.user_states = {}
        self.temp_data = {}
    
    def is_admin(self, user_id: int, username: str) -> bool:
        return self.config.is_admin(user_id, username)
    
    def handle_start(self, message: types.Message):
        user_id = message.from_user.id
        username = message.from_user.username
        first_name = message.from_user.first_name
        last_name = message.from_user.last_name or ""
        
        self.backend.register_user(user_id, username, first_name, last_name)

        if self.is_admin(user_id, username):
            self.backend.db.execute(
                "UPDATE users SET role = 'admin' WHERE user_id = ?",
                (user_id,)
            )
            self._show_admin_menu(message)
        else:
            role = self.backend.get_user_role(user_id)
            
            if role == 'driver':
                self._show_driver_menu(message)
            else:
                self.bot.send_message(
                    message.chat.id,
                    "🚫 Вы не зарегистрированы в системе. Обратитесь к администратору."
                )
    
    def _show_admin_menu(self, message: types.Message):
        markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
        markup.add("📊 Экспорт в Excel")
        markup.add("🚚 Добавить водителя", "🗑️ Удалить водителя")
        markup.add("📨 Создать рассылку", "📋 Список водителей")
        
        self.bot.send_message(
            message.chat.id,
            "👑 Панель администратора\n\n"
            "Выберите действие:",
            reply_markup=markup
        )
    
    def _show_driver_menu(self, message: types.Message):
        markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
        markup.add("📋 Мои заказы")
        
        self.bot.send_message(
            message.chat.id,
            "🚚 Панель водителя\n\n"
            "Доступные команды:\n"
            "/my_orders - история заказов",
            reply_markup=markup
        )
    
    def handle_admin_commands(self, message: types.Message):
        user_id = message.from_user.id
        username = message.from_user.username
        
        if not self.is_admin(user_id, username):
            self.bot.send_message(message.chat.id, "🚫 У вас нет прав администратора")
            return
        
        if message.text == "📊 Экспорт в Excel":
            self._handle_export_excel(message)
        elif message.text == "🚚 Добавить водителя":
            self._start_add_driver(message)
        elif message.text == "📨 Создать рассылку":
            self._start_create_broadcast(message)
        elif message.text == "📋 Список водителей":
            self._handle_export_drivers(message)
        elif message.text == "🗑️ Удалить водителя":
            self._start_remove_driver(message)
    
    def _handle_export_users(self, message: types.Message):
        users_data = self.backend.export_users()
        if len(users_data) > 4096:
            for x in range(0, len(users_data), 4096):
                self.bot.send_message(message.chat.id, users_data[x:x+4096])
        else:
            self.bot.send_message(message.chat.id, users_data)
    
    def _handle_export_excel(self, message: types.Message):
        markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
        markup.add("📊 Пользователи Excel", "🚚 Водители Excel")
        markup.add("⬅️ Назад")
        
        self.bot.send_message(
            message.chat.id,
            "Выберите что экспортировать в Excel:",
            reply_markup=markup
        )
    
    def handle_export_excel_choice(self, message: types.Message):
        user_id = message.from_user.id
        username = message.from_user.username
        
        if not self.is_admin(user_id, username):
            self.bot.send_message(message.chat.id, "🚫 У вас нет прав администратора")
            return
        
        if message.text == "📊 Пользователи Excel":
            self._export_users_excel(message)
        elif message.text == "🚚 Водители Excel":
            self._export_drivers_excel(message)
        elif message.text == "⬅️ Назад":
            self._show_admin_menu(message)
    
    def _export_users_excel(self, message: types.Message):
        try:
            filepath = self.backend.export_users_excel()
            if not filepath:
                self.bot.send_message(message.chat.id, "❌ Нет пользователей для экспорта")
                return
            
            with open(filepath, 'rb') as file:
                self.bot.send_document(
                    message.chat.id,
                    file,
                    caption="📊 Экспорт пользователей"
                )
            
            os.remove(filepath)
            
        except Exception as e:
            self.bot.send_message(message.chat.id, f"❌ Ошибка при экспорте: {str(e)}")
    
    def _export_drivers_excel(self, message: types.Message):
        try:
            filepath = self.backend.export_drivers_excel()
            if not filepath:
                self.bot.send_message(message.chat.id, "❌ Нет водителей для экспорта")
                return
            
            with open(filepath, 'rb') as file:
                self.bot.send_document(
                    message.chat.id,
                    file,
                    caption="🚚 Экспорт водителей"
                )
            
            os.remove(filepath)
            
        except Exception as e:
            self.bot.send_message(message.chat.id, f"❌ Ошибка при экспорте: {str(e)}")
    
    def _handle_export_drivers(self, message: types.Message):
        drivers_data = self.backend.export_drivers()
        if len(drivers_data) > 4096:
            for x in range(0, len(drivers_data), 4096):
                self.bot.send_message(message.chat.id, drivers_data[x:x+4096])
        else:
            self.bot.send_message(message.chat.id, drivers_data)
    
    def _start_add_driver(self, message: types.Message):
        user_id = message.from_user.id
        username = message.from_user.username
        
        if not self.is_admin(user_id, username):
            self.bot.send_message(message.chat.id, "🚫 У вас нет прав администратора")
            return
        
        self.user_states[message.from_user.id] = 'awaiting_driver_username'
        self.bot.send_message(
            message.chat.id,
            "Введите username водителя (без @):"
        )
    
    def _start_remove_driver(self, message: types.Message):
        user_id = message.from_user.id
        username = message.from_user.username
        
        if not self.is_admin(user_id, username):
            self.bot.send_message(message.chat.id, "🚫 У вас нет прав администратора")
            return
        
        drivers = self.backend.get_all_drivers()
        
        if not drivers:
            self.bot.send_message(message.chat.id, "🚫 Нет водителей для удаления")
            return
        
        markup = types.InlineKeyboardMarkup()
        for driver in drivers:
            markup.add(types.InlineKeyboardButton(
                f"🗑️ {driver['full_name']} (@{driver['username']})",
                callback_data=f"remove_driver_{driver['username']}"
            ))
        
        self.bot.send_message(
            message.chat.id,
            "Выберите водителя для удаления:",
            reply_markup=markup
        )
    
    def handle_remove_driver(self, call: types.CallbackQuery):
        user_id = call.from_user.id
        username = call.from_user.username
        
        if not self.is_admin(user_id, username):
            self.bot.answer_callback_query(call.id, "🚫 У вас нет прав администратора")
            return
        
        driver_username = call.data.split('_')[2]
        
        success = self.backend.remove_driver(driver_username)
        
        if success:
            self.bot.answer_callback_query(call.id, "✅ Водитель успешно удален")
            self.bot.edit_message_text(
                "✅ Водитель успешно удален",
                call.message.chat.id,
                call.message.message_id
            )
        else:
            self.bot.answer_callback_query(call.id, "❌ Водитель не найден")
            self.bot.edit_message_text(
                "❌ Водитель не найден",
                call.message.chat.id,
                call.message.message_id
            )
    
    def handle_driver_registration(self, message: types.Message):
        user_id = message.from_user.id
        username = message.from_user.username
        
        if not self.is_admin(user_id, username):
            self.bot.send_message(message.chat.id, "🚫 У вас нет прав администратора")
            if user_id in self.user_states:
                del self.user_states[user_id]
            if user_id in self.temp_data:
                del self.temp_data[user_id]
            return
        
        state = self.user_states.get(user_id)
        
        if state == 'awaiting_driver_username':
            username_input = message.text.strip()
            if not username_input:
                self.bot.send_message(message.chat.id, "Пожалуйста, введите корректный username")
                return
            
            user = self.backend.db.fetch_one(
                "SELECT user_id FROM users WHERE username = ?", 
                (username_input,)
            )
            
            if not user:
                self.bot.send_message(
                    message.chat.id,
                    f"❌ Пользователь @{username_input} не найден. "
                    f"Пользователь должен сначала запустить бота командой /start"
                )
                return
            
            driver_user_id = user['user_id']
            self.temp_data[user_id] = {'username': username_input, 'driver_user_id': driver_user_id}
            self.user_states[user_id] = 'awaiting_driver_fullname'
            self.bot.send_message(message.chat.id, "Введите ФИО водителя:")
        
        elif state == 'awaiting_driver_fullname':
            full_name = message.text.strip()
            self.temp_data[user_id]['full_name'] = full_name
            self.user_states[user_id] = 'awaiting_driver_phone'
            self.bot.send_message(message.chat.id, "Введите номер телефона водителя:")
        
        elif state == 'awaiting_driver_phone':
            phone = message.text.strip()
            self.temp_data[user_id]['phone'] = phone
            self.user_states[user_id] = 'awaiting_driver_group'
            
            markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
            markup.add("3 тонны", "5 тонн", "5+ тонн")
            
            self.bot.send_message(
                message.chat.id,
                "Выберите группу водителя:",
                reply_markup=markup
            )
        
        elif state == 'awaiting_driver_group':
            group_text = message.text.strip()
            group_mapping = {
                '3 тонны': '3_ton',
                '5 тонн': '5_ton',
                '5+ тонн': '5+_ton'
            }
            
            group_type = group_mapping.get(group_text)
            if not group_type:
                self.bot.send_message(message.chat.id, "Пожалуйста, выберите группу из предложенных вариантов")
                return
            
            data = self.temp_data.get(user_id, {})
            driver_user_id = data.get('driver_user_id')
            full_name = data.get('full_name')
            phone = data.get('phone')
            
            try:
                self.backend.register_driver(driver_user_id, full_name, phone, group_type)
                
                del self.user_states[user_id]
                del self.temp_data[user_id]
                
                markup = types.ReplyKeyboardRemove()
                self.bot.send_message(
                    message.chat.id,
                    f"✅ Водитель {full_name} успешно добавлен в группу '{group_text}'",
                    reply_markup=markup
                )
                self._show_admin_menu(message)
                
            except Exception as e:
                self.bot.send_message(message.chat.id, f"❌ Ошибка при добавлении водителя: {str(e)}")
    
    def _start_create_broadcast(self, message: types.Message):
        user_id = message.from_user.id
        username = message.from_user.username
        
        if not self.is_admin(user_id, username):
            self.bot.send_message(message.chat.id, "🚫 У вас нет прав администратора")
            return
        
        self.user_states[message.from_user.id] = 'awaiting_broadcast_photos'
        self.temp_data[message.from_user.id] = {'photos': []}
        
        self.bot.send_message(
            message.chat.id,
            "Отправьте до 6 фотографий для рассылки (или отправьте /skip чтобы пропустить):"
        )
    
    def handle_broadcast_photos(self, message: types.Message):
        user_id = message.from_user.id
        username = message.from_user.username
        
        if not self.is_admin(user_id, username):
            self.bot.send_message(message.chat.id, "🚫 У вас нет прав администратора")
            if user_id in self.user_states:
                del self.user_states[user_id]
            if user_id in self.temp_data:
                del self.temp_data[user_id]
            return
        
        if self.user_states.get(user_id) == 'awaiting_broadcast_photos':
            if message.photo:
                photo_id = message.photo[-1].file_id
                data = self.temp_data.get(user_id, {})
                photos = data.get('photos', [])
                
                if len(photos) < 6:
                    photos.append(photo_id)
                    data['photos'] = photos
                    self.temp_data[user_id] = data
                    
                    if len(photos) < 6:
                        self.bot.send_message(message.chat.id, f"Фото добавлено. Можно отправить еще {6 - len(photos)} фото или перейти к тексту командой /next")
                    else:
                        self.bot.send_message(message.chat.id, "Максимальное количество фото достигнуто. Переходим к тексту командой /next")
                else:
                    self.bot.send_message(message.chat.id, "Достигнут лимит в 6 фото. Переходим к тексту командой /next")
            
            elif message.text == '/skip':
                self.user_states[user_id] = 'awaiting_broadcast_text'
                self.bot.send_message(message.chat.id, "Введите текст рассылки:")
            
            elif message.text == '/next':
                self.user_states[user_id] = 'awaiting_broadcast_text'
                self.bot.send_message(message.chat.id, "Введите текст рассылки:")
    
    def handle_broadcast_text(self, message: types.Message):
        user_id = message.from_user.id
        username = message.from_user.username
        
        if not self.is_admin(user_id, username):
            self.bot.send_message(message.chat.id, "🚫 У вас нет прав администратора")
            if user_id in self.user_states:
                del self.user_states[user_id]
            if user_id in self.temp_data:
                del self.temp_data[user_id]
            return
        
        if self.user_states.get(user_id) == 'awaiting_broadcast_text':
            text = message.text
            data = self.temp_data.get(user_id, {})
            data['text'] = text
            self.temp_data[user_id] = data
            self.user_states[user_id] = 'awaiting_broadcast_group'
            
            markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
            markup.add("3 тонны", "5 тонн", "5+ тонн", "Все группы")
            
            self.bot.send_message(
                message.chat.id,
                "Выберите группу для рассылки:",
                reply_markup=markup
            )
    
    def handle_broadcast_group(self, message: types.Message):
        user_id = message.from_user.id
        username = message.from_user.username
        
        if not self.is_admin(user_id, username):
            self.bot.send_message(message.chat.id, "🚫 У вас нет прав администратора")
            if user_id in self.user_states:
                del self.user_states[user_id]
            if user_id in self.temp_data:
                del self.temp_data[user_id]
            return
        
        if self.user_states.get(user_id) == 'awaiting_broadcast_group':
            group_text = message.text.strip()
            group_mapping = {
                '3 тонны': '3_ton',
                '5 тонн': '5_ton',
                '5+ тонн': '5+_ton',
                'Все группы': 'all'
            }
            
            group_type = group_mapping.get(group_text)
            if not group_type:
                self.bot.send_message(message.chat.id, "Пожалуйста, выберите группу из предложенных вариантов")
                return
            
            data = self.temp_data.get(user_id, {})
            text = data.get('text', '')
            photos = data.get('photos', [])
            
            order_id = self.backend.create_order(user_id, text, group_type, photos)
            
            self._send_broadcast(order_id, group_type, text, photos)
            
            del self.user_states[user_id]
            del self.temp_data[user_id]
            
            markup = types.ReplyKeyboardRemove()
            self.bot.send_message(
                message.chat.id,
                f"✅ Рассылка отправлена группе '{group_text}'",
                reply_markup=markup
            )
            self._show_admin_menu(message)
    
    def _send_broadcast(self, order_id: int, group_type: str, text: str, photos: List[str]):
        if group_type == 'all':
            groups = ['3_ton', '5_ton', '5+_ton']
        else:
            groups = [group_type]
        
        for group in groups:
            drivers = self.backend.get_drivers_by_group(group)
            for driver in drivers:
                try:
                    if photos:
                        media = [types.InputMediaPhoto(photo) for photo in photos]
                        media[0].caption = f"📦 Новый заказ #{order_id}:\n\n{text}"
                        self.bot.send_media_group(driver['user_id'], media)
                    else:
                        self.bot.send_message(driver['user_id'], f"📦 Новый заказ #{order_id}:\n\n{text}")
                    
                    markup = types.InlineKeyboardMarkup()
                    markup.add(types.InlineKeyboardButton(
                        "✅ Взять заказ",
                        callback_data=f"accept_order_{order_id}"
                    ))
                    
                    self.bot.send_message(
                        driver['user_id'],
                        "Нажмите кнопку чтобы взять заказ:",
                        reply_markup=markup
                    )
                    
                except Exception as e:
                    print(f"Ошибка при отправке рассылки водителю {driver['user_id']}: {e}")
    
    def handle_order_accept(self, call: types.CallbackQuery):
        driver_id = call.from_user.id
        order_id = int(call.data.split('_')[2])
        
        driver = self.backend.get_driver_info(driver_id)
        if not driver:
            self.bot.answer_callback_query(call.id, "❌ Вы не являетесь водителем")
            return
        
        if self.backend.is_order_taken(order_id):
            self.bot.answer_callback_query(
                call.id, 
                "❌ Этот заказ уже взят другим водителем",
                show_alert=True
            )
            self.bot.edit_message_reply_markup(
                call.message.chat.id,
                call.message.message_id,
                reply_markup=None
            )
            self.bot.send_message(
                call.message.chat.id,
                "❌ К сожалению, этот заказ уже взят другим водителем"
            )
            return
        
        success = self.backend.accept_order(order_id, driver_id)
        
        if not success:
            self.bot.answer_callback_query(
                call.id, 
                "❌ Этот заказ уже взят другим водителем",
                show_alert=True
            )
            self.bot.edit_message_reply_markup(
                call.message.chat.id,
                call.message.message_id,
                reply_markup=None
            )
            self.bot.send_message(
                call.message.chat.id,
                "❌ К сожалению, этот заказ уже взят другим водителем"
            )
            return
        
        try:
            order = self.backend.get_order_info(order_id)
            if order:
                admin_id = order['admin_id']
                message_text = (
                    f"✅ Водитель принял заказ #{order_id}:\n\n"
                    f"Заказ: {order['description'][:100]}...\n"
                    f"Водитель: {driver['full_name']}\n"
                    f"Телефон: {driver['phone']}\n"
                    f"Username: @{driver['username']}\n"
                    f"Группа: {self._get_group_name(driver['group_type'])}\n"
                    f"Время: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
                )
                
                self.bot.send_message(admin_id, message_text)
            
            self.bot.answer_callback_query(call.id, "✅ Заказ принят!")
            self.bot.edit_message_reply_markup(
                call.message.chat.id,
                call.message.message_id,
                reply_markup=None
            )
            self.bot.send_message(
                call.message.chat.id,
                "✅ Вы успешно приняли заказ!"
            )
            
        except Exception as e:
            self.bot.answer_callback_query(call.id, "❌ Ошибка при принятии заказа")
    
    def handle_my_orders(self, message: types.Message):
        driver_id = message.from_user.id
        orders = self.backend.get_driver_orders_history(driver_id)
        
        if not orders:
            self.bot.send_message(message.chat.id, "📭 У вас пока нет выполненных заказов")
            return
        
        response = "📋 История ваших заказов:\n\n"
        for i, order in enumerate(orders, 1):
            response += f"{i}. Заказ #{order['order_id']}\n"
            response += f"   Описание: {order['description'][:50]}...\n"
            response += f"   Принят: {order['accepted_at']}\n"
            response += "─" * 30 + "\n"
        
        self.bot.send_message(message.chat.id, response)
    
    def _get_group_name(self, group_type: str) -> str:
        group_names = {
            '3_ton': '3 тонны',
            '5_ton': '5 тонн',
            '5+_ton': '5+ тонн'
        }
        return group_names.get(group_type, group_type)