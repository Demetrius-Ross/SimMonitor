# utils/layout_io.py
import json, pathlib, datetime

BASE_DIR = pathlib.Path(__file__).resolve().parent.parent   # root folder
CFG_DIR  = BASE_DIR / "configs"
CFG_DIR.mkdir(exist_ok=True)

def timestamp() -> str:
    return datetime.datetime.now().strftime("%Y%m%d_%H%M%S")

def write_layout(sim_map: dict, layout_map: dict, filename: str | None = None):
    """Save to /configs/<filename>.json.  If filename is None → auto timestamp."""
    if filename is None:
        filename = f"layout_{timestamp()}"
    path = CFG_DIR / f"{filename}.json"
    data = {"sim_map": sim_map, "layout_map": layout_map}
    path.write_text(json.dumps(data, indent=2))
    return path.name

def read_layout(path: pathlib.Path):
    data = json.loads(path.read_text())
    return data["sim_map"], data["layout_map"]

def list_layout_files():
    return sorted(CFG_DIR.glob("*.json"))
