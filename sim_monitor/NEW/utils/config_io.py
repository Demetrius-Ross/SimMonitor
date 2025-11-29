# config_io.py  (place in utils/ or same folder)
import json, pathlib

CONFIG_PATH = pathlib.Path(__file__).with_name("config.json")

_default_cfg = {"debug_mode": True}

def load_cfg() -> dict:
    if CONFIG_PATH.exists():
        try:
            return json.loads(CONFIG_PATH.read_text())
        except json.JSONDecodeError:
            pass
    return _default_cfg.copy()

def save_cfg(cfg: dict):
    CONFIG_PATH.write_text(json.dumps(cfg, indent=2))
