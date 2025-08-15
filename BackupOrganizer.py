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
from PyQt6.QtGui import QIcon, QShortcut
from PyQt6.QtCore import QProcess, Qt
from .PluginExporter import PluginExporter
from functools import partial
import zipfile

class BackupOrganizer(mobase.IPluginTool):
    _organizer: mobase.IOrganizer
    _modList: mobase.IModList
    _pluginList: mobase.IPluginList

    _isMo2Updated: bool

    def __init__(self):
        self.__parentWidget = None
        super().__init__()

    def init(self, organizer: mobase.IOrganizer):
        self._organizer = organizer
        self._modList = organizer.modList()
        self._pluginList = organizer.pluginList()
        # When the MO2 gui is opened, add the buttons to the GUI
        self._organizer.onUserInterfaceInitialized(lambda window: self.add_buttons_to_gui(window))
        self.FileWindow = None
        return True
    
    def add_buttons_to_gui(self, parent):
        """
        Adds buttons to the MO2 GUI for managing backups.
        Parameters:
        - parent: The parent widget to which the buttons will be added.
        """
        # Check if the parent widget has changed. If so, update it.
        if self.__parentWidget != parent:
            self.__parentWidget = parent

        # Get the icon path for the backup manager button
        # TODO - Make this a separate function in a separate python file - Other plugins are going to utilise this
        backup_manager_icon_path: str = self._organizer.pluginDataPath().replace('plugins/data', 'plugins/Kodex/Kodex Icons/backup_manager_icon.ico')

        manage_backups_button = self.create_button(backup_manager_icon_path, "Manage Backups", lambda _: self.display(), 'm')
        
        # Use MO2 mainwindow.ui to add a button next to the backups for opening the backup manager.
        # TODO - Delete the old MO2 buttons

        # All of these conditionals are in place to prevent exploding if the MO2 GUI changes - If any of these fail, we just don't add the custom button.
        central_widget = self._parentWidget().findChild(QWidget, 'centralWidget')
        if central_widget:
            categories_splitter = central_widget.findChild(QWidget, 'categoriesSplitter')
            if categories_splitter:
                splitter = categories_splitter.findChild(QWidget, 'splitter')
                if splitter:
                    layout_widget = splitter.findChild(QWidget, 'layoutWidget')
                    if layout_widget:
                        layout = layout_widget.layout()
                        hlayout: QHBoxLayout = layout.children()[0]
                        # Only insert the manage backups button if it doesn't already exist. Not doing this check results in the button showing up on plugin_reload again
                        exists = False
                        for i in range(hlayout.count()):
                            widget = hlayout.itemAt(i).widget()
                            if widget is not None and isinstance(widget, QPushButton) and widget.toolTip() == "Manage Backups":
                                exists = True
                                break

                        if not exists:
                            hlayout.insertWidget(hlayout.count() - 2, manage_backups_button)
                            #TODO - Delete old create and restore backup buttons here
    
    def create_button(self, icon_path, tool_tip, function, list_type):
        button = QPushButton()
        button.setIcon(QIcon(icon_path))
        button.setToolTip(tool_tip)
        button.clicked.connect(lambda: function(list_type))
        return button
    # Basic info
    def name(self) -> str:
        return "Backup Manager"

    def author(self) -> str:
        return "Kyler"

    def description(self) -> str:
        return "View and annotate MO2 Backups"

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
        return "Kodex of Kyler/Backup Manager"

    def tooltip(self) -> str:
        return "Lists existing MO2 backups and allows annotation"

    def icon(self):
        from PyQt6.QtGui import QIcon

        return QIcon()

    # Plugin Logic
    def display(self) -> bool:
        
        # Check if an existing backup_descriptions CSV exists. If not, create it. Headers are name and description
        self.file_descriptions = {}
        self.csv_file = Path(self._organizer.profilePath()) / "backup_descriptions.csv"

        # If it doesn't exist, create it with the headers and modlist.txt being set up as Main List - DO NOT MODIFY as the description    
        if not self.csv_file.exists():
            with open(self.csv_file, "w", newline="", encoding="utf-8") as f:
                writer = csv.writer(f)
                writer.writerow(["File Name", "Description"])
                writer.writerow(["modlist.txt", "Main List - DO NOT MODIFY"])
        
        # Create a temporary FileWindow just to use its method to get file descriptions. Prevents Code Reuse
        temp_window = FileWindow(self._organizer.profilePath(), {}, self.csv_file, self._organizer)
        self.file_descriptions = temp_window.get_updated_file_descriptions()
        # Close the temporary window since we don't need it displayed
        temp_window.close()
        
        # Pass profile path and organizer to FileWindow
        self.FileWindow = FileWindow(self._organizer.profilePath(), self.file_descriptions, self.csv_file, self._organizer)


