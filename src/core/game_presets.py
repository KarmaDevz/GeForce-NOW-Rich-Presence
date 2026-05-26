import re
from typing import Tuple, Optional

# A rich dictionary of popular GeForce NOW games with English presets.
# Keys are stripped of non-alphanumeric characters to ensure maximum matching accuracy.
PRESETS = {
    # Valve & Shooters
    "counter strike 2": ("Competitive Match", "In a tactical firefight"),
    "counter strike global offensive": ("Competitive Match", "Defusing the bomb"),
    "dota 2": ("Ranked Match", "Defending the Ancient"),
    "fortnite": ("Battle Royale", "Riding the Battle Bus"),
    "apex legends": ("Apex Match", "Fighting for Champion status"),
    "destiny 2": ("Exploring the Solar System", "Executing a strike"),
    "tom clancys rainbow six siege": ("Ranked Match", "Breaching the objective"),
    "team fortress 2": ("Casual Match", "Pushing the cart"),
    "pubg battlegrounds": ("Survival Match", "Searching for loot"),
    "rust": ("Wasteland Survival", "Gathering resources"),
    "ark survival evolved": ("Dinosaur Island", "Taming a T-Rex"),
    "ark survival ascended": ("Island Survival", "Taming dinosaurs"),
    "dayz": ("Chernarus Survival", "Searching for clean water"),
    "squad": ("Tactical Operations", "Coordinating with the squad"),
    "hell let loose": ("World War II Frontline", "Defending the sector"),
    "insurgency sandstorm": ("Tactical Firefight", "Securing the objective"),
    "arma 3": ("Military Simulation", "Executing tactical orders"),
    "payday 2": ("Bank Heist", "Cracking the vault"),
    "payday 3": ("Heist Operation", "Executing a plan"),
    "ready or not": ("Swat Operations", "Clearing the building"),
    "left 4 dead 2": ("Campaign Survival", "Fighting the horde"),
    "killing floor 2": ("Zed Outbreak", "Surviving waves of Zeds"),

    # RPGs & Adventures
    "cyberpunk 2077": ("Night City", "Exploring the neon streets"),
    "the witcher 3 wild hunt": ("Monster Hunt", "Tracking the Wild Hunt"),
    "baldurs gate 3": ("Forgotten Realms", "Rolling a D20"),
    "hogwarts legacy": ("Hogwarts Castle", "Attending magic classes"),
    "starfield": ("Deep Space Exploration", "Surveying uncharted planets"),
    "fallout 4": ("Commonwealth Wasteland", "Modifying power armor"),
    "fallout 76": ("Appalachia Survival", "Rebuilding the wasteland"),
    "skyrim": ("Tamriel Adventure", "Fighting a dragon"),
    "the elder scrolls online": ("Exploring Tamriel", "In a dungeon raid"),
    "path of exile": ("Wraeclast Adventure", "Farming maps"),
    "warframe": ("Origin System", "Executing bullet jumps"),
    "monster hunter world": ("Astera Expedition", "Tracking a giant monster"),
    "monster hunter rise": ("Kamura Village", "Hunting with Palamute"),
    "stardew valley": ("Pelican Town", "Farming and socializing"),
    "hades": ("Underworld Escape", "Defeating the Furies"),
    "hades 2": ("Underworld Chronicles", "Casting magic spells"),
    "hollow knight": ("Hallownest Expedition", "Exploring deepnest"),
    "dead cells": ("The Island Dungeon", "Collecting cells"),
    "palworld": ("Palpagos Islands", "Catching wild Pals"),
    "genshin impact": ("Teyvat World", "Exploring beautiful landscapes"),
    "honkai star rail": ("Astral Express", "In a turn-based battle"),
    "assassins creed valhalla": ("Viking Age", "Raiding monasteries"),
    "assassins creed odyssey": ("Ancient Greece", "Sailing the Aegean Sea"),
    "assassins creed origins": ("Ancient Egypt", "Exploring pyramids"),
    "assassins creed mirage": ("Baghdad Streets", "Stalking from the shadows"),
    "far cry 5": ("Hope County", "Liberating outposts"),
    "far cry 6": ("Yara Revolution", "Causing guerrilla chaos"),
    "watch dogs legion": ("London Rebellion", "Hacking the city"),
    "mass effect legendary edition": ("Normandy Commander", "Saving the galaxy"),
    "dragon age inquisition": ("Thedas Chronicles", "Closing fade rifts"),
    "star wars jedi fallen order": ("Jedi Journey", "Restoring the Order"),
    "star wars jedi survivor": ("Jedi Survivor", "Evading the Empire"),
    "sifu": ("Vengeance Journey", "Mastering kung fu"),
    "no mans sky": ("Infinite Universe", "Warping to a new star system"),
    "outer wilds": ("Solar System Loop", "Solving ancient mysteries"),

    # Simulation, Strategy & Creative
    "euro truck simulator 2": ("European Highways", "Delivering cargo on time"),
    "american truck simulator": ("US Interstate Route", "Driving a big rig"),
    "cities skylines": ("Metropolis Builder", "Managing city traffic"),
    "cities skylines 2": ("Modern City Planning", "Expanding the power grid"),
    "satisfactory": ("Massive Factory", "Optimizing assembly lines"),
    "factorio": ("Automated Base", "The factory must grow"),
    "rimworld": ("Colony Survival", "Defending against raiders"),
    "hearts of iron 4": ("World War II Strategy", "Commanding divisions"),
    "europa universalis 4": ("Empire Building", "Managing diplomacy"),
    "crusader kings 3": ("Medieval Dynasty", "Plotting an inheritance"),
    "stellaris": ("Galactic Empire", "Surveying anomalies"),
    "subnautica": ("Ocean Planet 4546B", "Building a Seamoth"),
    "subnautica below zero": ("Frozen Ocean planet", "Surviving the arctic cold"),
    "phasmophobia": ("Ghost Hunting", "Identifying ghost types"),
    "lethal company": ("Industrial Moon", "Collecting scrap for the company"),
    "deep rock galactic": ("Hoxxes IV Caves", "Mining gold and nitra"),
    "vampire survivors": ("Stage Survival", "Evolving weapons"),
    "football manager 2024": ("Tactical Boardroom", "Adjusting team training"),
    "football manager 2023": ("Football Manager", "Managing team tactics"),
    "beamng drive": ("Physics Sandbox", "Tuning vehicle suspension"),
    "terraria": ("Sandbox Adventure", "Defeating the Wall of Flesh"),

    # Action, Racing & Sports
    "rocket league": ("Arena Match", "Executing an aerial goal"),
    "forza horizon 4": ("British Countryside", "Racing in beautiful seasons"),
    "forza horizon 5": ("Mexican Landscapes", "Driving a hypercar"),
    "sea of thieves": ("Pirate Legend", "Sailing on a galleon"),
    "dead by daylight": ("The Fog", "Surviving the trial"),
    "alan wake 2": ("Dark Place", "Shining the flashlight"),
    "control": ("The Oldest House", "Using telekinetic powers"),
    "death stranding": ("UCA Delivery", "Walking through BT territory"),
    "tomb raider": ("Ancient Tomb", "Solving puzzles"),
    "rise of the tomb raider": ("Siberian Wilderness", "Hunting wildlife"),
    "shadow of the tomb raider": ("Peruvian Jungle", "Stopping the apocalypse"),
    "hitman 3": ("World of Assassination", "Planning silent assassin"),
    "mount & blade 2 bannerlord": ("Calradia Campaign", "Leading cavalry charge"),
    "battlefield 5": ("World War II Battle", "Capturing flags"),
    "battlefield 1": ("World War I Trenches", "Defending the front"),
    "battlefield 2042": ("Future War", "Calling in vehicle drops"),
    "it takes two": ("Co-op Adventure", "Solving puzzle platforms"),
    "a way out": ("Prison Break", "Escaping the police"),
    "ghostrunner": ("Dharma Tower", "Slicing through guards"),
    "ghostrunner 2": ("Cyber Void", "Riding the motorcycle"),
}

