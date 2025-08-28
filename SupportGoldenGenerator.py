import mobase
import re
from typing import List
import csv
import os
from PyQt6.QtCore import qInfo
from PyQt6.QtWidgets import QMessageBox
from PyQt6.QtGui import QIcon
import hashlib
import site
import xml.etree.ElementTree as ET
import subprocess

site.addsitedir(os.path.join(os.path.dirname(__file__), "lib"))
from .lib import wmi

class SupportGoldenGenerator(mobase.IPluginTool):
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
        return "Mod List Author Golden Data Generator"

    def author(self) -> str:
        return "Kyler"

    def icon(self):
        return QIcon()

    def description(self) -> str:
        return "Generates the required data to compare against for support reporting doucmentation. \n\n Note: If you're not a mod list author, you probably don't need this plugin."
    def version(self) -> mobase.VersionInfo:
        return mobase.VersionInfo(1, 0, 0, mobase.ReleaseType.CANDIDATE)
    def tooltip(self) -> str:
        return "Generate Support Documentation Golden Comparison"
    # Settings
    def isActive(self) -> str:
        return self._organizer.managedGame().feature(mobase.GamePlugins)
    def settings(self) -> List[mobase.PluginSetting]:
        return [
            mobase.PluginSetting("enabled", "enable this plugin", True)
        ]
    # Display
    def displayName(self) -> str:
        return "Generate Support Report - GOLDEN"

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
        output_name = "modlist_report_gold.csv"
        output_path = self._organizer.profilePath()
        output_location = output_path + "/" + output_name
        
        
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

            modlist_details[mod_name] = {
                "name": mod_name,
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
                plugin_path = os.path.join(mod.absolutePath(), plugin)
                plugin_paths.append((plugin, plugin_path))

            for plugin, plugin_path in plugin_paths:
                try:
                    hash_val = self.get_file_hash(plugin_path)
                except Exception as e:
                    hash_val = f"ERROR:{e}"
                modlist_details[mod_name]["plugin_hashes"][plugin] = hash_val
            modlist_details[mod_name]["plugins"] = mod_plugins

        # Fire off a warning box informing the user what is about to happen - Only write if they confirm
        msgBox = QMessageBox()
        msgBox.setText("This will overwrite the existing golden mod list report.\n\n This should only be done if you are a mod list author updating the golden for a new list version.")
        msgBox.setInformativeText("Do you want to continue?")
        msgBox.setStandardButtons(QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        if msgBox.exec() != QMessageBox.StandardButton.Yes:
            return False

        with open(output_location, "w", newline="", encoding="utf-8") as csvfile:
            writer = csv.writer(csvfile)
            writer.writerow([
            "Mod Name",
            "Mod Version",
            "Is Enabled",
            "Priority",
            "Custom Mod",
            "Plugin Hashes"
            ])
            for mod_name, details in modlist_details.items():
                # Format plugin hashes as plugin1:hash;plugin2:hash;...
                plugin_hashes = details.get("plugin_hashes", {})
                plugin_hashes_str = ";".join(
                    f"{plugin}:{hash_val}" for plugin, hash_val in plugin_hashes.items()
                )
                row = [
                    details["name"],
                    details["version"],
                    details["enabled"],
                    details["priority"],
                    details.get("custom_mod", ""),
                    plugin_hashes_str
                ]
                writer.writerow(row)
            qInfo(f"Golden data CSV written to {output_location}")

        msgBox = QMessageBox()
        msgBox.setText(
            "Support Golden Generation is complete!\nYou can find your CSV at:\n\n"
            + output_location
        )
        msgBox.setStandardButtons(QMessageBox.StandardButton.Ok | QMessageBox.StandardButton.Cancel)
        msgBox.button(QMessageBox.StandardButton.Ok).setText("Open File")
        msgBox.button(QMessageBox.StandardButton.Cancel).setText("Close")
        msgBox.button(QMessageBox.StandardButton.Ok).clicked.connect(lambda: open_file(output_location))

        msgBox.exec()

def open_file(file_path):
    try:
        import subprocess
        subprocess.Popen(["notepad.exe", file_path])
    except Exception as e:
        qInfo(f"Failed to open file {file_path}: {e}")


def createPlugin() -> mobase.IPlugin:
    return SupportGoldenGenerator()