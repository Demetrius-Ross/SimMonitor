# simulator_map.py
SIMULATOR_MAP = {
    1: "PC-12",
    2: "ERJ-32",
    3: "EC-135",
    4: "ERJ-24",
    5: "ERJ-16",
    6: "ERJ-19",
    7: "EC-130",
    8: "AS-350",
    9: "B407",
    10: "CRJ-700",
    11: "EC-145",
    12: "CRJ-200"
}

def get_simulator_name(device_id):
    """Returns the simulator name if available, else 'Unknown-Sim' with ID"""
    return SIMULATOR_MAP.get(device_id, f"Unknown-Sim-{device_id}")
