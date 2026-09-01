import logging
import os

# --- Настройки API (Binance Testnet) ---
# Ключи добавим позже, пока оставляем пустыми
API_KEY = os.getenv("BINANCE_TESTNET_API_KEY", "")
API_SECRET = os.getenv("BINANCE_TESTNET_API_SECRET", "")
USE_TESTNET = True  # КРИТИЧНО: Всегда True во время тестов!

TRADING_MODE = "NORMAL" # Режимы: "NORMAL" или "SCALPING"
RISK_MODE = "AGGRESSIVE" # Режимы: "CONSERVATIVE", "BALANCED", "AGGRESSIVE"
AI_ENABLED = True
SYMBOLS = [
    "BTC/USDT", "ETH/USDT", "SOL/USDT", "BNB/USDT", "ADA/USDT", "XRP/USDT", "DOGE/USDT", "LINK/USDT", "AVAX/USDT",
    "DOT/USDT", "LTC/USDT", "BCH/USDT", "ATOM/USDT", "UNI/USDT", "FIL/USDT", "NEAR/USDT", "AAVE/USDT", "OP/USDT", 
    "ARB/USDT", "INJ/USDT", "SUI/USDT", "APT/USDT", "FTM/USDT", "WLD/USDT", "GALA/USDT"
]
TIMEFRAME = "15m"  # Для скальпинга 1m, для нормального 15m
TRADE_SIZE_USDT = 100.0  # Сколько СВОИХ денег (маржи) мы вкладываем в сделку
LEVERAGE = 20 # Плечо
MAX_CAPITAL_USDT = 500.0 # Общий лимит выделенных средств на торговлю

# --- Про-Фичи (Pro-Trader) ---
USE_COMPOUNDING = False    # Использовать % от депозита вместо фикс. маржи
COMPOUND_PCT = 2.0         # Процент от депозита на 1 сделку
USE_ATR = False             # Динамический Стоп/Тейк по ATR (волатильность)
USE_TRAILING = True        # Использовать плавающий стоп
TRAILING_ACTIVATION_PCT = 0.008  # Активация трейлинга при +0.8% профита
TRAILING_DISTANCE_PCT = 0.004    # Дистанция трейлинга 0.4%

STOP_LOSS_PCT = 0.03  
TAKE_PROFIT_PCT = 0.06 

# --- Настройки ИИ (Meta-Labeling) ---
ML_PROBABILITY_THRESHOLD = 0.50  # Минимальная уверенность ИИ для входа в сделку (от 0 до 1)
MODEL_FILE = f"model_{TRADING_MODE.lower()}.pkl" # Разные файлы для разных режимов

# --- Настройки Telegram ---
TG_BOT_TOKEN = ""
TG_CHAT_ID = "332680373" # Будет заполнено позже

# --- Настройки логирования ---
LOG_FILE = "bot.log"
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[
        logging.FileHandler(LOG_FILE, encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("AlgoBot")
