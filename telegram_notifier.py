import requests
from config import logger, TG_BOT_TOKEN, TG_CHAT_ID

class TelegramNotifier:
    def __init__(self):
        self.token = TG_BOT_TOKEN
        self.chat_id = TG_CHAT_ID
        self.logger = logger.getChild("Telegram")
        self.base_url = f"https://api.telegram.org/bot{self.token}"

    def send_message(self, text):
        if not self.token or not self.chat_id:
            self.logger.warning("Telegram не настроен (отсутствует Token или Chat ID). Сообщение пропущено.")
            return

        try:
            url = f"{self.base_url}/sendMessage"
            payload = {
                "chat_id": self.chat_id,
                "text": text,
                "parse_mode": "HTML"
            }
            response = requests.post(url, json=payload, timeout=5)
            if response.status_code != 200:
                self.logger.error(f"Ошибка отправки в TG: {response.text}")
        except Exception as e:
            self.logger.error(f"Критическая ошибка отправки в TG: {e}")

    def get_updates(self):
        """Вспомогательная функция, чтобы узнать Chat ID пользователя"""
        try:
            url = f"{self.base_url}/getUpdates"
            response = requests.get(url, timeout=5).json()
            if response.get("ok") and len(response.get("result", [])) > 0:
                # Берем Chat ID из последнего сообщения
                chat_id = response["result"][-1]["message"]["chat"]["id"]
                return chat_id
            return None
        except Exception as e:
            self.logger.error(f"Ошибка при попытке получить обновления TG: {e}")
            return None
