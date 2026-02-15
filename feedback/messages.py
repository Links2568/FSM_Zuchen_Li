TRANSITION_MESSAGES = {
    # Forward transitions
    ("IDLE", "WATER_NO_HANDS"): "Water detected. Please put your hands under the water.",
    ("IDLE", "HANDS_NO_WATER"): "Hands detected. Please turn on the faucet.",
    ("IDLE", "WASHING"): "Good, now washing your hands.",
    ("WATER_NO_HANDS", "WASHING"): "Hands detected, now washing.",
    ("HANDS_NO_WATER", "WASHING"): "Water detected, now washing.",
    ("WASHING", "SOAPING"): "Applying hand soap, great!",
    ("SOAPING", "RINSING"): "Rinsing the soap off now.",
    ("RINSING", "TOWEL_DRYING"): "Drying hands with a towel, good choice.",
    ("RINSING", "CLOTHES_DRYING"): "Drying hands on clothes. A towel would be better.",
    ("RINSING", "BLOWER_DRYING"): "Using the hand dryer.",
    ("TOWEL_DRYING", "DONE"): "All done! Great job washing your hands.",
    ("CLOTHES_DRYING", "DONE"): "All done! Next time try using a towel.",
    ("BLOWER_DRYING", "DONE"): "All done! Great job.",
    # Idle timeout regressions
    ("WATER_NO_HANDS", "IDLE"): "Activity stopped. Please continue.",
    ("HANDS_NO_WATER", "IDLE"): "Activity stopped. Please continue.",
    ("WASHING", "IDLE"): "You seem to have stopped. Please continue washing.",
    ("SOAPING", "IDLE"): "You seem to have stopped. Please continue.",
    ("RINSING", "IDLE"): "You seem to have stopped. Please continue rinsing.",
    ("TOWEL_DRYING", "IDLE"): "You seem to have stopped drying.",
    ("CLOTHES_DRYING", "IDLE"): "You seem to have stopped drying.",
    ("BLOWER_DRYING", "IDLE"): "You seem to have stopped drying.",
}

STATE_WARNINGS = {
    "IDLE": {"delay": 20, "message": "Please turn on the faucet and start washing your hands."},
    "WATER_NO_HANDS": [
        {"delay": 10, "message": "Please put your hands under the water."},
        {"delay": 20, "message": "Please save water. Put your hands under or turn off the faucet."},
    ],
    "HANDS_NO_WATER": [
        {"delay": 10, "message": "Please turn on the faucet."},
    ],
    "WASHING": [
        {"delay": 20, "message": "Please save water. Apply soap or turn off the faucet."},
    ],
    "SOAPING": [
        {"delay": 10, "message": "Remember to lather all surfaces of your hands for at least 20 seconds."},
        {"delay": 25, "message": "Great lathering! You can rinse your hands now."},
    ],
    "RINSING": [
        {"delay": 15, "message": "Make sure to rinse off all the soap."},
    ],
    "TOWEL_DRYING": [
        {"delay": 8, "message": "Make sure your hands are fully dry."},
    ],
    "CLOTHES_DRYING": [
        {"delay": 8, "message": "Try using a clean towel next time for better hygiene."},
    ],
    "BLOWER_DRYING": [
        {"delay": 8, "message": "Keep your hands under the dryer until fully dry."},
    ],
}
