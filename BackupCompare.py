import mobase
import re
from typing import List
import csv
import os
from PyQt6.QtCore import qDebug, QtMsgType, qInstallMessageHandler, QMessageLogContext

try:
    from PyQt6.QtWidgets import QMessageBox
except ImportError:
    from PyQt5.QtWidgets import QMessageBox
class BackupCompare(mobase.IPluginTool):
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
        self.FileWindow = None
        version = self._organizer.appVersion().canonicalString()
        versionx = re.sub("[^0-9.]", "", version)
        self._version = float(".".join(versionx.split(".", 2)[:-1]))
        self._isMo2Updated = self._version >= 2.5
        return True

    # Basic info
    def name(self) -> str:
        return "Backup Comparison"

    def author(self) -> str:
        return "Kyler"

    def description(self) -> str:
        return "Compare's Modlist Backups to identify differences"

    def version(self) -> mobase.VersionInfo:
        return mobase.VersionInfo(0, 0, 1, mobase.ReleaseType.PRE_ALPHA)

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
    def displayName(self):
        return "Kodex of Kyler/Compare Backups"

    def tooltip(self) -> str:
        return "Exports Plugin List as CSV with Names and Flags"

    def icon(self):
        if self._isMo2Updated:
            from PyQt6.QtGui import QIcon
        else:
            from PyQt5.QtGui import QIcon

        return QIcon()

    # Plugin Logic
    def display(self) -> bool:
        
        # dialog = QFileDialog()
        # dialog.setFileMode(QFileDialog.FileMode.ExistingFiles)
        # dialog.setWindowTitle("Select Modlist Backups")
        # if dialog.exec():
        #     filenames = dialog.selectedFiles()
        #     for filename in filenames:
        #         qDebug(f"Selected backup file: {filename}")
        self.FileWindow = FileWindow()
# Class for file selection window
class FileWindow(QWidget):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.setWindowTitle('Select your MO2 Backups to Compare.')
        self.setGeometry(100, 100, 400, 100)

        layout = QGridLayout()
        self.setLayout(layout)

        # file selection
        file_browse = QPushButton('Browse')
        file_compare = QPushButton('Compare Backups')
        file_browse.clicked.connect(self.open_file_dialog)
        file_compare.clicked.connect(self.compare_files)

        self.file_list = QListWidget(self)

        layout.addWidget(QLabel('Selected Files:'), 0, 0)
        layout.addWidget(self.file_list, 1, 0, 1, 2)
        layout.addWidget(file_browse, 2, 0)
        layout.addWidget(file_compare, 2, 1)

        self.show()

    def open_file_dialog(self):
        filenames, _ = QFileDialog.getOpenFileNames(
            self,
            "Select Your MO2 Backups from your Profile(s) of choice"
        )
        if filenames:
            self.file_list.addItems([str(Path(filename))
                                     for filename in filenames])
    def compare_files(self):
        return True
