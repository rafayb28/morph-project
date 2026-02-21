"""Configuration constants for the decision engine.

All weights, thresholds, and defaults live here so they're easy to tweak
without touching logic code. Override at runtime by passing a custom config
dict to the pipeline if needed.
"""

# ── Default scale ────────────────────────────────────────────────────────────
DEFAULT_SCALE_FT_PER_PX = 0.5

# ── Label base-risk weights (0-10 scale, higher = more dangerous) ────────────
LABEL_BASE_WEIGHTS: dict[str, float] = {
    # Weapons & violence
    "weapon?": 9.0,
    "weapon": 10.0,
    "fight": 8.0,
    "medical_emergency": 8.0,
    "fire": 9.0,
    # Objects
    "unattended_bag": 6.0,
    "bag": 3.0,
    "suspicious_package": 7.0,
    "unknown_object": 4.0,
    # People & crowds
    "crowd_cluster": 5.0,
    "person": 1.0,
    "suspicious_person": 6.0,
    "rushing_individual": 7.0,
    "protest_group": 5.0,
    # Vehicles
    "vehicle": 3.0,
    "unauthorized_vehicle": 7.0,
    "approaching_vehicle": 6.0,
    # Urban / political event labels
    "perimeter_breach": 8.0,
    "rooftop_figure": 8.0,
    "stage_rush": 9.0,
    "counter_surveillance": 6.0,
    "unauthorized_drone": 8.0,
    "barricade_breach": 7.0,
    "vip_threat": 9.0,
    "confrontation": 7.0,
    # Contraband / policy violations
    "alcohol": 3.0,
    "drugs": 5.0,
    "smoking": 2.0,
    "graffiti": 2.0,
    "trespassing": 5.0,
    "vandalism": 4.0,
}
DEFAULT_LABEL_WEIGHT = 2.0

# ── Risk-hint bonus weights ─────────────────────────────────────────────────
HINT_WEIGHTS: dict[str, float] = {
    "unattended": 3.0,
    "running": 2.0,
    "aggressive": 3.5,
    "loitering": 1.5,
    "in_restricted_zone": 4.0,
    "stationary_long": 2.0,
    "approaching_stage": 4.5,
    "breaching_perimeter": 5.0,
    "concealed_object": 3.5,
    "erratic_movement": 3.0,
    "climbing": 3.5,
    "near_vip": 4.0,
    "counter_flow": 2.5,
    "obscured_face": 2.0,
    "coordinated_movement": 3.0,
}
DEFAULT_HINT_WEIGHT = 1.0

# ── Scoring factors ──────────────────────────────────────────────────────────
CONFIDENCE_EXPONENT = 1.2        # how sharply low confidence reduces score
PROXIMITY_DECAY_PX = 500.0       # half-life in pixels for proximity decay
INSTRUCTION_MATCH_BOOST = 3.0    # flat bonus when object matches operator keywords

# ── Keyword catalogue for instruction parsing ────────────────────────────────
WATCHLIST_KEYWORDS: dict[str, list[str]] = {
    "weapon": ["weapon", "gun", "knife", "armed", "firearm", "rifle", "shooter"],
    "fight": ["fight", "fighting", "brawl", "altercation", "assault", "violence", "confrontation"],
    "unattended_bag": ["unattended bag", "abandoned bag", "suspicious bag", "unattended package", "abandoned package", "suspicious package"],
    "crowd_cluster": ["overcrowding", "crowd", "overcrowded", "stampede", "crush", "crowd surge", "crowd density"],
    "medical_emergency": ["medical", "injury", "injured", "unconscious", "collapse", "seizure"],
    "fire": ["fire", "smoke", "flames"],
    "restricted_zone": ["restricted", "restricted area", "restricted zone", "off-limits", "no-go zone", "perimeter breach", "perimeter", "barricade"],
    "theft": ["theft", "stealing", "pickpocket", "shoplifting", "robbery"],
    # Urban / political event keywords
    "stage_rush": ["stage rush", "rushing the stage", "rushing stage", "charging stage", "stage approach"],
    "perimeter_breach": ["perimeter breach", "breach", "fence breach", "barricade breach", "barrier breach", "break through"],
    "rooftop_figure": ["rooftop", "roof", "elevated position", "sniper", "overwatch", "high ground"],
    "suspicious_person": ["suspicious person", "suspicious individual", "suspicious behavior", "acting suspicious", "loitering"],
    "unauthorized_vehicle": ["unauthorized vehicle", "vehicle breach", "vehicle approaching", "rogue vehicle", "car approaching"],
    "unauthorized_drone": ["drone", "unauthorized drone", "rogue drone", "unknown aircraft", "uav"],
    "vip_threat": ["vip", "speaker", "official", "dignitary", "protectee", "principal"],
    "protest_group": ["protest", "protester", "demonstrator", "rally group", "agitator"],
    # Contraband / policy violations (operator can add these mid-session)
    "alcohol": ["alcohol", "drinking", "beer", "liquor", "bottle", "flask", "open container", "intoxicated", "drunk"],
    "drugs": ["drugs", "drug use", "narcotics", "smoking weed", "joint", "syringe", "needle", "paraphernalia"],
    "smoking": ["smoking", "cigarette", "vaping", "vape"],
    "trespassing": ["trespassing", "trespasser", "unauthorized entry", "sneaking in", "jumped fence"],
    "vandalism": ["vandalism", "graffiti", "property damage", "tagging", "spray paint"],
}

URGENCY_MODIFIERS: dict[str, float] = {
    "immediately": 2.0,
    "urgent": 1.8,
    "high priority": 1.5,
    "asap": 1.5,
    "critical": 2.0,
    "watch for": 1.0,
    "monitor": 0.8,
    "keep an eye on": 0.8,
}

# ── Action planning ──────────────────────────────────────────────────────────
MAX_ACTIONS = 12
TOP_N_OBJECTS = 8

# Severity thresholds (risk score → severity)
SEVERITY_THRESHOLDS: list[tuple[float, str]] = [
    (15.0, "CRITICAL"),
    (10.0, "HIGH"),
    (5.0, "MEDIUM"),
    (0.0, "LOW"),
]

# ── Alert routing ────────────────────────────────────────────────────────────
ALERT_NOTIFY_MAP: dict[str, list[str]] = {
    "CRITICAL": ["security", "authorities"],
    "HIGH": ["security"],
    "MEDIUM": ["event_staff", "security"],
    "LOW": ["event_staff"],
}