# Class for file selection window
class FileWindow(QWidget):

    def __init__(self, profile_path, file_descriptions, csv_file, organizer, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.profile_path = profile_path
        self.file_descriptions = file_descriptions
        self.csv_file = csv_file
        self._organizer = organizer

        self.setWindowTitle('Mod Organizer 2 Modlist Backups')
        layout = QGridLayout()
        self.setLayout(layout)
        # Create and display table of generic example items
        self.table = QTableWidget(self)
        self.table.setColumnCount(5)
        self.table.setHorizontalHeaderLabels(['File Name', 'File Size', 'Date Modified', "Description (Double Click to Edit)", 'Actions'])
        # Have the last column stretch to fill the space
        self.table.horizontalHeader().setStretchLastSection(True)
        layout.addWidget(self.table, 0, 0, 1, 2)

        #Add some generic example data - Content in "Actions" is a button named "Set Description"

        # Load all backups
        self.load_backups()
        self.resize(self.table.horizontalHeader().length() + 80, self.table.verticalHeader().length() + self.table.horizontalHeader().height() + 80)
        

        # Add button at the bottom for "Create Complete Backup", "Create Modlist Backup", "Create Plugin List Backup"
        # Create a horizontal layout for the backup buttons
        button_layout = QHBoxLayout()
        create_complete_backup_button = QPushButton("Create Complete Backup", self)
        # Add a question mark button next to the complete backup button
        help_button = QPushButton("?", self)
        help_button.setFixedWidth(24)
        help_button.setToolTip("Click for help")

        

        def show_backup_help():
            QMessageBox.information(
            self,
            "Complete Backup Help",
            '''This will create a complete backup of your profile, which includes:
    - Modlist (Left panel of MO2) enabled mods and order
    - Plugin List (Right Panel "Plugins") enabled and order
    - Load Order
    - Locked Order (Any plugins with locked load order)'''
            )

        help_button.clicked.connect(show_backup_help)

        # Add both buttons to the layout
        button_layout.addWidget(help_button)
        button_layout.addWidget(create_complete_backup_button)
        
        create_modlist_backup_button = QPushButton("Create Modlist Backup", self)
        create_plugin_list_backup_button = QPushButton("Create Plugin List/Load Order Backup", self)

        button_layout.addWidget(create_modlist_backup_button)
        button_layout.addWidget(create_plugin_list_backup_button)

        # Put the button layout in a dedicated widget to prevent it from moving around on resize
        button_widget = QWidget(self)
        button_widget.setLayout(button_layout)
        layout.addWidget(button_widget, 1, 0, 1, 2)

        create_complete_backup_button.clicked.connect(self.create_complete_backup)
        create_modlist_backup_button.clicked.connect(self.create_modlist_backup)
        create_plugin_list_backup_button.clicked.connect(self.create_plugin_list_backup)

        # Add a checkbox for "Show only complete backups" that filters out everything other than the backup zips from the table.
        self.show_complete_backups_checkbox = QCheckBox("Show only complete backups", self)
        self.show_complete_backups_checkbox.setChecked(True)
        self.filter_table()
        self.show_complete_backups_checkbox.toggled.connect(self.filter_table)
        layout.addWidget(self.show_complete_backups_checkbox, 2, 0, 1, 2)

        self.show()

    def filter_table(self):
        """
        Filters the table based on the "Show only complete backups" checkbox.
            - By default, only complete backups are shown.
            - TODO - See if we can remember the users choice
        """
        # Get the current state of the checkbox
        show_complete = self.show_complete_backups_checkbox.isChecked()
        for row in range(self.table.rowCount()):
            item = self.table.item(row, 0)
            if item:
                # Check if the item is a complete backup
                is_complete_backup = item.text().startswith("backup_")
                # Show or hide the row based on the checkbox state
                self.table.setRowHidden(row, show_complete and not is_complete_backup)

    def create_complete_backup(self):
        """
            Creates a complete backup of the MO2 instance.
                Internally this creates copies of the following files:
                    - modlist.txt
                    - loadorder.txt
                    - lockedorder.txt
                    - plugins.txt
            These are stored in a zip folder under "Custom backups"
        """
        qInfo("Creating Complete backup...")
        # Get all files required to perform a complete backup
        loadorder_path = Path(self.profile_path) / "loadorder.txt"
        lockedorder_path = Path(self.profile_path) / "lockedorder.txt"
        plugins_path = Path(self.profile_path) / "plugins.txt"
        modlist_path = Path(self.profile_path) / "modlist.txt"
        # Create a complete_backups directory if it doesn't exist
        complete_backups_dir = Path(self.profile_path) / "complete_backups"
        complete_backups_dir.mkdir(exist_ok=True)
        # Copy all files in to a folder within complete_backups and zip that folder.
        with zipfile.ZipFile(complete_backups_dir / f"backup_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.zip", 'w') as zipf:
            zipf.write(loadorder_path, arcname="loadorder.txt")
            zipf.write(lockedorder_path, arcname="lockedorder.txt")
            zipf.write(plugins_path, arcname="plugins.txt")
            zipf.write(modlist_path, arcname="modlist.txt")
        # Refresh the table view to show new backup
        self.refresh_table()
    
    def refresh_table(self):
        """
        Refreshes the table view to show the latest backup information.
        """
        # Clear rows
        self.table.setRowCount(0)
        # Load all backups, including any new ones        
        self.load_backups()
        # Reapply filtering if the checkbox is checked
        if self.show_complete_backups_checkbox.isChecked():
            self.filter_table()

    def get_updated_file_descriptions(self):
        """
            Reloads the file descriptions from the CSV file.
            This is required whenever new backups are loaded, otherwise the descriptions may be outdated.

            Returns:
                A dictionary mapping file names to their descriptions.
        """
        # Reload the file descriptions from the CSV file
        file_descriptions = {}
        if self.csv_file.exists():
            with open(self.csv_file, "r", encoding="utf-8") as f:
                reader = csv.reader(f)
                next(reader, None)  # Skip header
                for row in reader:
                    if len(row) == 2:
                        file_descriptions[row[0]] = row[1]
        return file_descriptions
    def load_backups(self):
        """
            Loads all backup files from the profile directory and updates the table view.
            Grabs file name, size, date, and description.

            # TODO - Implement plugins.txt backups
        """

        # Also, look for backup zips in the complete_backups folder if it exists
        # First, find modlist.txt* files in the profile path
        backup_data = []

        self.file_descriptions = self.get_updated_file_descriptions()
        for file in Path(self.profile_path).glob("modlist.txt*"):
            if file.name.endswith(".bak"):
                continue
            file_name = file.name
            file_size = file.stat().st_size
            file_size_kb = file_size / 1024
            file_size_str = f"{file_size_kb:.2f} KB"
            file_date = file.stat().st_mtime
            file_date = datetime.datetime.fromtimestamp(file_date).strftime("%Y-%m-%d %H:%M:%S")
            if file_name in self.file_descriptions:
                backup_data.append((file_name, file_size_str, file_date, self.file_descriptions[file_name]))
            else:
                backup_data.append((file_name, file_size_str, file_date, None))

        # Now, look for backup zip files in the complete_backups folder
        complete_backups_dir = Path(self.profile_path) / "complete_backups"
        if complete_backups_dir.exists():
            for zip_file in complete_backups_dir.glob("*.zip"):
                file_name = zip_file.name
                file_size = zip_file.stat().st_size
                file_size_kb = file_size / 1024
                file_size_str = f"{file_size_kb:.2f} KB"
                file_date = zip_file.stat().st_mtime
                file_date = datetime.datetime.fromtimestamp(file_date).strftime("%Y-%m-%d %H:%M:%S")
                # Use description if available
                if file_name in self.file_descriptions:
                    backup_data.append((file_name, file_size_str, file_date, self.file_descriptions[file_name]))
                else:
                    backup_data.append((file_name, file_size_str, file_date, None))
        self.table.setRowCount(len(backup_data))

        # Populate the table with backup data
        for row, (name, size, date, desc) in enumerate(backup_data):
            self.table.setItem(row, 0, QTableWidgetItem(name))
            self.table.setItem(row, 1, QTableWidgetItem(str(size)))
            self.table.setItem(row, 2, QTableWidgetItem(str(date)))
            self.table.setItem(row, 3, QTableWidgetItem(desc))
            restore_backup_button = QPushButton("Restore Backup", self)
            delete_backup_button = QPushButton("Delete Backup", self)
            #Clear and set description buttons will be in the same cell
            action_layout = QHBoxLayout()
            action_layout.addWidget(restore_backup_button)
            action_layout.addWidget(delete_backup_button)
            action_widget = QWidget()
            action_widget.setLayout(action_layout)
            self.table.setCellWidget(row, 4, action_widget)
            # If set description is clicked, open a dialog to set the description
            restore_backup_button.clicked.connect(partial(self.restore_backup, row, name))
            delete_backup_button.clicked.connect(partial(self.delete_backup, row, name))

        # Make sure table columns and rows are fitted
         # Connect double click signal once and handle both actions in one slot
        self.table.itemDoubleClicked.connect(self.handle_double_click)

        # No rows should be editable by clicking
        for row in range(self.table.rowCount()):
            for col_idx in range(self.table.columnCount()):
                item = self.table.item(row, col_idx)
                if item:
                    item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
        self.table.resizeColumnsToContents()
        self.table.resizeRowsToContents()


    def delete_backup(self, row, name):
        """
            Delete a backup, identified by its row and name, and refresh the table

            Returns:
                None
        """
        qDebug(f"Deleting backup for {name} in {row}")
        # Pop up a confirmation dialog
        reply = QMessageBox.question(
            self,
            'Confirm Delete',
            f"Are you sure you want to delete the backup for {name}? This action cannot be undone.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )
        if reply == QMessageBox.StandardButton.No:
            return
        # Delete the backup file
        # if name is a complete backup, path will be <profile_path>/complete_backups/<name>, otherwise it will be <profile_path>/backups/<name>
        if name.startswith("backup_"):
            path_to_backup = Path(self.profile_path) / "complete_backups" / f"{name}"
        else:
            path_to_backup = Path(self.profile_path) / f"{name}"
        if path_to_backup.exists():
            path_to_backup.unlink()
        else:
            qDebug(f"Backup file not found: {path_to_backup}")
        # Refresh the table
        self.refresh_table()

    def create_modlist_backup(self):
        qDebug("Creating modlist backup...")
        # Implement modlist backup creation logic here

    def create_plugin_list_backup(self):
        qDebug("Creating plugin list backup...")
        # Implement plugin list backup creation logic here

    def open_file_in_notepad(self, row):
        """
            Open the specified backup file in Notepad++ or Notepad for editing.

            No, I am not adding support for Linux. You use Linux, do it yourself.
        """
        name = self.table.item(row, 0).text()
        notepad_path = Path("C:/Program Files/Notepad++/notepad++.exe")
        if notepad_path.exists():
            QProcess.startDetached(str(notepad_path), [str(Path(self.profile_path) / name)])
        # If notepad++ is not found, use basic notepad
        else:
            notepad_path = Path("C:/Windows/System32/notepad.exe")
            if notepad_path.exists():
                QProcess.startDetached(str(notepad_path), [str(Path(self.profile_path) / name)])
            else:
                qCritical(f"Notepad not found at {notepad_path}. How...How did you move Notepad? It's in System32.")

    def open_complete_backup_in_file_explorer(self, row):
        """
            Open the specified complete backup folder in the file explorer.

            Again, no, I'm not supporting Linux.

            Returns:
                None
        """
        name = self.table.item(row, 0).text()
        complete_backup_path = Path(self.profile_path) / "complete_backups" / name
        if complete_backup_path.exists():
            QProcess.startDetached("explorer.exe", [str(complete_backup_path)])
        else:
            qCritical(f"Complete backup folder not found: {complete_backup_path}")

    def restore_backup(self, row, name):
        qDebug(f"Restoring backup for {name} in {row}")
        # Pop up a confirmation dialog
        reply = QMessageBox.question(
            self,
            'Confirm Restore',
            f"Are you sure you want to restore the backup for {name}? This action cannot be undone.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )
        if reply == QMessageBox.StandardButton.No:
            return
        # Check if backup is a complete backup - These need special handling
        is_complete_backup = name.startswith("backup_")
        if is_complete_backup:
            # Handle complete backup restoration
            self.restore_complete_backup(name)
        else:
            # Handle regular backup restoration
            path_to_backup = Path(self.profile_path) / f"{name}"

            # Overwrite modlist.txt with the row's name
            new_modlist_path = Path(self.profile_path) / "modlist.txt"
            shutil.copy2(path_to_backup, new_modlist_path)
            # Refresh MO2
            self._organizer.refresh()

    def restore_complete_backup(self, name):
        """
            Restores a completed backup, overwriting the users files in profile

            This will replace the current modlist.txt, loadorder.txt, and lockedorder.txt with the versions from the backup.

            Because It's possible folks miss the "This cannot be undone", I will create backups of the original files before restoring.

            Returns:
                None
        """
        # Store .bak copies of modlist.txt, loadorder.txt, and lockedorder.txt in profile path
        for filename in ["modlist.txt", "loadorder.txt", "lockedorder.txt", "plugins.txt"]:
            original_path = Path(self.profile_path) / filename
            backup_path = Path(self.profile_path) / f"{filename}.bak"
            shutil.copy2(original_path, backup_path)
        # Unzip the complete backup in to the profile path, overwrite existing files
        backup_zip_path = Path(self.profile_path) / "complete_backups" / name
        if backup_zip_path.exists():
            with zipfile.ZipFile(backup_zip_path, 'r') as zip_ref:
                zip_ref.extractall(self.profile_path)
            qInfo(f"Restored complete backup from {backup_zip_path}")
        self._organizer.refresh()

    def handle_double_click(self, item):
        """
            Handles what happens when users double click the name of the backup, and the description
        """
        row = item.row()
        col = item.column()
        name = self.table.item(row, 0).text()
        # If double-clicked column is 0 (File Name), open in notepad
        if col == 0:
            # If the file is a complete backup, open it in a different way
            if name.startswith("backup_"):
                self.open_complete_backup_in_file_explorer(row)
            else:
                self.open_file_in_notepad(row)
        # If double-clicked column is 3 (Description), open set description dialog
        elif col == 3:
            # Only clear description if user cancels the dialog
            text, ok = QInputDialog.getText(self, "Set Description", "Enter description:")
            if ok and text:
                # Create a non-editable QTableWidgetItem for the description
                item = QTableWidgetItem(text)
                item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
                self.table.setItem(row, 3, item)
                self.update_csv_file(row, text, name)
                self.table.clearFocus()
            self.table.resizeRowsToContents()


    def update_csv_file(self, row, description, name):
        """
            Updates the CSV file with the new description for the given backup name.
        """
        if self.csv_file:
            # Read the existing CSV data
            with open(self.csv_file, "r", newline="", encoding="utf-8") as f:
                reader = csv.reader(f)
                data = list(reader)
            # Find the CSV Line the matches the filename
            for i, row in enumerate(data):
                if row[0] == name:
                    # Add Place this description in the description column of the CSV, the second column
                    data[i][1] = description

                    break
                # If the filename is not found, assume it is a new entry
            else:
                # Add a new row for the new entry
                data.append([name, description])

            # Write the updated data back to the CSV file
            with open(self.csv_file, "w", newline="", encoding="utf-8") as f:
                writer = csv.writer(f)
                writer.writerows(data)
