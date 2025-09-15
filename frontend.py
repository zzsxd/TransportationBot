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
            user = self.backend.db.get_user(user_id)
            if user and user.get('phone'):
                role = self.backend.get_user_role(user_id)
                if role == 'driver':
                    self._show_driver_menu(message)
                else:
                    self.bot.send_message(
                        message.chat.id,
                        "✅ Ваш номер телефона сохранен. Ожидайте регистрации администратором."
                    )
            else:
                self._request_contact(message)
    
    def _request_contact(self, message: types.Message):
        markup = types.ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
        contact_btn = types.KeyboardButton("📱 Отправить контакт", request_contact=True)
        markup.add(contact_btn)
        
        self.bot.send_message(
            message.chat.id,
            "👋 Добро пожаловать! Для работы в системе необходимо предоставить ваш номер телефона.\n\n"
            "Нажмите кнопку ниже чтобы отправить контакт:",
            reply_markup=markup
        )

    def handle_contact(self, message: types.Message):
        user_id = message.from_user.id
        username = message.from_user.username
        
        if message.contact:
            phone_number = message.contact.phone_number
            
            self.backend.update_user_phone(user_id, phone_number)
            
            driver_info = self.backend.get_driver_info(user_id)
            if driver_info:
                self.backend.db.execute(
                    "UPDATE drivers SET phone = ? WHERE user_id = ?",
                    (phone_number, user_id)
                )
                
                markup = types.ReplyKeyboardRemove()
                self.bot.send_message(
                    message.chat.id,
                    f"✅ Ваш номер телефона {phone_number} успешно сохранен!",
                    reply_markup=markup
                )
                self._show_driver_menu(message)
            else:
                markup = types.ReplyKeyboardRemove()
                self.bot.send_message(
                    message.chat.id,
                    f"✅ Ваш номер {phone_number} сохранен. Ожидайте регистрации администратором.",
                    reply_markup=markup
                )
        else:
            self.bot.send_message(
                message.chat.id,
                "Пожалуйста, отправьте ваш контакт используя кнопку."
            )

    def _show_admin_menu(self, message: types.Message):
        markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
        markup.add("📊 Экспорт в Excel")
        markup.add("🚚 Добавить водителя", "🗑️ Удалить водителя")
        markup.add("👥 Управление группами", "📋 Список водителей")
        markup.add("📨 Создать рассылку")
        
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
        elif message.text == "👥 Управление группами":
            self._handle_group_management(message)
        elif message.text == "➕ Добавить группу":
            self._start_add_group(message)
        elif message.text == "➖ Удалить группу":
            self._handle_remove_group(message)
        elif message.text == "📋 Список групп":
            self._handle_list_groups(message)
        elif message.text == "⬅️ Назад":
            self._show_admin_menu(message)
    
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
    
    def _handle_group_management(self, message: types.Message):
        markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
        markup.add("➕ Добавить группу", "➖ Удалить группу")
        markup.add("📋 Список групп", "⬅️ Назад")
        
        self.bot.send_message(
            message.chat.id,
            "👥 Управление группами водителей\n\n"
            "Выберите действие:",
            reply_markup=markup
        )

    def _start_add_group(self, message: types.Message):
        user_id = message.from_user.id
        username = message.from_user.username
        
        if not self.is_admin(user_id, username):
            self.bot.send_message(message.chat.id, "🚫 У вас нет прав администратора")
            return
        
        self.user_states[user_id] = 'awaiting_group_name'
        self.bot.send_message(
            message.chat.id,
            "Введите название новой группы:",
            reply_markup=types.ReplyKeyboardRemove()
        )

    def _handle_group_name(self, message: types.Message):
        user_id = message.from_user.id
        group_name = message.text.strip()
        
        if not group_name:
            self.bot.send_message(message.chat.id, "❌ Название группы не может быть пустым")
            return
        
        existing_group = self.backend.get_group_by_name(group_name)
        if existing_group:
            self.bot.send_message(message.chat.id, "❌ Группа с таким названием уже существует")
            return
        
        try:
            group_id = self.backend.add_group(group_name)
            self.user_states[user_id] = None
            
            markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
            markup.add("👥 Управление группами", "⬅️ Назад")
            
            self.bot.send_message(
                message.chat.id,
                f"✅ Группа '{group_name}' успешно создана!",
                reply_markup=markup
            )
        except Exception as e:
            self.bot.send_message(message.chat.id, f"❌ Ошибка при создании группы: {str(e)}")

    def handle_remove_group(self, call: types.CallbackQuery):
        user_id = call.from_user.id
        username = call.from_user.username
        
        if not self.is_admin(user_id, username):
            self.bot.answer_callback_query(call.id, "🚫 У вас нет прав администратора")
            return
        
        group_id = int(call.data.split('_')[2])
        
        try:
            group = self.backend.db.get_group(group_id)
            if not group:
                self.bot.answer_callback_query(call.id, "❌ Группа не найдена")
                return
            
            self.backend.delete_group(group_id)
            
            self.bot.answer_callback_query(call.id, f"✅ Группа '{group['group_name']}' успешно удалена")
            self.bot.edit_message_text(
                f"✅ Группа '{group['group_name']}' успешно удалена",
                call.message.chat.id,
                call.message.message_id
            )
        except Exception as e:
            self.bot.answer_callback_query(call.id, "❌ Ошибка при удалении группы")
            self.bot.edit_message_text(
                "❌ Ошибка при удалении группы",
                call.message.chat.id,
                call.message.message_id
            )

    def _handle_list_groups(self, message: types.Message):
        user_id = message.from_user.id
        username = message.from_user.username
        
        if not self.is_admin(user_id, username):
            self.bot.send_message(message.chat.id, "🚫 У вас нет прав администратора")
            return
        
        groups = self.backend.get_all_groups()
        
        if not groups:
            self.bot.send_message(message.chat.id, "❌ Нет созданных групп")
            return
        
        groups_list = "📋 Список групп:\n\n"
        for group in groups:
            drivers_count = len(self.backend.get_drivers_by_group(group['group_id']))
            groups_list += f"🏷️ {group['group_name']}: {drivers_count} водителей\n"
        
        self.bot.send_message(message.chat.id, groups_list)

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

    def _handle_group_remove_confirmation(self, message: types.Message):
        user_id = message.from_user.id
        group_name = message.text.replace("❌ ", "").strip()
        
        group = self.backend.get_group_by_name(group_name)
        if not group:
            self.bot.send_message(message.chat.id, "❌ Группа не найдена")
            return
        
        try:
            self.backend.delete_group(group['group_id'])
            self.user_states[user_id] = None
            
            markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
            markup.add("👥 Управление группами", "⬅️ Назад")
            
            self.bot.send_message(
                message.chat.id,
                f"✅ Группа '{group_name}' успешно удалена!",
                reply_markup=markup
            )
        except Exception as e:
            self.bot.send_message(message.chat.id, f"❌ Ошибка при удалении группы: {str(e)}")
    
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
        
        self.user_states[user_id] = 'awaiting_driver_phone'
        self.bot.send_message(
            message.chat.id,
            "Введите номер телефона водителя (в формате 79991234567):",
            reply_markup=types.ReplyKeyboardRemove()
        )

    def _handle_add_driver_method(self, message: types.Message):
        user_id = message.from_user.id
        username = message.from_user.username
        
        if not self.is_admin(user_id, username):
            self.bot.send_message(message.chat.id, "🚫 У вас нет прав администратора")
            return
        
        if message.text == "📱 По номеру телефона":
            self.user_states[user_id] = 'awaiting_driver_phone'
            self.bot.send_message(
                message.chat.id,
                "Введите номер телефона водителя:",
                reply_markup=types.ReplyKeyboardRemove()
            )
        elif message.text == "👤 По username":
            self.user_states[user_id] = 'awaiting_driver_username'
            self.bot.send_message(
                message.chat.id,
                "Введите username водителя (без @):",
                reply_markup=types.ReplyKeyboardRemove()
            )
        elif message.text == "⬅️ Назад":
            self._show_admin_menu(message)
    
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
        
        if state == 'awaiting_driver_phone':
            phone = message.text.strip()
            
            if not self._is_valid_phone(phone):
                self.bot.send_message(message.chat.id, "❌ Неверный формат номера телефона")
                return
            
            user = self.backend.get_user_by_phone(phone)
            
            if not user:
                self.bot.send_message(
                    message.chat.id,
                    f"❌ Пользователь с номером {phone} не найден. "
                    f"Пользователь должен сначала запустить бота и отправить свой контакт"
                )
                return
            
            self.temp_data[user_id] = {
                'phone': phone, 
                'driver_user_id': user['user_id'],
                'username': user['username']
            }
            self.user_states[user_id] = 'awaiting_driver_fullname'
            self.bot.send_message(message.chat.id, "Введите ФИО водителя:")
        
        elif state == 'awaiting_driver_fullname':
            full_name = message.text.strip()
            self.temp_data[user_id]['full_name'] = full_name
            self.user_states[user_id] = 'awaiting_driver_group'
            
            groups = self.backend.get_all_groups()
            
            if not groups:
                self.bot.send_message(
                    message.chat.id,
                    "❌ Нет созданных групп. Сначала создайте группы через меню '👥 Управление группами'"
                )
                self._show_admin_menu(message)
                del self.user_states[user_id]
                del self.temp_data[user_id]
                return
            
            markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
            for group in groups:
                markup.add(group['group_name'])
            
            self.bot.send_message(
                message.chat.id,
                "Выберите группу водителя:",
                reply_markup=markup
            )
        
        elif state == 'awaiting_driver_group':
            group_name = message.text.strip()
                   
            group = self.backend.get_group_by_name(group_name)
            if not group:
                self.bot.send_message(
                    message.chat.id,
                    "❌ Группа не найдена. Выберите группу из предложенных вариантов"
                )
                return
            
            data = self.temp_data.get(user_id, {})
            driver_user_id = data.get('driver_user_id')
            full_name = data.get('full_name')
            phone = data.get('phone')
            
            try:
                self.backend.register_driver(driver_user_id, full_name, phone, group['group_id'])
                
                del self.user_states[user_id]
                del self.temp_data[user_id]
                
                markup = types.ReplyKeyboardRemove()
                self.bot.send_message(
                    message.chat.id,
                    f"✅ Водитель {full_name} успешно добавлен в группу '{group_name}'\n"
                    f"Username: @{data.get('username', 'неизвестно')}\n"
                    f"Телефон: {phone}",
                    reply_markup=markup
                )
                self._show_admin_menu(message)
                
            except Exception as e:
                self.bot.send_message(message.chat.id, f"❌ Ошибка при добавлении водителя: {str(e)}")

    def _is_valid_phone(self, phone: str) -> bool:
        cleaned_phone = ''.join(filter(str.isdigit, phone))
        return len(cleaned_phone) >= 10
    
    def _start_create_broadcast(self, message: types.Message):
        user_id = message.from_user.id
        username = message.from_user.username
        
        if not self.is_admin(user_id, username):
            self.bot.send_message(message.chat.id, "🚫 У вас нет прав администратора")
            return
        
        groups = self.backend.get_all_groups()
        if not groups:
            self.bot.send_message(message.chat.id, "❌ Нет созданных групп. Сначала создайте группы через меню '👥 Управление группами'")
            return
        
        self.user_states[user_id] = 'awaiting_broadcast_photos'
        self.temp_data[user_id] = {'photos': []}
        
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
            
            groups = self.backend.get_all_groups()
            markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
            for group in groups:
                markup.add(group['group_name'])
            markup.add("Все группы")
            
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
            group_name = message.text.strip()
            
            data = self.temp_data.get(user_id, {})
            text = data.get('text', '')
            photos = data.get('photos', [])
            
            try:
                if group_name == "Все группы":
                    order_id = self.backend.create_order(user_id, text, None, photos)
                    self._send_broadcast_to_all_groups(order_id, text, photos)
                else:
                    group = self.backend.get_group_by_name(group_name)
                    if not group:
                        self.bot.send_message(message.chat.id, "❌ Группа не найдена")
                        return
                    
                    order_id = self.backend.create_order(user_id, text, group['group_id'], photos)
                    self._send_broadcast_to_group(order_id, group['group_id'], text, photos)
                
                del self.user_states[user_id]
                del self.temp_data[user_id]
                
                markup = types.ReplyKeyboardRemove()
                self.bot.send_message(
                    message.chat.id,
                    f"✅ Рассылка отправлена группе '{group_name}'",
                    reply_markup=markup
                )
                self._show_admin_menu(message)
                
            except Exception as e:
                self.bot.send_message(message.chat.id, f"❌ Ошибка при отправке рассылки: {str(e)}")
    
    def _send_broadcast(self, order_id: int, group_type: str, text: str, photos: List[str]):
        if group_type == 'all':
            all_drivers = []
            groups = self.backend.get_all_groups()
            for group in groups:
                drivers = self.backend.get_drivers_by_group(group['group_id'])
                all_drivers.extend(drivers)
            drivers = all_drivers
        else:
            group = self.backend.get_group_by_name(group_type)
            if not group:
                print(f"Группа '{group_type}' не найдена")
                return
            drivers = self.backend.get_drivers_by_group(group['group_id'])
        
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
                group_name = driver.get('group_name', 'Не указана')
                
                message_text = (
                    f"✅ Водитель принял заказ #{order_id}:\n\n"
                    f"Заказ: {order['description'][:100]}...\n"
                    f"Водитель: {driver['full_name']}\n"
                    f"Телефон: {driver['phone']}\n"
                    f"Username: @{driver['username']}\n"
                    f"Группа: {group_name}\n"
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

    def _send_broadcast_to_group(self, order_id: int, group_id: int, text: str, photos: List[str]):
        drivers = self.backend.get_drivers_by_group(group_id)
        self._send_to_drivers(drivers, order_id, text, photos)

    def _send_broadcast_to_all_groups(self, order_id: int, text: str, photos: List[str]):
        all_drivers = []
        groups = self.backend.get_all_groups()
        for group in groups:
            drivers = self.backend.get_drivers_by_group(group['group_id'])
            all_drivers.extend(drivers)
        self._send_to_drivers(all_drivers, order_id, text, photos)

    def _send_to_drivers(self, drivers: List[Dict], order_id: int, text: str, photos: List[str]):
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