def clean_game_name(name: str) -> str:
    """Cleans game name by stripping special characters, registered trademarks, etc."""
    c = name.lower()
    c = re.sub(r'[\u00ae\u2122]', '', c) # Strip ® and ™
    c = re.sub(r"[^a-z0-9\s]", " ", c)  # Replace hyphens, colons, apostrophes with spaces
    c = re.sub(r'\s+', ' ', c).strip()
    return c

def get_preset(game_name: str) -> Tuple[str, str]:
    """
    Returns (details, state) for the given game.
    If a preset doesn't exist, uses a smart generic generator in English.
    """
    cleaned = clean_game_name(game_name)
    
    # Try exact match first
    if cleaned in PRESETS:
        return PRESETS[cleaned]
    
    # Try substring match
    for k, v in PRESETS.items():
        if k in cleaned or cleaned in k:
            return v
            
    # Generic smart generator in English
    details = "In-Game"
    state = "Playing..."
    
    # Analyze name to generate a contextual state
    if "simulator" in cleaned:
        state = "Simulating..."
    elif "survival" in cleaned:
        state = "Surviving..."
    elif "manager" in cleaned:
        state = "Managing..."
    elif "tycoon" in cleaned:
        state = "Building empire..."
    elif "builder" in cleaned:
        state = "Constructing..."
    elif "war" in cleaned or "battle" in cleaned or "combat" in cleaned:
        state = "In battle..."
    elif "dead" in cleaned or "zombie" in cleaned or "resident evil" in cleaned:
        state = "Surviving the undead..."
    elif "racing" in cleaned or "speed" in cleaned or "drive" in cleaned or "rally" in cleaned or "forza" in cleaned:
        state = "Driving at high speed..."
    elif "hunt" in cleaned:
        state = "On the hunt..."
    elif "escape" in cleaned:
        state = "Escaping..."
    elif "space" in cleaned or "galaxy" in cleaned or "star" in cleaned:
        state = "Exploring the stars..."
        
    return details, state
