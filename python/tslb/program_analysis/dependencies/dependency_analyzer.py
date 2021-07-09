class BaseDependencyAnalyzer:
    """
    A base class to define the interface of all dependency analyzers.
    """
    display_name = ""

    def analyze_root(dirname, out):
        """
        Analyze the root directory tree rooted at :param str dirname:.

        :returns: Set(Dependency)
        :raises AnalyzeError: If an error has been encountered
        """
        raise NotImplementedError

    def analyze_file(filename, out):
        """
        Analyze a single file.

        :returns: Set(Dependency)
        :raises AnalyzeError: If an error has been encountered
        """
        raise NotImplementedError

    def analyze_buffer(buf, out):
        """
        Analyze an in-memory buffer that is a read file.

        :type buf: bytes (interpreted as ascii text) | str
        :returns: Set(Dependency)
        :raises AnalyzeError: If an error has been encountered
        """
        raise NotImplementedError


# Description of dependencies
class Dependency:
    """
    All dependencies inherit from this class. It is abstract and hence should
    not be instantiated.
    """

class FileDependency(Dependency):
    """
    A dependency on a file.
    """
    def __init__(self, filename):
        self.filename = filename

    def __eq__(self, o):
        if type(self) != type(o):
            return False

        return self.filename == o.filename

    def __hash__(self):
        return hash(self.filename)

class BinaryPackageDependency(Dependency):
    """
    An immediate dependency on a binary package.

    :param str bp_name: The binary package's name
    :param List(VersionConstraint(str)): List of version constraints
    """
    def __init__(self, bp_name, version_constraints):
        self.bp_name = bp_name
        self.version_constraints = tuple(version_constraints)

    def __eq__(self, o):
        if type(self) != type(o):
            return false

        return self.bp_name == o.bp_name and \
                self.version_contraints == o.version_constraints

    def __hash__(self):
        return hash((self.bp_name, *self.version_constraints))


class Or(Dependency):
    """
    One of the supplied children must be fulfilled. This is useful if a binary
    could live in /bin and /usr/bin and both versions would work.
    """
    def __init__(self, formulas):
        self.formulas = tuple(formulas)

    def __eq__(self, o):
        if type(self) != type(o):
            return False

        return self.formulas == o.formulas

    def __hash__(self):
        return hash(self.formulas)


#************************************ Exceptions ******************************
class AnalyzerError(Exception):
    pass
