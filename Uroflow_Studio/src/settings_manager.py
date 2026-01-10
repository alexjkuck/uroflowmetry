import json
import os
from pathlib import Path
from typing import Dict, Any
from datetime import datetime

#*******************************************************************
def get_settings_path()->Path:
    """
    --------------------------------------------------------------------
    get_settings_path()
    Returns the path where settings file should be stored

    OUTPUTS
    returns: Path object pointing to the settings file location

    (c) Kai Kuck 8-Jan-2026 20:45
    --------------------------------------------------------------------
    """
    settings_dir__primary = Path(r"C:\KaisDir\Dropbox\K0_Work\00_Elbeon\Elbeon_SkunkWorxx\UrineFlowmeter\Settings")
    settings_dir__fallback = Path("C:\\")
    
    if settings_dir__primary.exists():
        return settings_dir__primary / "UroSettings"
    else:
        return settings_dir__fallback / "UroSettings"
#*******************************************************************

#*******************************************************************
def get_default_settings()->Dict[str, Any]:
    """
    --------------------------------------------------------------------
    get_default_settings()
    Returns default settings dictionary

    OUTPUTS
    returns: Dictionary with default settings values

    (c) Kai Kuck 8-Jan-2026 20:45
    --------------------------------------------------------------------
    """
    # Try to get available ports, default to COM3 if unavailable
    default_com_port = "COM3"
    try:
        import serial.tools.list_ports
        ports = serial.tools.list_ports.comports()
        available_ports = [port.device for port in ports]
        if "COM3" in available_ports:
            default_com_port = "COM3"
        elif available_ports:
            default_com_port = available_ports[0]
    except:
        # If serial library not available, just use COM3
        pass
    
    return {
        "com_port": default_com_port,
        "baud_rate": 230400,
        "plot_time_length__sec": 180,
        "data_folder": r"C:\KaisDir\Dropbox\K0_Work\00_Elbeon\Elbeon_SkunkWorxx\UrineFlowmeter\Logging"
    }
#*******************************************************************

#*******************************************************************
def load_settings()->Dict[str, Any]:
    """
    --------------------------------------------------------------------
    load_settings()
    Loads settings from UroSettings file, or returns defaults if file doesn't exist

    OUTPUTS
    returns: Dictionary with settings values

    (c) Kai Kuck 8-Jan-2026 20:45
    --------------------------------------------------------------------
    """
    settings_path = get_settings_path()
    
    if settings_path.exists():
        try:
            with open(settings_path, 'r') as f:
                settings = json.load(f)
                # Validate and merge with defaults to ensure all keys exist
                default_settings = get_default_settings()
                for key in default_settings:
                    if key not in settings:
                        settings[key] = default_settings[key]
                return settings
        except (json.JSONDecodeError, IOError):
            # If file is corrupted, return defaults
            return get_default_settings()
    else:
        # File doesn't exist, return defaults and create file
        default_settings = get_default_settings()
        save_settings(default_settings)
        return default_settings
#*******************************************************************

#*******************************************************************
def save_settings(settings__dict: Dict[str, Any])->None:
    """
    --------------------------------------------------------------------
    save_settings()
    Saves settings dictionary to UroSettings file

    INPUTS
    settings__dict… Dictionary containing settings to save

    OUTPUTS
    None

    (c) Kai Kuck 8-Jan-2026 20:45
    --------------------------------------------------------------------
    """
    settings_path = get_settings_path()
    
    # Create directory if it doesn't exist (for primary location)
    settings_dir__primary = Path(r"C:\KaisDir\Dropbox\K0_Work\00_Elbeon\Elbeon_SkunkWorxx\UrineFlowmeter\Settings")
    if not settings_dir__primary.exists() and settings_path.parent == settings_dir__primary:
        try:
            settings_dir__primary.mkdir(parents=True, exist_ok=True)
        except (OSError, PermissionError):
            # If we can't create primary, fall back to C:\
            settings_path = Path("C:\\") / "UroSettings"
    
    try:
        with open(settings_path, 'w') as f:
            json.dump(settings__dict, f, indent=4)
    except (IOError, PermissionError):
        # If we can't write to primary, try fallback
        if settings_path.parent != Path("C:\\"):
            settings_path = Path("C:\\") / "UroSettings"
            with open(settings_path, 'w') as f:
                json.dump(settings__dict, f, indent=4)
#*******************************************************************

