
import mobase
from typing import List

#from .BackupCompare import BackupCompare
from .SupportReporter import SupportReporter

def createPlugins() -> List[mobase.IPlugin]:
        ## Try to import SupportGoldenGenerator - If it doesn't work, assume it doesn't exist and instead import everything without it
        try:
            from .SupportGoldenGenerator import SupportGoldenGenerator
            return [SupportReporter(), SupportGoldenGenerator()]
        except Exception as e:
            return [SupportReporter()]


