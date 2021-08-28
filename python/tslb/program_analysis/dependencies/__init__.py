"""
Dependency analysis

This uses binary packages as well and hence breaks with he
`program_analysis`-decoupled from tslb to some degree.
"""
from .dependency_analyzer import *

from .shebang_analyzer import ShebangAnalyzer
from .soname_matching_analyzer import SONAMEMatchingAnalyzer
from .shell_analyzer import ShellAnalyzer
from .python_analyzer import PythonAnalyzer

ALL_ANALYZERS = [
    SONAMEMatchingAnalyzer,
    ShebangAnalyzer,
    ShellAnalyzer,
    PythonAnalyzer
]
