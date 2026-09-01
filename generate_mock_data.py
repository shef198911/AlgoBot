import sqlite3
from datetime import datetime, timedelta
import random
from db_manager import init_db, DB_FILE

def populate_mock_data():
    init_db()
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    
    # Очищаем старые данные
    cursor.execute("DELETE FROM trades")
    cursor.execute("DELETE FROM bot_status")
    
    # Генерируем 15 фейковых сделок для красивого графика
    now = datetime.now()
    total_profit = 0
    
    for i in range(15, 0, -1):
        trade_time = now - timedelta(hours=i*4)
        side = random.choice(['BUY', 'SELL'])
        entry = random.uniform(55000, 65000)
        
        # 70% win rate для красивой картинки
        is_win = random.random() < 0.7 
        if is_win:
            profit = random.uniform(5, 25)
            exit_price = entry * 1.01 if side == 'BUY' else entry * 0.99
        else:
            profit = random.uniform(-5, -15)
            exit_price = entry * 0.99 if side == 'BUY' else entry * 1.01
            
        ai_conf = random.uniform(0.65, 0.95)
        
        cursor.execute('''
            INSERT INTO trades (timestamp, symbol, side, entry_price, exit_price, profit_usdt, ai_confidence, status)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ''', (trade_time.strftime("%Y-%m-%d %H:%M:%S"), 'BTC/USDT', side, entry, exit_price, profit, ai_conf, 'CLOSED'))

    # Добавляем статус
    cursor.execute('''
        INSERT INTO bot_status (timestamp, message, ai_confidence)
        VALUES (?, ?, ?)
    ''', (now.strftime("%Y-%m-%d %H:%M:%S"), "Мониторинг рынка. Ожидание идеального сетапа.", 0.78))
    
    conn.commit()
    conn.close()
    print("Тестовые данные успешно сгенерированы!")

if __name__ == "__main__":
    populate_mock_data()
