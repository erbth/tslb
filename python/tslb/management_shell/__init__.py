class Element:
    """
    A common base class for elements. Elements can be directories or anything
    else that the code defines. The only limitation is that elements must
    inherit from this class.
    """
    def __init__(self):
        self.name = ""


class Directory(Element):
    """
    A common base class for directories.
    """
    def __init__(self):
        super().__init__()

    def listdir(self):
        """
        Return a list of elements in this directory.
        """
        return []


class RootDirectory(Directory):
    def __init__(self):
        super().__init__()
        self.name = ""

        # Avoid any cyclic import on load
        from . import module_rootfs, module_scratch_space, module_source_packages, module_tslb

        self.dirs = [
                module_rootfs.RootDirectory(),
                module_scratch_space.RootDirectory(),
                module_source_packages.RootDirectory(),
                module_tslb.RootDirectory()
            ]


    def listdir(self):
        """
        Return a list of elements in the root directory.
        """
        return self.dirs


class Action(Element):
    """
    A base class for actions that can be executed.

    :param writes: can be set to True to indicate that the action will modify
        the system's state i.e. an object.
    """
    def __init__(self, writes=False, **kwargs):
        super().__init__()

        self.writes = writes

    def run(self, *args):
        """
        Execute the action with the specified arguments.

        :returns: None.
        """
        pass


class Property(Element):
    """
    A base class for properties of objects.

    :param writable: The property can be written.
    """
    def __init__(self, writable=False, **kwargs):
        super().__init__()

        self.writable = writable


    def read_raw(self):
        """
        Returns the attribute's raw value.
        """
        raise NotImplementedError


    def read(self):
        """
        Returns the attribute's value in a form that is suitable for displaying
        it to a user.

        :returns: The propertie's value.
        """
        raise NotImplementedError


    def write(self, value):
        """
        Sets the propertie's value.

        :param str value: The value to assign, must not be None.
        """
        if not self.writable:
            raise RuntimeError("This property is read only")

        raise NotImplementedError
