"""
Some common exceptions to be used in various places.
"""

class ConfFileError(Exception):
    def __init__(self, msg=None, filename=None, line=None):
        if filename:
            composed = "Error in config file '%s'" % filename
        else:
            composed = "Error in a config file"

        if line:
            composed = composed + (" on line %s" % line)

        composed = composed + (": " + msg if msg else ".")

        super().__init__(composed)

class PackageDefinitionMissing(Exception):
    def __init__(self, name, filename=None):
        composed = "Package definition of '%s' missing" % name
        composed = composed + (": file '%s'." % filename if filename else ".")

        super().__init__(composed)

class CompiletimeDependencyError(Exception):
    def __init__(self, pkg_name, cdep):
        super().__init__("'%s' depends on '%s', but the latter does not exist." %
                (pkg_name, cdep))

class InvalidState(Exception):
    def __init__(self, msg):
        super().__init__('Invalid state: %s' % msg)

class BuildError(Exception):
    def __init__(self, msg=None):
        super().__init__('Build error' if not msg else ('Build error %s' % msg))

class LocationMissing(Exception):
    def __init__(self, location):
        super().__init__("Location '%s' missing" % location)

class SourceArchiveMissing(Exception):
    def __init__(self, pkg_name, archive_name):
        super().__init__("Source archive '%s' of package '%s' missing." % (pkg_name, archive_name))

class CommandFailed(Exception):
    def __init__(self, command, code=None):
        if isinstance(command, list) or isinstance(command, tuple):
            command = ' '.join(command)

        self.command = command
        self.returncode = code

        if code is not None:
            super().__init__("Command `%s' failed with exit code %s." % (command, code))
        else:
            super().__init__("Command `%s' failed." % command)

class InvalidParameter(Exception):
    def __init__(self, function, parameter):
        super().__init__("Invalid parameter '%s' to function '%s'" % (parameter, function))

class AnalyzeError(Exception):
    def __init__(self, msg):
        super().__init__(msg)

class NotImplemented(Exception):
    def __init__(self, msg):
        super().__init__(msg)

class SavedYourLife(Exception):
    def __init__(self, msg):
        super().__init__('I just saved your life: %s' % msg)

class InvalidPackedShapeName(Exception):
    def __init__(self, name, msg = None):
        if msg:
            super().__init__("Invalid packed shape TSLegacy package name: '%s' (%s)" % (name, msg))
        else:
            super().__init__("Invalid packed shape TSLegacy package name: '%s'" % name)

class InvalidText(Exception):
    def __init__(self, text, msg):
        super().__init__("Invalid text '%s': %s" % (text, msg))

class NoSuchRow(Exception):
    def __init__(self, id, table):
        super().__init__("Row '%s' does not exists in table %s." (id, table))

class NoSuchAttribute(Exception):
    def __init__(self, obj, key):
        super().__init__("%s has no attribute `%s'." % (obj, key))

class MissingWriteIntent(Exception):
    def __init__(self, reference=None):
        if reference:
            super().__init__(
                    "A write was requested but no write intent specified before. I abort to avoid deadlocks. (%s)" %
                    reference)
        else:
            super().__init__(
                    "A write was requested but no write intent specified before. I abort to avoid deadlocks.")

class AttributeManuallyHeld(Exception):
    def __init__(self, attr_name):
        super().__init__("Attribute %s was manually held." % attr_name)

