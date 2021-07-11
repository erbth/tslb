"""
Dependency analysis

This uses binary packages as well and hence breaks with he
`program_analysis`-decoupled from tslb to some degree.
"""
from .dependency_analyzer import *

from .shebang_analyzer import ShebangAnalyzer
from .shell_analyzer import ShellAnalyzer

ALL_ANALYZERS = [
    ShebangAnalyzer,
    ShellAnalyzer
]
