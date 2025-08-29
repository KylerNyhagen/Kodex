
import mobase
from typing import List

#from .BackupCompare import BackupCompare
#from .SupportReporter import SupportReporter
import mobase
import re
from typing import List
import csv
import os
from PyQt6.QtWidgets import QMessageBox
from PyQt6.QtGui import QIcon
from PyQt6.QtCore import qDebug, qInfo
import hashlib
import site
import xml.etree.ElementTree as ET
import subprocess
import glob
from PyQt6.QtCore import QUrl
from PyQt6.QtGui import QDesktopServices

site.addsitedir(os.path.join(os.path.dirname(__file__), "lib"))
from .lib import wmi


class SupportReporter(mobase.IPluginTool):
    _organizer: mobase.IOrganizer
    _modList: mobase.IModList
    _pluginList: mobase.IPluginList

    def __init__(self):
        super().__init__()

    def init(self, organizer: mobase.IOrganizer):
        self._organizer = organizer
        self._modList = organizer.modList()
        self._pluginList = organizer.pluginList()

        version = self._organizer.appVersion().canonicalString()
        versionx = re.sub("[^0-9.]", "", version)
        self._version = float(".".join(versionx.split(".", 2)[:-1]))
        return True

    # Basic info
    def name(self) -> str:
        return "Mod List Support Report for MO2"

    def author(self) -> str:
        return "Kyler"

    def icon(self):
        return QIcon()

    def description(self) -> str:
        return "Generates HTML File containing the current mod list, and flags any differences from the official list."
    def version(self) -> mobase.VersionInfo:
        return mobase.VersionInfo(1, 0, 0, mobase.ReleaseType.CANDIDATE)
    def tooltip(self) -> str:
        return "Export Support Documentation"
    # Settings
    def isActive(self) -> str:
        return self._organizer.managedGame().feature(mobase.GamePlugins)
    def settings(self) -> List[mobase.PluginSetting]:
        return [
            mobase.PluginSetting("enabled", "enable this plugin", True),
            # Color Picker for The CSS of the html report
            mobase.PluginSetting("Report Color", "color for the report", "#990000"),
            mobase.PluginSetting("Report Title", "title for the report", "Scrolls of Schtevie - Support Report")
        ]
    # Display
    def displayName(self) -> str:
        return "Generate Support Report"

    def get_file_hash(self, file_path):
        # Only stat/read if file exists
        if os.path.isfile(file_path):
            # Use memoryview for faster hash calculation
            with open(file_path, "rb") as f:
                chunk = f.read(65536)
                if not chunk:
                    hash_val = "EMPTY"
                else:
                    size_bytes = os.stat(file_path).st_size.to_bytes(8, "little")
                    hash_val = hashlib.md5(chunk + size_bytes).hexdigest()
        else:
            hash_val = "NOT_FOUND"

        return hash_val
    
    # Plugin Logic
    def display(self) -> bool:
        output_name = "support_output.html"
        output_path = self._organizer.profilePath()
        output_location = output_path + "/" + output_name
        managed_game = self._organizer.managedGame().gameName()
        recent_crash_logs = []
        if managed_game == "Skyrim Special Edition":
            # Get users my_documents Path
            try:
                # Windows API Coming in clutch.
                import ctypes.wintypes
                CSIDL_PERSONAL = 5 
                SHGFP_TYPE_CURRENT = 0
                buf = ctypes.create_unicode_buffer(ctypes.wintypes.MAX_PATH)
                ctypes.windll.shell32.SHGetFolderPathW(None, CSIDL_PERSONAL, None, SHGFP_TYPE_CURRENT, buf)
                my_documents = buf.value
            except Exception:
                # User is probably using linux
                my_documents = "N/A"
            if my_documents != "N/A":
                crash_log_dir = os.path.join(my_documents, "My Games", "Skyrim Special Edition", "SKSE")
                # Grab the last 3 most recent crash-*.log files
                recent_crash_logs = sorted(
                    glob.glob(os.path.join(crash_log_dir, "crash-*.log")),
                    key=os.path.getmtime,
                    reverse=True
                )[:3]
                for log in recent_crash_logs:
                    qDebug(f"Found crash log: {log}")

        # Get All Mods by Priority
        all_mods = self._modList.allModsByProfilePriority()
        all_plugins = self._pluginList.pluginNames()
        modlist_details = {}
        # Loops through all mods, get versions and enabled state
        for mod_name in all_mods:
            mod = self._modList.getMod(mod_name)

            mod_version = mod.version().canonicalString()
            # 2 = Bitwise for ACTIVE
            mod_is_enabled = bool((self._modList.state(mod_name) & mobase.ModState.ACTIVE))
            mod_priority = self._modList.priority(mod_name)
            qDebug(f"mod url for {mod_name}: {mod.nexusId()} {managed_game}")
            modlist_details[mod_name] = {
                "name": mod_name,
                "nexus_url": f"https://www.nexusmods.com/skyrimspecialedition/mods/{mod.nexusId()}" if managed_game == "Skyrim Special Edition" and mod.nexusId() > 0 else "",
                "version": mod_version,
                "enabled": mod_is_enabled,
                "priority": mod_priority,
                "mod_path": mod.absolutePath(),
                "plugin_hashes": {}
            }
            # Find the plugins associated with each mod based on _pluginlist.origin()
            mod_plugins = [plugin for plugin in all_plugins if self._pluginList.origin(plugin) == mod_name]

            # Collect plugin paths first, then batch stat/read to minimize IO overhead
            plugin_paths = []
            for plugin in mod_plugins:
                plugin
                plugin_path = os.path.join(mod.absolutePath(), plugin)
                plugin_paths.append((plugin, plugin_path))

            for plugin, plugin_path in plugin_paths:
                try:
                    hash_val = self.get_file_hash(plugin_path)
                except Exception as e:
                    hash_val = f"ERROR:{e}"
                modlist_details[mod_name]["plugin_hashes"][plugin] = hash_val
            modlist_details[mod_name]["plugins"] = mod_plugins

        


        # Grab the modlist_report_gold.csv and pull it's mod details - we need to compare to make sure there are no changes
        golden_modlist_path = self._organizer.profilePath() + "/modlist_report_gold.csv"
        if not os.path.exists(golden_modlist_path):
            return False

        with open(golden_modlist_path, "r", newline="", encoding="utf-8") as csvfile:
            reader = csv.DictReader(csvfile)
            for row in reader:
                mod_name = row["Mod Name"]
                if mod_name in modlist_details:
                    modlist_details[mod_name]["golden_data"] = {
                        "version": row["Mod Version"],
                        "enabled": row["Is Enabled"],
                        "priority": row["Priority"],
                        "plugin_hashes": row.get("Plugin Hashes", "")
                    }

        # Check to make sure all mod details line up with the golden_data mod details
        for mod_name, details in modlist_details.items():
            if "golden_data" in details:
                golden_data = details["golden_data"]
                # Convert CSV values to appropriate types for comparison
                golden_data_enabled = golden_data["enabled"].lower() in ("true", "1", "yes")
                golden_data_priority = int(golden_data["priority"])
                if (golden_data["version"] != details["version"]):
                    modlist_details[mod_name]["discrepancy_version"] = f"Current: {details['version']}, Correct: {golden_data['version']}"
                if golden_data_enabled != details["enabled"]:
                    modlist_details[mod_name]["discrepancy_enabled"] = f"Current: {details['enabled']}, Correct: {golden_data['enabled']}"
                if golden_data_priority != details["priority"]:
                    modlist_details[mod_name]["discrepancy_priority"] = f"Current: {details['priority']}, Correct: {golden_data['priority']}"

                # Compare plugin hashes
                golden_data_hashes = {}
                for pair in golden_data.get("plugin_hashes", "").split(";"):
                    if ":" in pair:
                        plugin, hash_val = pair.split(":", 1)
                        golden_data_hashes[plugin] = hash_val
                for plugin, current_hash in details.get("plugin_hashes", {}).items():
                    correct_hash = golden_data_hashes.get(plugin)
                    # Normalize empty or missing hashes for comparison
                    if not current_hash or current_hash in ("NOT_FOUND", "EMPTY"):
                        current_hash_norm = ""
                    else:
                        current_hash_norm = current_hash
                    if not correct_hash or correct_hash in ("NOT_FOUND", "EMPTY"):
                        correct_hash_norm = ""
                    else:
                        correct_hash_norm = correct_hash
                    if correct_hash is not None and current_hash_norm != correct_hash_norm:
                        if "discrepancy_plugin_hashes" not in modlist_details[mod_name]:
                            modlist_details[mod_name]["discrepancy_plugin_hashes"] = []
                        modlist_details[mod_name]["discrepancy_plugin_hashes"].append(
                            f"{plugin}: Current: {current_hash}, Correct: {correct_hash}"
                        )
            
            # If a mod has no golden data, either it's a custom mod, or no golden data exists period
            else:
                modlist_details[mod_name]["custom_mod"] = "Custom Mod"

        # Obtain Users Hardware Specifications (GPU, VRAM, CPU, RAM)

        #TODO See if I can improve this - there's a lot of libraries needed just to handle this
        c = wmi.WMI()
        hardware_info = {
            "GPU": None,
            "VRAM": None,
            "CPU": None,
            "RAM": None
        }

        gpus = c.Win32_VideoController()

        #AMD GPUs need special handling
        if gpus:
            # Try to find the most descriptive AMD GPU name
            amd_gpus = [gpu for gpu in gpus if "amd" in getattr(gpu, "Name", "").lower()]
            if amd_gpus:
                # Get the GPU not named "AMD Radeon(TM) Graphics". If there isn't one found, report "AMD Radeon(TM) Graphics"
                gpu = next((g for g in amd_gpus if "AMD Radeon(TM) Graphics" not in getattr(g, "Name", "")), amd_gpus[0])

                gpu_name = getattr(gpu, "Name", "Unknown")
                hardware_info["GPU"] = gpu_name
            else:
                hardware_info["GPU"] = getattr(gpus[0], "Name", "Unknown")


        # Use pynvml to get VRAM only if GPU is NVIDIA
        if hardware_info["GPU"] and "nvidia" in hardware_info["GPU"].lower():
            try:
                from .lib import pynvml
                pynvml.nvmlInit()
                vram_bytes = pynvml.nvmlDeviceGetMemoryInfo(pynvml.nvmlDeviceGetHandleByIndex(0)).total
                vram_gb = round(vram_bytes / (1024 ** 3), 2)
                hardware_info["VRAM"] = vram_gb
            except Exception as e:
                vram_gb = "Unknown"
                hardware_info["VRAM"] = vram_gb
        elif hardware_info["GPU"] and "amd" in hardware_info["GPU"].lower():
            try:                
                # Output a dxdiag text file - We have to wait for the file to exist before parsing it though - it takes a while
                # All AMD GPU Parsing python libraries do not support windows.
                import time
                # Output to profile path
                # Only run this if the dxdiag.xml doesn't already exist
                if not os.path.exists(os.path.join(self._organizer.profilePath(), 'dxdiag.xml')):
                    dxdiag_output = subprocess.Popen(f"dxdiag /x {os.path.join(self._organizer.profilePath(), 'dxdiag.xml')}", shell=True)
                    
                # There is no output from this command, the file just silently eventually gets created. Keep checking every now and then to see if there is a dxdiag.txt
                from PyQt6.QtCore import QThread, pyqtSignal

                # Separate thread to make sure it doesn't make MO2 appear non-responsive
                class DxdiagWaiter(QThread):
                    file_ready = pyqtSignal(str)

                    def __init__(self, file_path):
                        super().__init__()
                        self.file_path = file_path

                    def run(self):
                        while not os.path.exists(self.file_path):
                            time.sleep(1)
                        self.file_ready.emit(self.file_path)

                dxdiag_xml_path = os.path.join(self._organizer.profilePath(), 'dxdiag.xml')
                waiter = DxdiagWaiter(dxdiag_xml_path)

                # Create a blocking message box
                msg_box = QMessageBox()
                msg_box.setWindowTitle("Waiting for dxdiag.xml")
                msg_box.setText("AMD GPU Detected.\n Generating dxdiag.xml...\nPlease wait until the file is ready.\n This might take a couple seconds. Hang Tight!")
                msg_box.setStandardButtons(QMessageBox.StandardButton.NoButton)
                msg_box.setModal(True)

                def on_dxdiag_ready(path):
                    msg_box.accept()  # Close the message box

                waiter.file_ready.connect(on_dxdiag_ready)
                waiter.start()
                msg_box.exec()  # This blocks until msg_box.accept() is called

                waiter.file_ready.connect(on_dxdiag_ready)
                waiter.start()

                

                # Read dxdiag.xml
                tree = ET.parse(dxdiag_xml_path)
                root = tree.getroot()

                # Grab the DisplayDevice where CardName matches the GPU
                display_device = next((dev for dev in root.findall(".//DisplayDevice") if dev.find("CardName").text == hardware_info["GPU"]), None)
                #Get DedicatedMemory
                dedicated_memory = display_device.find("DedicatedMemory").text if display_device else "Unknown"
                # Memory is reported as "X MB" so convert to GB
                hardware_info["VRAM"] = round(int(dedicated_memory.split(" ")[0]) / 1024, 2) if dedicated_memory != "Unknown" else "Unknown"
                
            except Exception as e:
                hardware_info["VRAM"] = "Unknown"
        else:
            hardware_info["VRAM"] = "Unknown"
        
        # Get CPU Information. Really we just need the name.
        cpus = c.Win32_Processor()
        if cpus:
            hardware_info["CPU"] = cpus[0].Name
            
        ram = c.Win32_PhysicalMemory()
        if ram:
            # Report RAM in GB
            hardware_info["RAM"] = sum(int(ram_module.Capacity) for ram_module in ram) / (1024 ** 3) 

        page_file_get_size = c.Win32_PageFileUsage()
        #page_file_get_drive = c.Win32_PageFile()
        # Windows deprecated the only way to get the drive. That sucks.
        if page_file_get_size:
            page_File_size = sum(int(page.AllocatedBaseSize) for page in page_file_get_size)
            qDebug(f"Page File Size: {page_File_size / (1024 ** 3)} GB")
            hardware_info["Page File Size"] = page_File_size / (1024)
        
        import shutil

        # Get the total disk space and free disk space
        total, used, free = shutil.disk_usage(self._organizer.profilePath())
        hardware_info["Total Disk Space"] = total / (1024 ** 3)  # Convert to GB
        hardware_info["Used Disk Space"] = used / (1024 ** 3)    # Convert to GB
        hardware_info["Free Disk Space"] = free / (1024 ** 3)    # Convert to GB
        # Generate a web page that displays the table and enables sorting the table by clicking the headers.
        html_output_location = output_location
        with open(html_output_location, "w", newline="", encoding="utf-8") as htmlfile:
            # Determine if any mod is a custom mod
            has_custom_mod = any(details.get("custom_mod", "") for details in modlist_details.values())

            # Check if any mod has plugin hash discrepancies
            has_plugin_hash_discrepancy = any(
                details.get("discrepancy_plugin_hashes") for details in modlist_details.values()
            )
            # Get the Color
            report_color = self._organizer.pluginSetting(self.name(), "Report Color")
            report_title = self._organizer.pluginSetting(self.name(), "Report Title")
            # Write hardware info before the table
            
            # If you're this deep in the code and you see this...I'm sorry - Honestly, I have no idea how to make this clean while also being portable.
            # But hey, it works!
            def brighten_color(hex_color, factor=1.3):
                """Brighten a hex color by a given factor (default 1.3)."""
                from PyQt6.QtGui import QColor
                color = QColor(hex_color)
                r = min(int(color.red() * factor), 255)
                g = min(int(color.green() * factor), 255)
                b = min(int(color.blue() * factor), 255)
                return "#{:02x}{:02x}{:02x}".format(r, g, b)

            bright_report_color = brighten_color(report_color)

            # Use DataTables.js for fast client-side sorting, searching, and pagination
            htmlfile.write("""<html>
                    <head>
                    <title>Mod Discrepancies</title>
                    <link rel="stylesheet" type="text/css" href="https://cdn.datatables.net/1.13.6/css/jquery.dataTables.min.css"/>
                    <style>
                    body {{ 
                    background: #181818;
                    color: #e0e0e0;
                    font-family: 'Segoe UI', Arial, sans-serif;
                    margin: 0;
                    padding: 0;
                    }}
                    .header-container {{ 
                    background: #222;
                    padding: 32px 0 16px 0;
                    text-align: center;
                    border-bottom: 2px solid {bright_report_color};
                    }}
                    .ascii-art {{ 
                    font-family: 'Courier New', monospace;
                    font-size: 18px;
                    color: {bright_report_color};
                    line-height: 1.1;
                    margin-bottom: 8px;
                    white-space: pre;
                    }}
                    .main-title {{ 
                    font-size: 2em;
                    font-weight: bold;
                    color: #e0e0e0;
                    margin-bottom: 8px;
                    letter-spacing: 2px;
                    }}
                    .subtitle {{ 
                    font-size: 1.1em;
                    color: #cccccc;
                    margin-bottom: 16px;
                    }}
                    .hardware-info-container {{ 
                    background: #232323;
                    margin: 32px auto 0 auto;
                    width: 60%;
                    border-radius: 12px;
                    box-shadow: 0 0 8px #111;
                    padding: 24px 32px;
                    }}
                    .hardware-title {{ 
                    font-size: 1.3em;
                    font-weight: bold;
                    color: {bright_report_color};
                    margin-bottom: 12px;
                    letter-spacing: 1px;
                    }}
                    .hardware-list {{ 
                    list-style: none;
                    padding: 0;
                    margin: 0;
                    }}
                    .hardware-list li {{ 
                    padding: 8px 0;
                    border-bottom: 1px solid #333;
                    font-size: 1.05em;
                    }}
                    .hardware-list li:last-child {{ 
                    border-bottom: none;
                    }}
                    .hardware-label {{ 
                    font-weight: bold;
                    color: #e0e0e0;
                    margin-right: 8px;
                    }}
                    .table-container {{
                    width: 95%;
                    margin: 32px auto 32px auto;
                    background: #222;
                    box-shadow: 0 0 12px #111;
                    border-radius: 8px;
                    overflow-x: auto;
                    }}
                    table.dataTable {{ 
                    border-collapse: collapse;
                    width: 100%;
                    background: #222;
                    color: #e0e0e0;
                    }}
                    th, td {{ 
                    border: 1px solid #444;
                    padding: 8px 12px;
                    text-align: left;
                    }}
                    th {{ 
                    background: #333;
                    color: {bright_report_color};
                    transition: background 0.2s;
                    }}
                    tr:nth-child(even) {{ 
                    background: #242424;
                    }}
                    tr:nth-child(odd) {{ 
                    background: #222;
                    }}
                    tr:hover {{ 
                    background: #333;
                    }}
                    .discrepancy-current {{ 
                    color: #ff3333;
                    font-weight: bold;
                    }}
                    .separator-row {{ 
                    background: {bright_report_color} !important;
                    color: #ffffff !important;
                    font-weight: bold;
                    }}
                    .mod-version-col {{ width: 120px; }}
                    .enabled-col {{ width: 80px; }}
                    .priority-col {{ width: 80px; }}
                    .custom-mod-col {{ width: 1%; white-space: nowrap; }}
                    a {{ 
                    color: {bright_report_color};
                    text-decoration: underline;
                    transition: color 0.2s, text-decoration 0.2s;
                    }}
                    a:hover {{ 
                    color: #ff3333;
                    text-decoration: none;
                    }}
                    </style>
                    <script src="https://code.jquery.com/jquery-3.7.1.min.js"></script>
                    <script src="https://cdn.datatables.net/1.13.6/js/jquery.dataTables.min.js"></script>
                    <script>
                    $(document).ready(function() {{ 
                        $('#modTable').DataTable({{ 
                            "pageLength": -1,
                            "lengthMenu": [ [100, 250, 500, 1000, -1], [100, 250, 500, 1000, "All"] ],
                            "order": [],
                            "stateSave": true,
                            "scrollX": true,
                            "deferRender": true
                        }});
                    }});
                    </script>
                    </head>
                    <body>
                    <div class="header-container">
                        <div class="ascii-art">
                ██╗░░██╗░█████╗░██████╗░███████╗██╗░░██╗
                ██║░██╔╝██╔══██╗██╔══██╗██╔════╝╚██╗██╔╝
                █████═╝░██║░░██║██║░░██║█████╗░░░╚███╔╝░
                ██╔═██╗░██║░░██║██║░░██║██╔══╝░░░██╔██╗░
                ██║░╚██╗╚█████╔╝██████╔╝███████╗██╔╝╚██╗
                ╚═╝░░╚═╝░╚════╝░╚═════╝░╚══════╝╚═╝░░╚═╝
                        </div>
                        <div class="main-title">{report_title}</div>
                        <div class="subtitle">Comprehensive Mod List Analysis</div>
                    </div>
                    <div class="hardware-info-container">
                        <div class="hardware-title">User Hardware Information</div>
                        <ul class="hardware-list">
                            <li><span class="hardware-label">GPU:</span> {gpu}</li>
                            <li><span class="hardware-label">VRAM:</span> {vram} GB</li>
                            <li><span class="hardware-label">CPU:</span> {cpu}</li>
                            <li><span class="hardware-label">RAM:</span> {ram} GB</li>
                            <li><span class="hardware-label">Page File Size:</span> {page_file_size} GB</li>
                            <li><span class="hardware-label">Disk Space Usage:</span> {used_disk_space} / {total_disk_space} GB ({free_disk_space} GB free)</li>
                        </ul>
                    </div>
                    """.format(
                    bright_report_color=bright_report_color,
                    report_title=report_title,
                    gpu=hardware_info.get("GPU", "Unknown"),
                    vram=hardware_info.get("VRAM", "Unknown"),
                    cpu=hardware_info.get("CPU", "Unknown"),
                    ram=round(hardware_info.get("RAM", 0), 2) if isinstance(hardware_info.get("RAM", 0), (int, float)) else hardware_info.get("RAM", "Unknown"),
                    page_file_size=round(hardware_info.get("Page File Size", 0), 2) if isinstance(hardware_info.get("Page File Size", 0), (int, float)) else hardware_info.get("Page File Size", "Unknown"),
                    used_disk_space=round(hardware_info.get("Used Disk Space", 0), 2) if isinstance(hardware_info.get("Used Disk Space", 0), (int, float)) else hardware_info.get("Used Disk Space", "Unknown"),
                    total_disk_space=round(hardware_info.get("Total Disk Space", 0), 2) if isinstance(hardware_info.get("Total Disk Space", 0), (int, float)) else hardware_info.get("Total Disk Space", "Unknown"),
                    free_disk_space=round(hardware_info.get("Free Disk Space", 0), 2) if isinstance(hardware_info.get("Free Disk Space", 0), (int, float)) else hardware_info.get("Free Disk Space", "Unknown"),
                ))
            col_offset = 4
            if recent_crash_logs:
                htmlfile.write(f"""
                <div class="hardware-info-container crash-logs-container" style="margin-top:32px;">
                    <div class="hardware-title" style="margin-bottom:12px;">Recent Crash Logs</div>
                    <ul class="hardware-list" style="margin-bottom:0;">
                """)
                for log_path in recent_crash_logs:
                    try:
                        with open(log_path, "r", encoding="utf-8", errors="replace") as log_file:
                            log_content = log_file.read()
                    except Exception as e:
                        log_content = f"Could not read log: {e}"
                    log_name = os.path.basename(log_path)
                    htmlfile.write(f"""
                    <li style="padding:0;">
                        <details style="margin-bottom:12px;">
                            <summary style="font-weight:bold;color:{bright_report_color};cursor:pointer;">{log_name}</summary>
                            <pre style="background:#232323;color:#e0e0e0;padding:12px;border-radius:8px;max-height:400px;overflow:auto;font-size:0.95em;">{log_content}</pre>
                        </details>
                    </li>
                    """)
                htmlfile.write("</ul></div>") 
            # Wrap the table in a container to ensure header and body alignment
            htmlfile.write('<div class="table-container">\n')
            header_row = (
                '<table id="modTable" class="display" style="width:100%">\n'
                '<thead><tr>\n'
                '<th>Mod Name</th>\n'
                '<th class="mod-version-col">Mod Version</th>\n'
                '<th class="enabled-col">Is Enabled</th>\n'
                '<th class="priority-col">Priority</th>\n'
            )
            if has_custom_mod:
                header_row += f'<th class="custom-mod-col">Custom Mod?</th>\n'
                col_offset += 1
            header_row += (
                f'<th>Version?</th>'
                f'<th>Enabled?</th>'
                f'<th>Priority?</th>\n'
            )
            if has_plugin_hash_discrepancy:
                header_row += f'<th>Plugin Hash Discrepancies</th>\n'
            header_row += "</tr></thead>\n<tbody>\n"
            htmlfile.write(header_row)

            def highlight_current(text):
                if text and text.startswith("Current: "):
                    parts = text.split(",", 1)
                    if len(parts) == 2:
                        current_part = parts[0]
                        rest = parts[1]
                        current_value = current_part.replace("Current: ", "")
                        return f'<span class="discrepancy-current">Current: {current_value}</span>,{rest}'
                    return text or ""
                return text or ""

            for mod_name, details in modlist_details.items():
                is_separator = mod_name.endswith("_separator")
                row_class = "separator-row" if is_separator else ""
                if is_separator:
                    display_name = mod_name[:-10] + " - Separator"
                else:
                    nexus_url = details.get("nexus_url", "")
                    if nexus_url:
                        display_name = f'<a href="{nexus_url}" target="_blank">{details["name"]}</a>'
                    else:
                        display_name = details["name"]

                row_html = (
                    f'<tr{" class=\""+row_class+"\"" if row_class else ""}>\n'
                    f'  <td>{display_name}</td>\n'
                    f'  <td>{details["version"]}</td>\n'
                    f'  <td>{details["enabled"]}</td>\n'
                    f'  <td>{details["priority"]}</td>\n'
                )
                if has_custom_mod:
                    row_html += f"<td>{details.get('custom_mod', '')}</td>\n"
                row_html += (
                    f"<td>{highlight_current(details.get('discrepancy_version', ''))}</td>\n"
                    f"<td>{highlight_current(details.get('discrepancy_enabled', ''))}</td>\n"
                    f"<td>{highlight_current(details.get('discrepancy_priority', ''))}</td>\n"
                )
                if has_plugin_hash_discrepancy:
                    plugin_hashes = details.get("discrepancy_plugin_hashes", [])
                    if plugin_hashes:
                        row_html += "<td>"
                        row_html += "<br>".join(
                            highlight_current(hash_text) for hash_text in plugin_hashes
                        )
                        row_html += "</td>\n"
                    else:
                        row_html += "<td></td>\n"
                row_html += "</tr>\n"
                htmlfile.write(row_html)
            htmlfile.write("""
            </tbody></table>
            </div>
            <div style="width:100%;text-align:center;padding:24px 0 12px 0;color:#888;font-size:1em;">
                <hr style="margin-bottom:12px;border:0;border-top:1px solid #444;">
                Kodex Author: Kyler45, <a href="https://github.com/KylerNyhagen">GitHub</a>
                Kodex Version: 1.0.0
            </div>
            </body></html>
            """)

        msgBox = QMessageBox()
        msgBox.setText(
            "Support Output is complete!\nYou can find your export at:\n\n"
            + html_output_location
        )
        msgBox.setInformativeText("Open the file path below and provide this to your friendly support team!")
        msgBox.setStandardButtons(QMessageBox.StandardButton.Ok | QMessageBox.StandardButton.Cancel)
        msgBox.button(QMessageBox.StandardButton.Ok).setText("Open File")
        msgBox.button(QMessageBox.StandardButton.Cancel).setText("Open Folder")
        msgBox.button(QMessageBox.StandardButton.Cancel).clicked.connect(lambda: open_folder(html_output_location))
        msgBox.button(QMessageBox.StandardButton.Ok).clicked.connect(lambda: open_file(html_output_location))

        msgBox.exec()

def open_folder(text: str):
    # Open the html_output_location folder, highlight the file selected
    import sys
    
    # Make the file the selected file in windows explorer
    # Ensure the path is quoted correctly and explorer /select is used
    command = f'explorer /select,"{os.path.normpath(text)}"'
    subprocess.run(command, shell=True)



def open_file(file_path: str):
    # Opens the specified file using the default application
    QDesktopServices.openUrl(QUrl.fromLocalFile(file_path))


def createPlugin() -> mobase.IPlugin:
    return SupportReporter()