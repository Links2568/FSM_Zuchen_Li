TRANSITION_MESSAGES = {
    # Forward transitions
    ("IDLE", "WATER_NO_HANDS"): "Water detected. Please put your hands under the water.",
    ("IDLE", "HANDS_NO_WATER"): "Hands detected. Please turn on the faucet.",
    ("IDLE", "WASHING"): "Good, now washing your hands.",
    ("WATER_NO_HANDS", "WASHING"): "Hands detected, now washing.",
    ("HANDS_NO_WATER", "WASHING"): "Water detected, now washing.",
    ("WASHING", "SOAPING"): "Applying hand soap, great!",
    ("SOAPING", "RINSING"): "Rinsing the soap off now.",
    # Rinsing quality upgrades
    ("RINSING", "RINSING_OK"): "Good rinsing! Keep going for a thorough rinse.",
    ("RINSING_OK", "RINSING_THOROUGH"): "Excellent! Thorough rinsing achieved.",
    # Re-soap from any rinsing level
    ("RINSING", "SOAPING"): "Re-applying soap for another round.",
    ("RINSING_OK", "SOAPING"): "Re-applying soap for another round.",
    ("RINSING_THOROUGH", "SOAPING"): "Re-applying soap for another round.",
    # Drying from RINSING variants
    ("RINSING", "TOWEL_DRYING"): "Drying hands with a towel, good choice.",
    ("RINSING", "CLOTHES_DRYING"): "Drying hands on clothes. A towel would be better.",
    ("RINSING", "BLOWER_DRYING"): "Using the hand dryer.",
    ("RINSING_OK", "TOWEL_DRYING"): "Drying hands with a towel, good choice.",
    ("RINSING_OK", "CLOTHES_DRYING"): "Drying hands on clothes. A towel would be better.",
    ("RINSING_OK", "BLOWER_DRYING"): "Using the hand dryer.",
    ("RINSING_THOROUGH", "TOWEL_DRYING"): "Drying hands with a towel, good choice.",
    ("RINSING_THOROUGH", "CLOTHES_DRYING"): "Drying hands on clothes. A towel would be better.",
    ("RINSING_THOROUGH", "BLOWER_DRYING"): "Using the hand dryer.",
    # Skip soap — wash directly to drying
    ("WASHING", "TOWEL_DRYING"): "Drying without soap. Try using soap next time.",
    ("WASHING", "CLOTHES_DRYING"): "Drying on clothes without soap. Try soap and a towel next time.",
    ("WASHING", "BLOWER_DRYING"): "Drying without soap. Try using soap next time.",
    # Skip rinse — soap directly to drying
    ("SOAPING", "TOWEL_DRYING"): "Drying without rinsing. Make sure to rinse off the soap next time.",
    ("SOAPING", "CLOTHES_DRYING"): "Drying on clothes without rinsing. Rinse and use a towel next time.",
    ("SOAPING", "BLOWER_DRYING"): "Drying without rinsing. Make sure to rinse off the soap next time.",
    # Drying to DONE
    ("TOWEL_DRYING", "DONE"): "All done! Great job washing your hands.",
    ("CLOTHES_DRYING", "DONE"): "All done! Next time try using a towel.",
    ("BLOWER_DRYING", "DONE"): "All done! Great job.",
    # Idle timeout regressions
    ("WATER_NO_HANDS", "IDLE"): "Activity stopped. Please continue.",
    ("HANDS_NO_WATER", "IDLE"): "Activity stopped. Please continue.",
    ("WASHING", "IDLE"): "You seem to have stopped. Please continue washing.",
    ("SOAPING", "IDLE"): "You seem to have stopped. Please continue.",
    ("RINSING", "IDLE"): "You seem to have stopped. Please continue rinsing.",
    ("RINSING_OK", "IDLE"): "You seem to have stopped. Please continue rinsing.",
    ("RINSING_THOROUGH", "IDLE"): "You seem to have stopped rinsing.",
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
    "RINSING_OK": [
        {"delay": 8, "message": "Good rinsing! Keep going a bit longer for a thorough rinse."},
    ],
    "RINSING_THOROUGH": [
        {"delay": 8, "message": "Excellent rinse! You can dry your hands now."},
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

# Adaptive Level-of-Detail guidance: lod_level 0 = basic, 1 = detailed, 2 = very detailed
LOD_GUIDANCE = {
    "IDLE": [
        "Please start washing your hands.",
        "Turn on the faucet and place your hands under the water to begin.",
        "Step 1: Turn on the faucet. Step 2: Place both hands under the running water.",
    ],
    "WATER_NO_HANDS": [
        "Put your hands under the water.",
        "Place both hands under the running water to start washing.",
        "Move your hands directly under the faucet stream. The water is running but your hands are not detected.",
    ],
    "HANDS_NO_WATER": [
        "Turn on the faucet.",
        "Turn on the faucet to start washing your hands.",
        "Reach for the faucet handle and turn it on. Then place your hands under the water stream.",
    ],
    "WASHING": [
        "Apply soap when ready.",
        "Good, your hands are under water. Now apply soap to both hands.",
        "Reach for the soap dispenser and press it to get soap on your hands. Rub all surfaces.",
    ],
    "SOAPING": [
        "Lather all hand surfaces.",
        "Rub the soap over all surfaces: palms, backs, between fingers, and under nails.",
        "Make sure to scrub: palms together, back of each hand, interlace fingers, thumbs, and fingertips on palms. Aim for 20 seconds.",
    ],
    "RINSING": [
        "Rinse off the soap.",
        "Hold your hands under running water and rinse off all the soap.",
        "Place both hands under the water stream and rub them together to remove all soap residue. Continue for at least 10 seconds.",
    ],
    "RINSING_OK": [
        "Good rinsing! Keep going or dry your hands.",
        "You have rinsed for a good amount of time. A bit more for a thorough rinse, or you can dry.",
        "You have been rinsing for about 5 seconds. Continue for 5 more seconds for a thorough rinse, or proceed to dry your hands.",
    ],
    "RINSING_THOROUGH": [
        "Excellent rinse! Dry your hands now.",
        "Thorough rinse achieved. Use a towel or dryer to dry your hands.",
        "Great job rinsing thoroughly! Now reach for a paper towel or use the hand dryer to dry your hands completely.",
    ],
    "TOWEL_DRYING": [
        "Dry your hands thoroughly.",
        "Use the towel to dry all surfaces of your hands completely.",
        "Pat both sides of your hands, between your fingers, and your wrists with the towel until completely dry.",
    ],
    "CLOTHES_DRYING": [
        "Drying on clothes. Use a towel next time.",
        "You are wiping your hands on your clothes. A clean towel is more hygienic.",
        "Using clothes to dry is less hygienic. Next time, reach for a paper towel or use the hand dryer instead.",
    ],
    "BLOWER_DRYING": [
        "Keep hands under the dryer.",
        "Hold your hands under the dryer and rub them together until dry.",
        "Position both hands under the air stream and rub them together. Make sure all surfaces are dry before finishing.",
    ],
    "DONE": [
        "All done! Great job.",
        "Hand washing complete. Great job!",
        "Hand washing complete. You did a great job following all the steps!",
    ],
}
