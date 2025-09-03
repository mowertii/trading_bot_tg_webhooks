# app/trading/settings_manager.py
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
    take_profit_percent: float = Field(default=5.7, ge=0, le=100)


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
        data = settings.model_dump()  # получаем dict
        tmp.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
        tmp.replace(self.path)

    def get(self, reload: bool = True) -> BotSettings:
        """
        Возвращает текущие настройки.
        Если reload=True — перечитывает JSON с диска (чтобы подхватывать онлайн-изменения).
        """
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
    """По умолчанию перечитываем JSON для онлайн-обновлений."""
    return _manager.get(reload=reload)


def update_settings(**kwargs) -> BotSettings:
    return _manager.update(**kwargs)
