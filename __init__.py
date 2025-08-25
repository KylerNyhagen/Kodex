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
from .LodGenPluginDisabler import LodGenPluginDisabler
from functools import partial
import zipfile

class SupportReporter(mobase.IPluginTool):
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
        return "Scrolls of Schtevie - Support Plugin"

    def author(self) -> str:
        return "Kyler"

    def description(self) -> str:
        return "Provides critical support documentation to Scrolls of Schtevie staff to fix your problems!"

    def version(self) -> mobase.VersionInfo:
        return mobase.VersionInfo(0, 0, 7, mobase.ReleaseType.PRE_ALPHA)

    def tooltip(self) -> str:
        return "Export Support Documentation"
    
    # Settings
    def isActive(self) -> str:
        return self._organizer.managedGame().feature(mobase.GamePlugins)

    def settings(self) -> List[mobase.PluginSetting]:
        return [
            mobase.PluginSetting("enabled", "enable this plugin", True)
        ]

    # Display
    def displayName(self) -> str:
        return "Scrolls of Schtevie - Support Plugin"

   

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
        outputName = "Support_Dump.csv"
        outputPath = self._organizer.profilePath()
        outputLocation = outputPath + "/" + outputName
        modDetails = {}
        
        # Get All Mods by Priority
        allMods = self._modList.allModsByProfilePriority()
        # Loops through all mods, get versions and enabled state
        for mod in allMods:
            modMain = self._modList.getMod(mod)
            modVersion = modMain.version().canonicalString()
            # 2 = Bitwise for ACTIVE
            modEnabled = bool((self._modList.state(mod) & mobase.ModState.ACTIVE))
            qDebug(f"Mod found: {mod}, Version: {modVersion}, Enabled: {modEnabled}")
            mod_priority = self._modList.priority(mod)

            modDetails[mod] = {
                "name": mod,
                "version": modVersion,
                "enabled": modEnabled,
                "priority": mod_priority
            }

        # Grab the JoJ_Gold.csv and pull it's mod details - we need to compare to make sure there are no changes
        joj_gold_path = self._organizer.profilePath() + "/JoJ_Gold.csv"
        if not os.path.exists(joj_gold_path):
            qDebug(f"JoJ_Gold.csv not found at {joj_gold_path}")
            return False

        with open(joj_gold_path, "r", newline="", encoding="utf-8") as csvfile:
            reader = csv.DictReader(csvfile)
            for row in reader:
                mod_name = row["Mod Name"]
                if mod_name in modDetails:
                    modDetails[mod_name]["joj_gold"] = {
                        "version": row["Mod Version"],
                        "enabled": row["Is Enabled"],
                        "priority": row["Priority"]
                    }

        # Check to make sure all mod details line up with the joj_gold mod details
        for mod, details in modDetails.items():
            if "joj_gold" in details:
                joj_gold = details["joj_gold"]
                # Convert CSV values to appropriate types for comparison
                joj_gold_enabled = joj_gold["enabled"].lower() in ("true", "1", "yes")
                joj_gold_priority = int(joj_gold["priority"])
                qDebug(f"Comparing mod {mod}: Current Version: {details['version']}, JoJ_Gold Version: {joj_gold['version']}; Current Enabled: {details['enabled']}, JoJ_Gold Enabled: {joj_gold_enabled}; Current Priority: {details['priority']}, JoJ_Gold Priority: {joj_gold_priority}")
                if (joj_gold["version"] != details["version"])  :
                    modDetails[mod]["discrepancy_version"] = f"Current: {details['version']}, Correct: {joj_gold['version']}"
                if joj_gold_enabled != details["enabled"]:
                    modDetails[mod]["discrepancy_enabled"] = f"Current: {details['enabled']}, Correct: {joj_gold['enabled']}"
                if joj_gold_priority != details["priority"]:
                    modDetails[mod]["discrepancy_priority"] = f"Current: {details['priority']}, Correct: {joj_gold['priority']}"
            else:
                modDetails[mod]["custom_mod"] = "Custom Mod"

        # Obtain Users Hardware Specifications (GPU, VRAM, CPU, RAM)
        

        #Write out a CSV Reporting all mods and their discrepancies if exist:
        outputLocation = self._organizer.profilePath() + "/mod_discrepancies.csv"
        with open(outputLocation, "w", newline="", encoding="utf-8") as csvfile:
            writer = csv.writer(csvfile)
            # Write header
            writer.writerow(
                [
                    "Mod Name",
                    "Mod Version",
                    "Is Enabled",
                    "Priority",
                    "Custom Mod?",
                    "Version?",
                    "Enabled?",
                    "Priority?"
                ]
            )
            for mod, details in modDetails.items():
                writer.writerow(
                    [
                        details["name"],
                        details["version"],
                        details["enabled"],
                        details["priority"],
                        details.get("custom_mod", ""),
                        details.get("discrepancy_version", ""),
                        details.get("discrepancy_enabled", ""),
                        details.get("discrepancy_priority", "")
                    ]
                )

        # Generate a web page that displays the table and enables sorting the table by clicking the headers.
        htmlOutputLocation = self._organizer.profilePath() + "/mod_discrepancies.html"
        with open(htmlOutputLocation, "w", newline="", encoding="utf-8") as htmlfile:
            # Determine if any mod is a custom mod
            has_custom_mod = any(details.get("custom_mod", "") for details in modDetails.values())

            htmlfile.write("""<html>
        <head>
        <title>Mod Discrepancies</title>
        <style>
        body {
        background: #181818;
        color: #e0e0e0;
        font-family: 'Segoe UI', Arial, sans-serif;
        margin: 0;
        padding: 0;
        }
        .header-container {
        background: #222;
        padding: 32px 0 16px 0;
        text-align: center;
        border-bottom: 2px solid #990000;
        }
        .ascii-art {
        font-family: 'Courier New', monospace;
        font-size: 18px;
        color: #990000;
        line-height: 1.1;
        margin-bottom: 8px;
        white-space: pre;
        }
        .main-title {
        font-size: 2em;
        font-weight: bold;
        color: #e0e0e0;
        margin-bottom: 8px;
        letter-spacing: 2px;
        }
        .subtitle {
        font-size: 1.1em;
        color: #cccccc;
        margin-bottom: 16px;
        }
        table {
        border-collapse: collapse;
        width: 95%;
        margin: 32px auto 32px auto;
        background: #222;
        color: #e0e0e0;
        box-shadow: 0 0 12px #111;
        }
        th, td {
        border: 1px solid #444;
        padding: 8px 12px;
        text-align: left;
        }
        th {
        cursor: pointer;
        background: #333;
        color: #990000;
        transition: background 0.2s;
        }
        th:hover {
        background: #444;
        }
        tr:nth-child(even) {
        background: #242424;
        }
        tr:nth-child(odd) {
        background: #222;
        }
        tr:hover {
        background: #333;
        }
        .discrepancy-current {
        color: #ff3333;
        font-weight: bold;
        }
        /* Reduce width for certain columns */
        .mod-version-col { width: 120px; }
        .enabled-col { width: 80px; }
        .priority-col { width: 80px; }
        .custom-mod-col { width: 1%; white-space: nowrap; }
        </style>
        <script>
        function sortTableByColumn(tableId, colIndex) {
        var table = document.getElementById(tableId);
        var rows = Array.from(table.rows).slice(1);
        var asc = table.getAttribute("data-sort-dir") !== "desc";
        rows.sort(function(a, b) {
        var valA = a.cells[colIndex].innerText;
        var valB = b.cells[colIndex].innerText;
        if (!isNaN(valA) && !isNaN(valB)) {
            valA = Number(valA);
            valB = Number(valB);
        }
        return asc ? (valA > valB ? 1 : valA < valB ? -1 : 0) : (valA < valB ? 1 : valA > valB ? -1 : 0);
        });
        for (var i = 0; i < rows.length; i++) {
        table.tBodies[0].appendChild(rows[i]);
        }
        table.setAttribute("data-sort-dir", asc ? "desc" : "asc");
        }
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
            <div class="main-title">Scrolls of Schtevie - Support Diagnostic Report</div>
            <div class="subtitle">Comprehensive Mod Discrepancy Analysis</div>
        </div>
        <table id="modTable" border="1" data-sort-dir="asc">
        <tr>
        <th onclick="sortTableByColumn('modTable', 0)">Mod Name</th>
        <th class="mod-version-col" onclick="sortTableByColumn('modTable', 1)">Mod Version</th>
        <th class="enabled-col" onclick="sortTableByColumn('modTable', 2)">Is Enabled</th>
        <th class="priority-col" onclick="sortTableByColumn('modTable', 3)">Priority</th>
""")
            col_offset = 4
            if has_custom_mod:
                htmlfile.write('<th class="custom-mod-col" onclick="sortTableByColumn(\'modTable\', 4)">Custom Mod?</th>\n')
                col_offset += 1
            htmlfile.write(f"""<th onclick="sortTableByColumn('modTable', {col_offset})">Version?</th>
        <th onclick="sortTableByColumn('modTable', {col_offset+1})">Enabled?</th>
        <th onclick="sortTableByColumn('modTable', {col_offset+2})">Priority?</th>
        </tr>
""")
            for mod, details in modDetails.items():
                htmlfile.write("<tr>\n")
                htmlfile.write(f"<td>{details['name']}</td>\n")
                htmlfile.write(f"<td>{details['version']}</td>\n")
                htmlfile.write(f"<td>{details['enabled']}</td>\n")
                htmlfile.write(f"<td>{details['priority']}</td>\n")
                if has_custom_mod:
                    htmlfile.write(f"<td>{details.get('custom_mod', '')}</td>\n")
                # Highlight "Current: X" in red using a span
                def highlight_current(text):
                    if text and text.startswith("Current: "):
                        parts = text.split(",", 1)
                        if len(parts) == 2:
                            current_part = parts[0]
                            rest = parts[1]
                            current_value = current_part.replace("Current: ", "")
                            return f'<span class="discrepancy-current">Current: {current_value}</span>,{rest}'
                    return text or ""

                htmlfile.write(f"<td>{highlight_current(details.get('discrepancy_version', ''))}</td>\n")
                htmlfile.write(f"<td>{highlight_current(details.get('discrepancy_enabled', ''))}</td>\n")
                htmlfile.write(f"<td>{highlight_current(details.get('discrepancy_priority', ''))}</td>\n")
                htmlfile.write("</tr>\n")
            htmlfile.write("</table></body></html>\n")

        msgBox = QMessageBox()
        msgBox.setText(
            "Support Output is complete!\nYou can find your export at:\n\n"
            + outputLocation
        )
        msgBox.exec()



def createPlugins() -> List[mobase.IPlugin]:
    return [BackupOrganizer(), PluginExporter(), LodGenPluginDisabler(),  SupportReporter()]
