import os

class ConfigureAction(object):
    def __init__(self):
        self.after = []
        self.before = []
        self.name = ""

    def generate_configure_script(self):
        """
        Can be a triple (filename, interpreter, content), or None
        """
        return None

    def generate_unconfigure_script(self):
        """
        Can be a triple (filename, interpreter, content), or None
        """
        return None

# Predefined configure actions
class ConfigureCustomScript_base(ConfigureAction):
    def __init__(self, filename, interpreter, content = None,
            after = [], before = []):
        """
        If content is None, then the file content is read from a corresponding
        file on disk that has that name. Therefore filename can be a path.

        :interpreter: A path to the interpreter for the file, or None to
                      execute it directly.
        """
        super().__init__()

        self.filename = os.path.basename(filename)
        self.interpreter = interpreter
        self.after = after
        self.before = before

        self.name = "Custom_" + self.filename

        if content:
            self.content = content
        else:
            with open(filename) as f:
                self.content = c = f.read()

                while c:
                    c = f.read()
                    self.content = self.content + c

class ConfigureCustomScript_configure(ConfigureCustomScript_base):
    def __init__(self, filename, interpreter, content = None):
        super().__init__(filename, interpreter, content)

    def generate_configure_script(self):
        return (self.filename, self.interpreter, self.content)

class ConfigureCustomScript_unconfigure(ConfigureCustomScript_base):
    def __init__(self, filename, interpreter, content = None):
        super().__init__(filename, interpreter, content)

    def generate_unconfigure_script(self):
        return (self.filename, self.interpreter, self.content)


# The actual script generator. It's more a reducer, though, because of the
# divide-and-conquer architecture.
class Generator(object):
    def __init__(self, actions, interpreter,
            configuresh_directory = None, support_file_directory = None):
        if not isinstance(actions, set):
            actions = set(actions)

        self.actions = actions
        self.interpreter = interpreter

    def generate_configure_scripts(self):
        """
        Generate configure.sh and support files in the given directories if
        they are not None.
        """
        pass

    def generator_unconfigure_scripts(self):
        """
        Generate unconfigure.sh and support scripts in the given directories if
        they are not None.
        """
        pass
