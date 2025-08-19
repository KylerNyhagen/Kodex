import datetime
import shutil
import mobase
import re
from typing import List
import csv
import os
from PyQt6.QtCore import qDebug, qCritical, qInfo
from pathlib import Path
#from .BackupCompare import BackupCompare
from PyQt6.QtWidgets import QMessageBox, QFileDialog, QApplication, QWidget, QGridLayout, QListWidget, QPushButton, QLabel, QTableWidget, QTableWidgetItem, QHBoxLayout, QInputDialog, QCheckBox
from PyQt6.QtGui import QIcon, QShortcut, QPixmap
from PyQt6.QtCore import QProcess, Qt
from .PluginExporter import PluginExporter
from .BackupOrganizer import BackupOrganizer
from functools import partial
import zipfile

class LodGenPluginDisabler(mobase.IPluginTool):
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
        return "Kyler's Plugin Disabler for Texgen/Dyndolod"

    def author(self) -> str:
        return "Kyler"

    def description(self) -> str:
        return "Allows toggling of plugins specified in settings for Texgen and Dyndolod. \n\nPlugins should be comma separated. e.g plugin1.esp,plugin2.esp"

    def version(self) -> mobase.VersionInfo:
        return mobase.VersionInfo(0, 0, 7, mobase.ReleaseType.PRE_ALPHA)

    def tooltip(self) -> str:
        return "Allows Toggling of plugins"
    
    # Settings
    def isActive(self) -> str:
        return self._organizer.managedGame().feature(mobase.GamePlugins)

    def settings(self) -> List[mobase.PluginSetting]:
        return [
            mobase.PluginSetting("enabled", "enable this plugin", True),
            mobase.PluginSetting("texgen_plugins", "List of plugins to disable for Textgen, comma separated", "JOJ - Cell Patch - Lair of Succubi.esp,SOS - Journal of Followers.esp,SOS - Alternate Perspective.esp"),
            mobase.PluginSetting("dyndolod_plugins", "List of plugins to disable for Dyndolod, comma separated", "JKs Castle Volkihar - Embers XD patch.esp,OCW_AMM-SE_FEPatch.esp,JOJ - City Patch - Markarth.esp,JOJ - OCW Atlas Map Marker Fix.esp,JOJ - Cell Patch - Lair of Succubi.esp,SOS - Journal of Followers.esp,SOS - Alternate Perspective.esp"),
            mobase.PluginSetting("auto_disable", "Automatically disable plugins on tool run", False),
        ]

    # Display
    def displayName(self) -> str:
        return "Kodex of Kyler/Toggle Lod Gen Plugins"

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
        texgen_plugins = self._organizer.pluginSetting(self.name(), "texgen_plugins")
        qDebug(f"Texgen Plugins: {texgen_plugins}")

        #Pop Dialog Box asking user which plugins 

        msgBox = QMessageBox()
        msgBox.setText("Which plugins would you like to disable?")
        msgBox.setStandardButtons(
            QMessageBox.StandardButton.Cancel
        )
        texgen_btn = msgBox.addButton("TexGen", QMessageBox.ButtonRole.ActionRole)
        dyndolod_btn = msgBox.addButton("DynDOLOD", QMessageBox.ButtonRole.ActionRole)
        both_btn = msgBox.addButton("ENABLE Both", QMessageBox.ButtonRole.ActionRole)

        def disable_plugins(plugins_type: str):
            plugins = self._organizer.pluginSetting(self.name(), f"{plugins_type}").split(",")
            not_found = []
            # loop through plugins.txt manually - Bethesda Plugin Manager prevents using the API calls..
            plugins_txt_path = Path(self._organizer.profilePath()) / "plugins.txt"
            if plugins_txt_path.exists():
                plugins_to_disable = [p.strip() for p in plugins]
                found_plugins = []
                lines = []
                with plugins_txt_path.open("r", encoding="utf-8") as f:
                    for line in f:
                        orig_line = line.rstrip('\n')
                        line_stripped = orig_line.lstrip('*').strip()
                        if line_stripped in plugins_to_disable:
                            qDebug(f"Found plugin to disable: {line_stripped}")
                            found_plugins.append(line_stripped)
                            # Remove '*' to disable - keep the line in the same location it was.
                            lines.append(line_stripped)
                        else:
                            lines.append(orig_line)
                # Write back the modified plugins.txt if not found is empty
                not_found = [p for p in plugins_to_disable if p not in found_plugins]
                if not_found:
                    warning_msg = "The following plugins were not found:\n\n" + "\n".join(not_found) + "\n\nIt is recommended you figure out what is going on before continuing.\n Perhaps a plugin name changed?\n\n ===For your safety, all plugins found will be re-enabled.==="
                    QMessageBox.warning(None, "Plugin(s) Not Found", warning_msg,)
                else:
                    with plugins_txt_path.open("w", encoding="utf-8") as f:
                        for l in lines:
                            f.write(l + "\n")
                    QMessageBox.information(None, "Success", "The following plugins were sucessfully disabled: \n\n" + "\n".join(plugins))
            self._organizer.refresh()
          

        def enable_plugins(plugins_type: str):
            plugins = self._organizer.pluginSetting(self.name(), plugins_type).split(",")
            # loop through plugins.txt manually - Bethesda Plugin Manager prevents using the API calls..
            plugins_txt_path = Path(self._organizer.profilePath()) / "plugins.txt"
            if plugins_txt_path.exists():
                plugins_to_enable = [p.strip() for p in plugins]
                found_plugins = []
                lines = []
                with plugins_txt_path.open("r", encoding="utf-8") as f:
                    for line in f:
                        orig_line = line.rstrip('\n')
                        line_stripped = orig_line.lstrip('*').strip()
                        if line_stripped in plugins_to_enable:
                            qDebug(f"Found plugin to enable: {line_stripped}")
                            found_plugins.append(line_stripped)
                            # Add '*' to enable - keep the line in the same location it was.
                            lines.append(f"*{line_stripped}")
                        else:
                            lines.append(orig_line)
                # Write back the modified plugins.txt if not found is empty
                not_found = [p for p in plugins_to_enable if p not in found_plugins]
                if not_found:
                    warning_msg = "The following plugins were not found:\n\n" + "\n".join(not_found) + "\n\nIt is recommended you figure out what is going on before continuing.\n Perhaps a plugin name changed?\n\n ===For your safety, all plugins found will be re-enabled.==="
                    QMessageBox.warning(None, "Plugin(s) Not Found", warning_msg,)
                else:
                    with plugins_txt_path.open("w", encoding="utf-8") as f:
                        for l in lines:
                            f.write(l + "\n")

        def enable_both_plugins():
            enable_plugins("texgen_plugins")
            enable_plugins("dyndolod_plugins")
            QMessageBox.information(None, "Success", "All plugins were re-enabled.")
            self._organizer.refresh()



        texgen_btn.clicked.connect(lambda: disable_plugins("texgen_plugins"))
        dyndolod_btn.clicked.connect(lambda: disable_plugins("dyndolod_plugins"))
        both_btn.clicked.connect(enable_both_plugins)
        msgBox.setDefaultButton(QMessageBox.StandardButton.Cancel)
        msgBox.exec()

# Tell Mod Organizer to initialize the plugin
def createPlugin() -> mobase.IPlugin:
    return LodGenPluginDisabler()
