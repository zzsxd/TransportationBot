import telebot
from frontend import Frontend
from config_parser import ConfigParser

def main():
    config = ConfigParser()
    bot_token = config.get_bot_token()
    
    if not bot_token:
        print("Ошибка: не указан bot_token в конфигурационном файле")
        return

    bot = telebot.TeleBot(bot_token)
    frontend = Frontend(bot)
    
    @bot.message_handler(commands=['start'])
    def handle_start(message):
        frontend.clear_user_state(message.from_user.id)
        frontend.handle_start(message)

    @bot.message_handler(commands=['cancel'])
    def handle_cancel(message):
        user_id = message.from_user.id
        frontend.clear_user_state(user_id)
        
        if frontend.is_admin(user_id, message.from_user.username):
            frontend._show_admin_menu(message)
        else:
            driver = frontend.backend.get_driver_info(user_id)
            if driver:
                frontend._show_driver_menu(message)
            else:
                frontend.bot.send_message(
                    message.chat.id,
                    "❌ Команда отмены выполнена. Используйте /start для начала работы."
                )
    
    @bot.message_handler(commands=['my_orders'])
    def handle_my_orders(message):
        frontend.handle_my_orders(message)
    
    @bot.message_handler(func=lambda message: True)
    def handle_messages(message):
        user_id = message.from_user.id
        username = message.from_user.username
        
        state = frontend.user_states.get(user_id)
        if state:
            if state.startswith('awaiting_driver'):
                frontend.handle_driver_registration(message)
                return
            elif state == 'awaiting_broadcast_photos':
                frontend.handle_broadcast_photos(message)
                return
            elif state == 'awaiting_broadcast_text':
                frontend.handle_broadcast_text(message)
                return
            elif state == 'awaiting_broadcast_group':
                frontend.handle_broadcast_group(message)
                return
            elif state == 'awaiting_topic_name':
                frontend.handle_topic_name(message)
                return
            elif state == 'awaiting_group_name':
                frontend._handle_group_name(message)
                return
            elif state == 'awaiting_driver_phone':
                frontend.handle_driver_registration(message)
                return
            elif state == 'awaiting_group_remove':
                frontend._handle_group_remove_confirmation(message)
                return
            elif state.startswith('awaiting_price_'):
                frontend.handle_driver_price(message)
                return
        
        if message.text in ["📊 Пользователи Excel", "🚚 Водители Excel", "⬅️ Назад"]:
            frontend.handle_export_excel_choice(message)
            return
        elif message.text in ["👥 Управление группами", "➕ Добавить группу", "➖ Удалить группу", "📋 Список групп"]:
            frontend.handle_admin_commands(message)
            return
        elif message.text == "💵 Предложить цену":
            frontend.handle_driver_price_request(message)
            return
        elif message.text.startswith("❌ "):
            frontend._handle_group_remove(message)
            return
        
        if frontend.is_admin(user_id, username):
            frontend.handle_admin_commands(message)
    
    @bot.message_handler(content_types=['photo'])
    def handle_photos(message):
        user_id = message.from_user.id
        username = message.from_user.username
        state = frontend.user_states.get(user_id)
        
        if state == 'awaiting_broadcast_photos' and frontend.is_admin(user_id, username):
            frontend.handle_broadcast_photos(message)

    @bot.message_handler(content_types=['contact'])
    def handle_contact(message):
        frontend.handle_contact(message)
    
    @bot.callback_query_handler(func=lambda call: call.data.startswith('accept_order_'))
    def handle_callback(call):
        frontend.handle_order_accept(call)
    
    @bot.callback_query_handler(func=lambda call: call.data.startswith('remove_driver_'))
    def handle_remove_driver(call):
        frontend.handle_remove_driver(call)

    @bot.callback_query_handler(func=lambda call: call.data.startswith('remove_group_'))
    def handle_remove_group(call):
        frontend.handle_remove_group(call)

    @bot.callback_query_handler(func=lambda call: call.data.startswith('accept_offer_'))
    def handle_accept_offer(call):
        frontend.handle_accept_offer(call)
    
    print("Бот запущен...")
    bot.polling(none_stop=True)

if __name__ == "__main__":
    main()