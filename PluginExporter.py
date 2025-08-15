import mobase
import re
from typing import List
import csv
import os


try:
    from PyQt6.QtWidgets import QMessageBox
except ImportError:
    from PyQt5.QtWidgets import QMessageBox


class PluginExporter(mobase.IPluginTool):
    _organizer: mobase.IOrganizer
    _modList: mobase.IModList
    _pluginList: mobase.IPluginList

    _isMo2Updated: bool

    def __init__(self):
        super().__init__()

    def init(self, organizer: mobase.IOrganizer):
        self._organizer = organizer
        self._modList = organizer.modList()
        self._pluginList = organizer.pluginList()

        version = self._organizer.appVersion().canonicalString()
        versionx = re.sub("[^0-9.]", "", version)
        self._version = float(".".join(versionx.split(".", 2)[:-1]))
        self._isMo2Updated = self._version >= 2.5
        return True

    # Basic info
    def name(self) -> str:
        return "Kyler Plugin Exporter"

    def author(self) -> str:
        return "Kyler"

    def description(self) -> str:
        return "Exports Plugin List as CSV with Names and Flags"

    def version(self) -> mobase.VersionInfo:
        return mobase.VersionInfo(0, 0, 7, mobase.ReleaseType.PRE_ALPHA)

    # Settings
    def isActive(self) -> str:
        return self._organizer.managedGame().feature(mobase.GamePlugins)

    def settings(self) -> List[mobase.PluginSetting]:
        return [
            mobase.PluginSetting("enabled", "enable this plugin", True)
            # Add Settings Later for file location etc...(this isnt working as expected yet for me)
            # mobase.PluginSetting("enabled", "enable this plugin", True),
            # mobase.PluginSetting("saveDestination", "Where to save file", "./profiles"),
            # mobase.PluginSetting("saveFileName", "What shall we call the file?", "LazyModlistExporter.csv"),
        ]

    # Display
    def displayName(self) -> str:
        return "Kodex of Kyler/Plugin Exporter"

    def tooltip(self) -> str:
        return "Exports Plugin List as CSV with Names and Flags"

    def icon(self):
        if self._isMo2Updated:
            from PyQt6.QtGui import QIcon
        else:
            from PyQt5.QtGui import QIcon

        return QIcon()


    def debugMsg(self, s):
        msgBox = QMessageBox()
        
        msgBox.setText(s)
        msgBox.exec()
        return

    # Plugin Logic
    def display(self) -> bool:
        # Define File Location
        outputName = "PluginExporter.csv"
        outputPath = self._organizer.profilePath()
        outputLocation = outputPath + "/" + outputName

        
        # Get All Mods by Priority
        allMods = self._modList.allModsByProfilePriority()

        # Get All Plugins
        allPlugins = self._pluginList.pluginNames()
        pluginDetails = {}
        for plugin in allPlugins:
            # Get plugin priority, flags, and origin
            ini_files = None
            priority = self._pluginList.priority(plugin)
            light_flag = self._pluginList.isLightFlagged(plugin)
            master_flag = self._pluginList.isMasterFlagged(plugin)
            plugins_origin = self._pluginList.origin(plugin)
            # Get mod associated with the plugin - Ignore data
            if plugins_origin is not "data":
                mod = self._modList.getMod(plugins_origin)
            # if name contains "unnofficial" or "unofficial":
            if mod is not None:
                    
                    #self.debugMsg(f"Mod for plugin {plugin} found: {mod.name()}")
                    # Check in the mods directory structure for ini files, but not meta.ini
                    ini_files = [f for f in os.listdir(mod.absolutePath()) if f.endswith('.ini') and f != 'meta.ini']
                    #self.debugMsg(f"INI files found for {mod.name()}: {ini_files}")
                
            # Add to list of dictionaries
            pluginDetails[plugin] = {
                "priority": priority,
                "name": plugin,
                "light_flag": light_flag,
                "master_flag": master_flag,
                "origin": plugins_origin,
                "has_ini_files": bool(ini_files),
                "ini_files": ini_files if ini_files else None
            }

        # loop through plugins and sort by priority
        allPlugins.sort(key=lambda x: pluginDetails[x]["priority"])
        # Write Header to CSV file using csv module
        with open(outputLocation, "w", newline="", encoding="utf-8") as csvfile:
            writer = csv.writer(csvfile)
            # Write header
            writer.writerow(
                [
                    "Priority",
                    "Plugin Name",
                    "Plugin Light Flag",
                    "Plugin Master Flag",
                    "Plugin Origin",
                    "Has INI Files",
                    "INI Files (if any)",
                ]
            )


            for plugin in allPlugins:
                    writer.writerow(
                        [
                            pluginDetails[plugin]["priority"],
                            pluginDetails[plugin]["name"],
                            pluginDetails[plugin]["light_flag"],
                            pluginDetails[plugin]["master_flag"],
                            pluginDetails[plugin]["origin"],
                            pluginDetails[plugin]["has_ini_files"],
                            pluginDetails[plugin]["ini_files"] if pluginDetails[plugin]["ini_files"] else "None"
                        ]
                    )
  
        msgBox = QMessageBox()
        msgBox.setText(
            "Plugin Export is complete!\nYou can find your export at:\n\n"
            + outputLocation
        )
        msgBox.exec()


# Tell Mod Organizer to initialize the plugin
def createPlugin() -> mobase.IPlugin:
    return PluginExporter()
