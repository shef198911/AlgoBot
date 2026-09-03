import pandas as pd
import joblib
import os
from config import logger, MODEL_FILE, ML_PROBABILITY_THRESHOLD, FEATURE_COLUMNS, TAKE_PROFIT_PCT

class MLFilter:
    def __init__(self):
        self.logger = logger.getChild("MLFilter")
        self.ensemble = None
        self.regressor = None
        self.is_trained = False
        self.load_model()
        
    def load_model(self):
        if os.path.exists(MODEL_FILE):
            try:
                model_data = joblib.load(MODEL_FILE)
                # Обратная совместимость или новая структура
                if isinstance(model_data, dict) and 'ensemble' in model_data:
                    self.ensemble = model_data['ensemble']
                    self.regressor = model_data['regressor']
                else:
                    self.ensemble = model_data # старая версия (если вдруг)
                    
                self.is_trained = True
                self.logger.info(f"Модель ИИ V3 успешно загружена из {MODEL_FILE}")
            except Exception as e:
                self.logger.error(f"Ошибка загрузки ИИ: {e}")
        else:
            self.logger.warning(f"Файл {MODEL_FILE} не найден. ИИ отключен.")
            
    def evaluate_signal(self, current_features):
        """
        Возвращает: (is_approved: bool, ai_confidence: float, predicted_tp_pct: float)
        """
        if not self.is_trained or self.ensemble is None:
            self.logger.warning("ML модель не загружена. Fail-closed активирован: сигнал отклонен.")
            return False, 0.0, None 
            
        try:
            if hasattr(self.ensemble, 'feature_names_in_'):
                feature_cols = [c for c in self.ensemble.feature_names_in_ if c in current_features]
            else:
                feature_cols = [c for c in FEATURE_COLUMNS if c in current_features]
            
            X = pd.DataFrame([current_features[feature_cols]])
            
            # Ансамбль: усредненная вероятность от 3-х моделей
            prob = float(self.ensemble.predict_proba(X)[0][1])
            self.last_probs = {}
            self.last_probs_str = ""
            
            try:
                probs_parts = []
                for name, est in self.ensemble.named_estimators_.items():
                    # Проверяем признаки конкретного эстиматора
                    est_cols = getattr(est, 'feature_names_in_', feature_cols)
                    X_est = pd.DataFrame([current_features[est_cols]])
                    p = float(est.predict_proba(X_est)[0][1])
                    self.last_probs[name.upper()] = p
                    probs_parts.append(f"{name.upper()}={p:.2f}")
                self.last_probs_str = ", ".join(probs_parts)
                self.logger.info(f"Оценка моделей: {self.last_probs_str}")
            except Exception as e:
                self.logger.debug(f"Не удалось получить разбивку по моделям: {e}")
                
            self.logger.info(f"Оценка ИИ (Ансамбль): уверенность {prob:.2f} (порог {ML_PROBABILITY_THRESHOLD})")
            
            is_approved = prob >= ML_PROBABILITY_THRESHOLD
            
            # Если сделка одобрена, просим регрессор предсказать Тейк-Профит
            predicted_tp_pct = None
            if is_approved and self.regressor is not None:
                reg_cols = getattr(self.regressor, 'feature_names_in_', feature_cols)
                X_reg = pd.DataFrame([current_features[reg_cols]])
                predicted_tp_pct = self.regressor.predict(X_reg)[0]
                # Ограничиваем неадекватные значения
                predicted_tp_pct = max(0.005, min(TAKE_PROFIT_PCT * 2.0, predicted_tp_pct))
                
            return is_approved, prob, predicted_tp_pct
            
        except Exception as e:
            self.logger.error(f"Ошибка при оценке сигнала: {e}")
            return False, 0.0, None
