# app/trading/settings_manager.py - РАСШИРЕННАЯ ВЕРСИЯ с мульти-TP
from __future__ import annotations
from pydantic import BaseModel, Field
from pathlib import Path
import json
import threading

# Путь: /app/db/bot_settings.json (если рабочая директория /app)
_SETTINGS_PATH = Path(__file__).resolve().parents[1] / "db" / "bot_settings.json"
_LOCK = threading.RLock()

class BotSettings(BaseModel):
    # Проценты указываются как человек видит: 40 означает 40%
    risk_long_percent: float = Field(default=30.0, ge=0, le=100)
    risk_short_percent: float = Field(default=30.0, ge=0, le=100)
    stop_loss_percent: float = Field(default=0.51, ge=0, le=100)
    
    # НОВОЕ: мульти-TP настройки
    use_multi_tp: bool = True  # Включить/выключить мульти-TP
    take_profit_percent: float = Field(default=5.7, ge=0, le=100)  # Старое поле для совместимости
    tp_levels: list[float] = [0.5, 1.0, 1.6]  # Уровни TP в процентах
    tp_portions: list[float] = [0.33, 0.33, 0.34]  # Доли позиции для каждого TP (в сумме ~1.0)
    
    # Авто-ликвидация
    auto_liquidation_enabled: bool = True
    auto_liquidation_time: str = "21:44"
    auto_liquidation_block_minutes: int = 30
    auto_liquidation_days: list[int] = [0, 1, 2, 3, 4]

    def get_tp_distribution(self, total_lots: int) -> list[tuple[float, int]]:
        """
        Возвращает распределение лотов по уровням TP.
        Returns: [(tp_percent, lots), ...]
        """
        if not self.use_multi_tp or total_lots <= 0:
            return [(self.take_profit_percent, total_lots)]
        
        distribution = []
        remaining_lots = total_lots
        
        # Распределяем лоты по порциям
        for i, (tp_percent, portion) in enumerate(zip(self.tp_levels, self.tp_portions)):
            if i == len(self.tp_levels) - 1:  # Последний уровень получает все оставшиеся лоты
                lots = remaining_lots
            else:
                lots = max(1, round(total_lots * portion))  # Минимум 1 лот
                lots = min(lots, remaining_lots)  # Не больше оставшихся
            
            if lots > 0:
                distribution.append((tp_percent, lots))
                remaining_lots -= lots
            
            if remaining_lots <= 0:
                break
        
        return distribution

class SettingsManager:
    def __init__(self, path: Path):
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._settings = self._load_or_default()

    def _load_or_default(self) -> BotSettings:
        if self.path.exists():
            try:
                data = json.loads(self.path.read_text(encoding="utf-8"))
                return BotSettings(**data)
            except Exception:
                pass
        # defaults
        s = BotSettings()
        self._persist(s)
        return s

    def _persist(self, settings: BotSettings):
        tmp = self.path.with_suffix(".json.tmp")
        data = settings.model_dump()
        tmp.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
        tmp.replace(self.path)

    def get(self, reload: bool = False) -> BotSettings:
        with _LOCK:
            if reload:
                self._settings = self._load_or_default()
            return self._settings

    def update(self, **kwargs) -> BotSettings:
        with _LOCK:
            updated = self._settings.model_copy(update=kwargs)
            self._persist(updated)
            self._settings = updated
            return updated

_manager = SettingsManager(_SETTINGS_PATH)

def get_settings(reload: bool = True) -> BotSettings:
    return _manager.get(reload=reload)

def update_settings(**kwargs) -> BotSettings:
    return _manager.update(**kwargs)