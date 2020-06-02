"""
The main shell module that interacts with the user.
"""
import atexit
import os
import re
import readline
import shlex
from tslb.Console import Color
from . import *
from . import object_editor


root_directory = RootDirectory()
history_file = os.path.expanduser("~/.tslb_mgmt_shell_history")

def main(*args):
    cwd_path = '/'
    cwd = root_directory

    if os.path.isfile(history_file):
        readline.read_history_file(history_file)

    readline.set_history_length(1000)
    atexit.register(readline.write_history_file, history_file)

    # Set a completer function
    def completer(text, state):
        nonlocal cwd

        try:
            completions = list(filter(
                lambda x: x.startswith(text),
                [d.name for d in cwd.listdir()]
            ))

            if state >= len(completions):
                return None
            else:
                return completions[state]

        except BaseException as e:
            print(str(e))
            return None

    readline.set_completer(completer)
    readline.set_completer_delims(' \t\r\n')

    # Enable autocompletion when the tab key is pressed
    readline.parse_and_bind('tab:complete')

    # Main interpreter loop
    while True:
        prompt = "\1\033[38;2;190;39;6;1m\2tslb\1\033[0m\2:\1\033[94;1m\2%s\1\033[0m\2$ " % cwd_path

        try:
            line = input(prompt)

        except KeyboardInterrupt:
            line = ""
            print()

        elems = [e for e in shlex.split(line)]

        if not elems:
            continue

        cmd = elems[0]

        # Parse built-in commands
        if cmd == 'exit':
            try:
                exitcode = int(elems[1]) if len(elems) >=2 else 0

            except:
                exitcode = 1

            return exitcode

        elif cmd == "ls":
            if len(elems) > 1:
                print("ls does not accept arguments.")
                continue

            for e in cwd.listdir():
                s = ""
                postfix = ""

                if isinstance(e, Directory):
                    s += "\033[94;1m"

                elif isinstance(e, Action):
                    if e.writes:
                        s += "\033[91;1m"
                    else:
                        s += "\033[92;1m"

                elif isinstance(e, Property):
                    if e.writable:
                        s += "\033[93;1m"
                    else:
                        s += "\033[33m"

                    postfix = ': %s' % e.read().replace('\n', '\\n')

                    if len(postfix) > 80:
                        postfix = postfix[:80] + " <truncated>"

                s += e.name + Color.NORMAL + postfix
                print(s)

        elif cmd == "cd":
            if len(elems) > 2:
                print("Too many arguments.")
                continue

            if len(elems) == 1 or elems[1] == '.':
                continue

            dst = ""

            if elems[1] == '..':
                dst = cwd_path.rstrip('/')

                while dst and dst[-1] != '/':
                    dst = dst[:-1]

                while len(dst) > 1 and dst[-1] == '/':
                    dst = dst[:-1]

                if not dst:
                    continue

            else:
                dst = elems[1]
                if dst[0] != '/':
                    dst = cwd_path + ('/' if cwd_path[-1] != '/' else '') + dst

            new_cwd = root_directory
            new_cwd_path = ""

            found = True

            if dst == '/':
                new_cwd_path = dst

            else:
                for name in dst.split('/'):
                    found = False

                    for d in new_cwd.listdir():
                        if isinstance(d, Directory) and d.name == name:
                            new_cwd = d
                            new_cwd_path += "/" + name
                            found = True
                            break

            if found:
                cwd = new_cwd
                cwd_path = new_cwd_path

            else:
                print('There is no directory with path "%s".' % dst)


        elif cmd == 'edit':
            if len(elems) != 2:
                print("Usage: edit <property>")
                continue

            prop = None

            for elem in cwd.listdir():
                if elem.name == elems[1] and isinstance(elem, Property):
                    prop = elem
                    break

            if not prop:
                print("No such property.")
                continue

            try:
                val = prop.read_raw()
            except NotImplemented:
                print("This property does not implement `read_raw`.")
                continue

            try:
                new_val = object_editor.edit_object(val, prop.writable)

                # Save the content if it changed
                if new_val == val:
                    print("\nValue not modified.")

                else:
                    prop.write(new_val)
                    print("\nStored the new value.")

            except object_editor.UnsupportedObject as e:
                print(str(e) + '\n')


        else:
            # See if the current working directory contains an action or
            # property with that name.
            found = False

            for e in cwd.listdir():
                if isinstance(e, Action) and cmd == e.name:
                    e.run(*elems)
                    found = True
                    break

                elif isinstance(e, Property) and cmd == e.name:
                    if len(elems) == 1:
                        print(str(e.read()))

                    else:
                        if elems[1] == '=' and len(elems) <= 3:
                            if e.writable:
                                if len(elems) == 3:
                                    e.write(elems[2])
                                else:
                                    e.write(None)

                            else:
                                print("This property is read-only.")

                        else:
                            print("Must either have no arguments or an '=' optionally followed by a value.")

                    found = True
                    break

            if not found:
                print('Command "%s" not found.' % cmd)
