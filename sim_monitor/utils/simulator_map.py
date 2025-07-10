# simulator_map.py
SIMULATOR_MAP = {
    1: "AS-350",
    #1: "PC-12",
    2: "B407",
    #2: "ERJ-32",
    3: "EC-130",
    4: "EC-135",
    5: "ERJ-24",
    6: "PC-12",
    7: "CRJ-200",
    8: "ERJ-19",
    9: "ERJ-16",
    10: "CRJ-700",
    11: "EC-145",
    12: "ERJ-32"
}

SIMULATOR_LAYOUT = {
    1:  (0, 0),
    #1:  (2, 1),
    2:  (1, 0),
    #2:  (6, 1),
    3:  (2, 0),
    7:  (3, 0),
    8:  (4, 1),
    9:  (4, 0),
    10: (3, 1),

    4:  (0, 1),
    5:  (1, 1),
    6:  (2, 1),
    # columns 3 & 4 in row 1 are empty
    11: (5, 1),
    12: (5, 0),
    #12: (1, 0),
}

def get_simulator_name(device_id):
    """Returns the simulator name if available, else 'Unknown-Sim' with ID"""
    return SIMULATOR_MAP.get(device_id, f"Unknown-Sim-{device_id}")
