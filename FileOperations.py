import os
import stat
import shutil
import CommonExceptions as es

def copy_from_base(base_dir, src_path, dst_dir):
    path_components = []

    while src_path and src_path != base_dir:
        src_path, last = os.path.split(src_path)
        path_components.append(last)

    path_components.reverse()
    gradual_path = ''

    for comp in path_components:
        gradual_path = os.path.join(gradual_path, comp)

        src = os.path.join(base_dir, gradual_path)
        dst = os.path.join(dst_dir, gradual_path)

        s = os.stat(src, follow_symlinks = False)

        if stat.S_ISDIR(s.st_mode):
            if not os.path.isdir(dst):
                os.mkdir(dst)
                shutil.copystat(src, dst)
                os.chown(dst, uid=s.st_uid, gid=s.st_gid)
        else:
            copy_attributes = True

            if stat.S_ISLNK(s.st_mode):
                os.symlink (os.readlink(src), dst)
                copy_attributes = False
            elif stat.S_ISREG(s.st_mode):
                shutil.copy(src, dst)
            elif stat.S_ISBLK(s.st_mode):
                os.mknod(dst, mode=stat.S_IFBLK, device=s.st_rdev)
            elif stat.S_ISCHR(s.st_mode):
                os.mknod(dst, mode=stat.S_IFCHR, device=s.st_rdev)
            elif stat.S_ISFIFO(s.st_mode):
                os.mkfifo(dst)
            elif stat.S_ISSOCK(s.st_mode):
                raise es.NotImplemented("Cannot copy socket '%s' (not implemented)" % src)
            elif stat.S_ISDOOR(s.st_mode):
                raise es.NotImplemented("Cannot copy door '%s' (not implemented)" % src)
            else:
                raise es.NotImplemented("Unknown filetype of '%s'." % src)

            if copy_attributes:
                shutil.copystat(src, dst)
                os.chown(dst, uid=s.st_uid, gid=s.st_gid)

def traverse_directory_tree(base, action, element = ''):
    """
    With respect to directories, this function does an pre-order traversel.
    Nothing else would be suitable for general purpose directory structures,
    as they are hierarchical.

    action gets a path relative to base.
    """

    if element:
        action (element)

    abs_element = os.path.join(base, element)

    try:
        s = os.stat(abs_element, follow_symlinks = False)
    except FileNotFoundError:
        return

    if stat.S_ISDIR(s.st_mode):
        for e in os.listdir (abs_element):
            traverse_directory_tree(base, action, os.path.join(element, e))

def mkdir_p(path, mode, base="/"):
    path_components = []

    while path and path != '/':
        path, component = os.path.split(path)

        if component:
            path_components.append(component)

    path_components.reverse()
    p = base

    for component in path_components:
        p = os.path.join(p, component)

        if not os.path.isdir(p):
            os.mkdir(p, mode=mode)

class LinkChunk(object):
    """
    A data structure for moving and changing sets of links.

    Runtimes are worst case and assume that the os operations and list.append
    take constant time.
    """
    def __init__(self, links = None):
        """
        O(n)
        """
        # List of tuples (link, target, on_disk)
        self.links = []

        if links:
            for link in links:
                self.add_link(link)

    def add_link(self, link):
        """
        O(1)

        If link is not an absolute path, it will be converted into one with
        respect to the current working directory.
        """
        link = os.path.abspath(link)

        self.links.append((
            link,
            os.path.normpath(os.path.join(os.path.dirname(link), os.readlink(link))),
            True))

    def has_link(self, link):
        """
        O(n)
        """
        return any(link == l for (l,_,_) in self.links)

    def move_link(self, old_path, new_path):
        """
        O(n)

        Adapts targets as well.
        Does nothing if the link is not in the chunk.
        """
        old_path = os.path.abspath(old_path)
        new_path = os.path.abspath(new_path)

        in_chunk = False

        for i, (link, target, on_disk) in enumerate(self.links):
            if link == old_path:
                if on_disk:
                    os.remove(link)

                self.links[i] = (new_path, target, False)
                in_chunk = True

        if in_chunk:
            self.move_target(old_path, new_path)

    def move_target(self, old_path, new_path):
        """
        O(n)

        Does nothing if there's no link with that target in the chunk.
        """
        old_path = os.path.abspath(old_path)
        new_path = os.path.abspath(new_path)

        for i, (link, target, on_disk) in enumerate(self.links):
            if target == old_path:
                if on_disk:
                    os.remove(link)

                self.links[i] = (link, new_path, False)

    def create_links(self):
        """
        O(n)

        Creates links with relative targets.
        """
        for (link, target, on_disk) in self.links:
            if not on_disk:
                os.symlink(
                        os.path.relpath(target, start=os.path.dirname(link)),
                        link)

    def __str__(self):
        return str(self.links)
