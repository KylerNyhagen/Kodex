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



def createPlugins() -> List[mobase.IPlugin]:
    return [BackupOrganizer(), PluginExporter(), LodGenPluginDisabler()]
