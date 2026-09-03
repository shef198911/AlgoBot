import logging
import os
from dotenv import load_dotenv

load_dotenv()

# --- Настройки API (Binance Testnet) ---
# Ключи добавим позже, пока оставляем пустыми
API_KEY = os.getenv("BINANCE_TESTNET_API_KEY", "")
API_SECRET = os.getenv("BINANCE_TESTNET_API_SECRET", "")
USE_TESTNET = True  # КРИТИЧНО: Всегда True во время тестов!

TRADING_MODE = "NORMAL" # Режимы: "NORMAL" или "SCALPING"
RISK_MODE = "BALANCED" # Режимы: "CONSERVATIVE", "BALANCED", "AGGRESSIVE"
AI_ENABLED = True
SYMBOLS = [
    "BTC/USDT", "ETH/USDT", "SOL/USDT", "BNB/USDT", "ADA/USDT", "XRP/USDT", "DOGE/USDT", "LINK/USDT", "AVAX/USDT",
    "DOT/USDT", "LTC/USDT", "BCH/USDT", "ATOM/USDT", "UNI/USDT", "FIL/USDT", "NEAR/USDT", "AAVE/USDT", "OP/USDT", 
    "ARB/USDT", "INJ/USDT", "SUI/USDT", "APT/USDT", "S/USDT", "WLD/USDT", "GALA/USDT"
]
if TRADING_MODE == "NORMAL":
    TIMEFRAME = "15m"
    TREND_TIMEFRAME = "1h"
    ML_HORIZON = 48
    SWING_K = 3
    RETEST_MAX_BARS = 8
else: # SCALPING
    TIMEFRAME = "1m"
    TREND_TIMEFRAME = "15m"
    ML_HORIZON = 60
    SWING_K = 2
    RETEST_MAX_BARS = 5

TRADE_SIZE_USDT = 100.0  # Сколько СВОИХ денег (маржи) мы вкладываем в сделку
LEVERAGE = 20 # Плечо
MAX_CAPITAL_USDT = 500.0 # Общий лимит выделенных средств на торговлю

# --- Настройки Market Structure & Price Action Engine ---
SR_ZONE_ATR_MULTIPLIER = 0.75       # Ширина зоны S/R в ATR
SR_MERGE_TOLERANCE_ATR = 1.0       # Макс. дистанция для объединения близких свингов в одну зону
BREAKOUT_ATR_MULTIPLIER = 0.3      # Буфер пробоя в ATR
MIN_BREAKOUT_PCT = 0.0015          # Минимальный пробой в %
RETEST_TOLERANCE_ATR = 0.8         # Допуск ретеста в ATR
INVALIDATION_ATR_MULTIPLIER = 1.0  # Буфер инвалидации пробитого уровня
PINBAR_WICK_RATIO = 0.45           # Минимальная доля тени для пин-бара / отторжения
ENGULFING_BODY_RATIO = 1.1         # Отношение тела для поглощения

# Веса факторов для расчета SETUP_SCORE (сумма = 100)
SCORE_WEIGHT_BREAKOUT = 20
SCORE_WEIGHT_RETEST = 20
SCORE_WEIGHT_REJECTION = 15
SCORE_WEIGHT_VOLUME = 10
SCORE_WEIGHT_STRUCTURE = 15
SCORE_WEIGHT_TREND = 10
SCORE_WEIGHT_MOMENTUM = 10
MIN_SETUP_SCORE = 55               # Минимальный балл сетапа для формирования ta_signal
SCORE_ADX_MIN = 20                 # Минимальный ADX для трендового фактора в score

# Параметры Range Detection & Trend Pullback
RANGE_MAX_EXPANSION_ATR = 3.5      # Максимальная высота коридора в ATR для боковика
RANGE_MIN_TOUCHES = 2              # Мин. касаний верхней/нижней границ для подтверждения коридора
PULLBACK_MAX_DEPTH_ATR = 2.0       # Макс. глубина отката по тренду в ATR

DATASET_TARGET_BARS = 1500         # Базовый объем истории для обучения (с возможностью расширения)

# --- Про-Фичи (Pro-Trader) ---
USE_COMPOUNDING = False    # Использовать % от депозита вместо фикс. маржи
COMPOUND_PCT = 2.0         # Процент от депозита на 1 сделку
USE_ATR = False             # Динамический Стоп/Тейк по ATR (волатильность)
USE_TRAILING = True        # Использовать плавающий стоп
TRAILING_ACTIVATION_PCT = 0.008  # Активация трейлинга при +0.8% профита
TRAILING_DISTANCE_PCT = 0.004    # Дистанция трейлинга 0.4%

STOP_LOSS_PCT = 0.02  
TAKE_PROFIT_PCT = 0.04 

# --- Настройки ИИ (Meta-Labeling) ---
ML_PROBABILITY_THRESHOLD = 0.55  # Минимальная уверенность ИИ для входа в сделку (от 0 до 1)
MODEL_FILE = f"model_{TRADING_MODE.lower()}.pkl" # Разные файлы для разных режимов

# --- Настройки Telegram ---
TG_BOT_TOKEN = os.getenv("TG_BOT_TOKEN", "")
TG_CHAT_ID = os.getenv("TG_CHAT_ID", "") # Будет заполнено позже

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
 
MIN_SR_DISTANCE_PCT = 0.005 # Мин. расстояние (0.5%) до сопротивления/поддержки перед входом

FEATURE_COLUMNS = [
    'EMA_FAST', 'EMA_SLOW', 'RSI', 'ATRr', 'VWAP', 'ADX', 
    'BB_UPPER', 'BB_LOWER', 'BB_WIDTH', 'PRICE_ROC', 'VOL_RATIO', 'VWAP_DIST',
    # Market Structure & Levels
    'DIST_RES_PCT', 'DIST_SUP_PCT', 'SR_STRENGTH', 'MARKET_STRUCTURE',
    # BOS & CHOCH
    'BOS_LONG', 'BOS_SHORT', 'CHOCH_LONG', 'CHOCH_SHORT',
    # Breakout & Retest Quality
    'BREAKOUT_STRENGTH', 'BREAKOUT_VOLUME_RATIO',
    'IS_BREAKOUT_LONG', 'IS_BREAKOUT_SHORT',
    'IS_RETEST_LONG', 'IS_RETEST_SHORT',
    # Candle Confirmations & Sweeps
    'BULLISH_REJECTION', 'BEARISH_REJECTION',
    'BULLISH_ENGULFING', 'BEARISH_ENGULFING',
    'LIQUIDITY_SWEEP_HIGH', 'LIQUIDITY_SWEEP_LOW',
    # Final Setup Score
    'SETUP_SCORE'
]
