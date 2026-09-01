import time
from telegram_notifier import TelegramNotifier
from config import TG_BOT_TOKEN

if __name__ == "__main__":
    if not TG_BOT_TOKEN:
        print("Ошибка: Токен бота не установлен в config.py")
        exit()
        
    print("==================================================")
    print("НАСТРОЙКА TELEGRAM")
    print("1. Открой своего бота в Telegram.")
    print("2. Нажми кнопку 'Запустить' (или напиши ему любое сообщение, например 'Привет').")
    print("==================================================")
    print("Жду сообщение от тебя...")
    
    notifier = TelegramNotifier()
    
    while True:
        chat_id = notifier.get_updates()
        if chat_id:
            print("\nУСПЕХ! Я нашел твой Chat ID.")
            print(f"Твой Chat ID: {chat_id}")
            print("\nСкопируй этот номер и вставь его в файл config.py в переменную TG_CHAT_ID = \"сюда\"")
            break
        time.sleep(3)
