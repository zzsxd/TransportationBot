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
        self.group_id = self.config.get_group_id()
        
        self.user_states = {}
        self.temp_data = {}

    def clear_user_state(self, user_id: int):
        if user_id in self.user_states:
            del self.user_states[user_id]
        if user_id in self.temp_data:
            del self.temp_data[user_id]
    
    def is_admin(self, user_id: int, username: str) -> bool:
        return self.config.is_admin(user_id, username)
    
    def handle_start(self, message: types.Message):
        user_id = message.from_user.id
        username = message.from_user.username
        first_name = message.from_user.first_name
        last_name = message.from_user.last_name or ""
        
        self.clear_user_state(user_id)
        
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
            "👥 Управление группыми водителей\n\n"
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
        
        markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
        markup.add("❌ Отмена")
        
        self.bot.send_message(
            message.chat.id,
            "Отправьте до 6 фотографий для рассылки (или отправьте /skip чтобы пропустить):\n\n"
            "Для отмены нажмите '❌ Отмена'",
            reply_markup=markup
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
        
        if message.text == "❌ Отмена":
            self.clear_user_state(user_id)
            self._show_admin_menu(message)
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
            data['group_name'] = group_name
            self.temp_data[user_id] = data
            
            self.user_states[user_id] = 'awaiting_topic_name'
            self.bot.send_message(
                message.chat.id,
                "Введите название заказа для топика:",
                reply_markup=types.ReplyKeyboardRemove()
            )
    
    def handle_topic_name(self, message: types.Message):
        user_id = message.from_user.id
        username = message.from_user.username
        
        if not self.is_admin(user_id, username):
            self.bot.send_message(message.chat.id, "🚫 У вас нет прав администратора")
            if user_id in self.user_states:
                del self.user_states[user_id]
            if user_id in self.temp_data:
                del self.temp_data[user_id]
            return
        
        if self.user_states.get(user_id) == 'awaiting_topic_name':
            topic_name = message.text.strip()
            data = self.temp_data.get(user_id, {})
            
            try:
                if data.get('group_name') == "Все группы":
                    order_id = self.backend.create_order_with_topic(
                        user_id, data['text'], None, data['photos'], topic_name
                    )
                    self._send_broadcast_to_all_groups(order_id, data['text'], data['photos'], topic_name)
                else:
                    group = self.backend.get_group_by_name(data['group_name'])
                    if not group:
                        self.bot.send_message(message.chat.id, "❌ Группа не найдена")
                        return
                    
                    order_id = self.backend.create_order_with_topic(
                        user_id, data['text'], group['group_id'], data['photos'], topic_name
                    )
                    self._send_broadcast_to_group(order_id, group['group_id'], data['text'], data['photos'], topic_name)
                
                self._create_topic_in_group(topic_name, order_id, data['text'], data['photos'])
                
                del self.user_states[user_id]
                del self.temp_data[user_id]
                
                markup = types.ReplyKeyboardRemove()
                self.bot.send_message(
                    message.chat.id,
                    f"✅ Рассылка отправлена группе '{data.get('group_name', 'Все группы')}'\n"
                    f"Топик '{topic_name}' создан в группе",
                    reply_markup=markup
                )
                self._show_admin_menu(message)
                
            except Exception as e:
                self.bot.send_message(message.chat.id, f"❌ Ошибка при отправке рассылки: {str(e)}")
    
    def _create_topic_in_group(self, topic_name: str, order_id: int, text: str, photos: List[str]):
        if not self.group_id:
            print("❌ Group ID не указан в конфигурации")
            return
        
        try:
            topic_result = self.bot.create_forum_topic(
                self.group_id,
                f"Заказ #{order_id}: {topic_name}"
            )
            
            if not topic_result or not hasattr(topic_result, 'message_thread_id'):
                print("❌ Не удалось создать топик")
                self._send_to_group_without_topic(order_id, text, photos, topic_name)
                return
            
            topic_id = topic_result.message_thread_id
            
            self.backend.db.execute(
                "UPDATE orders SET topic_id = ? WHERE order_id = ?",
                (topic_id, order_id)
            )
            
            message_text = f"📦 Заказ #{order_id}: {topic_name}\n\n{text}"
            
            if photos:
                media = [types.InputMediaPhoto(photo, caption=message_text if i == 0 else "") 
                        for i, photo in enumerate(photos)]
                self.bot.send_media_group(
                    self.group_id,
                    media,
                    message_thread_id=topic_id
                )
            else:
                self.bot.send_message(
                    self.group_id,
                    message_text,
                    message_thread_id=topic_id
                )
                
            print(f"✅ Топик создан: {topic_name} (ID: {topic_id})")
            
        except Exception as e:
            print(f"❌ Ошибка при создании топика: {e}")
            self._send_to_group_without_topic(order_id, text, photos, topic_name)

    def _send_to_group_without_topic(self, order_id: int, text: str, photos: List[str], topic_name: str):
        try:
            message_text = f"📦 Заказ #{order_id}: {topic_name}\n\n{text}"
            if photos:
                media = [types.InputMediaPhoto(photo, caption=message_text if i == 0 else "") 
                        for i, photo in enumerate(photos)]
                self.bot.send_media_group(self.group_id, media)
            else:
                self.bot.send_message(self.group_id, message_text)
            print(f"✅ Заказ отправлен в общий чат группы")
        except Exception as e:
            print(f"❌ Ошибка при отправке в общий чат: {e}")
    

    def send_offer_to_topic(self, order_id: int, driver_info: Dict, price: float):
        if not self.group_id:
            return
        
        try:
            order = self.backend.get_order_info(order_id)
            if not order or not order.get('topic_id'):
                return
            
            offer_message = (
                f"💵 Новое предложение по заказу #{order_id} - {order.get('topic_name', 'Без названия')}\n\n"
                f"Водитель: {driver_info['full_name']}\n"
                f"Телефон: {driver_info['phone']}\n"
                f"Username: @{driver_info['username']}\n"
                f"Цена: {price} руб.\n\n"
                f"Заказ: {order['description'][:100]}..."
            )
            
            markup = types.InlineKeyboardMarkup()
            markup.add(types.InlineKeyboardButton(
                "✅ Принять предложение",
                callback_data=f"accept_offer_{order_id}_{driver_info['user_id']}"
            ))
            
            self.bot.send_message(
                self.group_id,
                offer_message,
                reply_markup=markup,
                message_thread_id=order['topic_id']
            )
            
        except Exception as e:
            print(f"❌ Ошибка при отправке предложения в топик: {e}")
            try:
                order = self.backend.get_order_info(order_id)
                offer_message = (
                    f"💵 Новое предложение по заказу #{order_id} - {order.get('topic_name', 'Без названия')}\n\n"
                    f"Водитель: {driver_info['full_name']}\n"
                    f"Телефон: {driver_info['phone']}\n"
                    f"Username: @{driver_info['username']}\n"
                    f"Цена: {price} руб."
                )
                
                markup = types.InlineKeyboardMarkup()
                markup.add(types.InlineKeyboardButton(
                    "✅ Принять предложение",
                    callback_data=f"accept_offer_{order_id}_{driver_info['user_id']}"
                ))
                
                self.bot.send_message(self.group_id, offer_message, reply_markup=markup)
            except Exception as e2:
                print(f"❌ Ошибка при отправке в общий чат: {e2}")

    def _send_broadcast_to_group(self, order_id: int, group_id: int, text: str, photos: List[str], topic_name: str):
        drivers = self.backend.get_drivers_by_group(group_id)
        self._send_to_drivers(drivers, order_id, text, photos, topic_name)

    def _send_broadcast_to_all_groups(self, order_id: int, text: str, photos: List[str], topic_name: str):
        all_drivers = []
        groups = self.backend.get_all_groups()
        for group in groups:
            drivers = self.backend.get_drivers_by_group(group['group_id'])
            all_drivers.extend(drivers)
        self._send_to_drivers(all_drivers, order_id, text, photos, topic_name)

    def _send_to_drivers(self, drivers: List[Dict], order_id: int, text: str, photos: List[str], topic_name: str):
        for driver in drivers:
            try:
                if photos:
                    media = [types.InputMediaPhoto(photo) for photo in photos]
                    media[0].caption = f"📦 Новый заказ #{order_id} - {topic_name}:\n\n{text}"
                    self.bot.send_media_group(driver['user_id'], media)
                else:
                    self.bot.send_message(
                        driver['user_id'], 
                        f"📦 Новый заказ #{order_id} - {topic_name}:\n\n{text}"
                    )
                
                if driver['user_id'] not in self.temp_data:
                    self.temp_data[driver['user_id']] = {}
                self.temp_data[driver['user_id']]['current_order'] = order_id
                self.temp_data[driver['user_id']]['current_topic'] = topic_name
                
                markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
                markup.add("💵 Предложить цену")
                
                self.bot.send_message(
                    driver['user_id'],
                    "Нажмите кнопку чтобы предложить свою цену за заказ:",
                    reply_markup=markup
                )
                
            except Exception as e:
                print(f"Ошибка при отправке рассылки водителю {driver['user_id']}: {e}")

    def handle_driver_price_request(self, message: types.Message):
        user_id = message.from_user.id
        driver = self.backend.get_driver_info(user_id)
        
        if not driver:
            self.bot.send_message(message.chat.id, "❌ Вы не являетесь водителем")
            return
        
        if user_id not in self.temp_data or 'current_order' not in self.temp_data[user_id]:
            self.bot.send_message(message.chat.id, "❌ Нет активного заказа для предложения цены")
            return
        
        order_id = self.temp_data[user_id]['current_order']
        self.user_states[user_id] = f'awaiting_price_{order_id}'
        
        self.bot.send_message(
            message.chat.id,
            "Введите вашу цену за заказ:",
            reply_markup=types.ReplyKeyboardRemove()
        )

    def handle_driver_price(self, message: types.Message):
        user_id = message.from_user.id
        driver = self.backend.get_driver_info(user_id)
        
        if not driver:
            self.bot.send_message(message.chat.id, "❌ Вы не являетесь водителем")
            return
        
        if user_id in self.user_states and self.user_states[user_id].startswith('awaiting_price_'):
            try:
                price = float(message.text)
                order_id = int(self.user_states[user_id].split('_')[2])
                
                self.backend.add_driver_offer(order_id, user_id, price)
                
                self.send_offer_to_topic(order_id, driver, price)
                
                self.bot.send_message(
                    message.chat.id,
                    f"✅ Ваше предложение {price} руб. отправлено администратору"
                )
                
                self.clear_user_state(user_id)
                
            except ValueError:
                self.bot.send_message(message.chat.id, "❌ Пожалуйста, введите корректную цену (число)")
        else:
            self.bot.send_message(message.chat.id, "❌ Нет активного запроса на цену")

    def handle_accept_offer(self, call: types.CallbackQuery):
        parts = call.data.split('_')
        order_id = int(parts[2])
        driver_id = int(parts[3])
        
        user_id = call.from_user.id
        username = call.from_user.username
        
        if not self.is_admin(user_id, username):
            self.bot.answer_callback_query(call.id, "🚫 У вас нет прав администратора")
            return
        
        offers = self.backend.get_order_offers(order_id)
        offer_id = None
        for offer in offers:
            if offer['driver_id'] == driver_id:
                offer_id = offer['offer_id']
                break
        
        if not offer_id:
            self.bot.answer_callback_query(call.id, "❌ Предложение не найдено")
            return
        
        success = self.backend.accept_driver_offer(offer_id)
        
        if success:
            self.bot.answer_callback_query(call.id, "✅ Предложение принято")
            self.bot.edit_message_text(
                "✅ Предложение принято",
                call.message.chat.id,
                call.message.message_id
            )
            
            try:
                self.bot.send_message(
                    driver_id,
                    f"✅ Ваше предложение по заказу #{order_id} принято! Заказ закреплен за вами."
                )
            except:
                pass
            
            if self.group_id:
                order = self.backend.get_order_info(order_id)
                driver = self.backend.get_driver_info(driver_id)
                
                if order and driver:
                    completion_message = (
                        f"✅ Заказ #{order_id} - {order.get('topic_name', 'Без названия')} выполнен!\n\n"
                        f"Водитель: {driver['full_name']}\n"
                        f"Телефон: {driver['phone']}\n"
                        f"Username: @{driver['username']}\n"
                        f"Заказ: {order['description'][:100]}..."
                    )
                    
                    try:
                        self.bot.send_message(
                            self.group_id,
                            completion_message,
                            message_thread_id=order_id
                        )
                    except:
                        self.bot.send_message(self.group_id, completion_message)
        else:
            self.bot.answer_callback_query(call.id, "❌ Ошибка при принятии предложения")

    def handle_order_accept(self, call: types.CallbackQuery):
        driver_id = call.from_user.id
        order_id = int(call.data.split('_')[2])
        
        driver = self.backend.get_driver_info(driver_id)
        if not driver:
            self.bot.answer_callback_query(call.id, "❌ Вы не являетесь водителем")
            return
        
        self.bot.send_message(
            driver_id,
            "ℹ️ Пожалуйста, используйте кнопку '💵 Предложить цену' для участия в заказе"
        )
        self.bot.answer_callback_query(call.id, "Используйте кнопку 'Предложить цену'")

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