import os
import stat
import shutil
from tslb import CommonExceptions as es
from . import fs


def find_all_hard_links(base_dir, st_buf):
    """
    :params str base_dir: Base directory to search in
    :params st_buf: stat result describing the inode for which links are searched
    :returns List(str): [<paths of linkts, relative to base_dir without leading ./>]
    :raises RuntimeError: If not all hard links where found in the subtree
    """
    links = []

    dev = st_buf.st_dev
    inode = st_buf.st_ino

    def _work(f):
        fp = os.path.join(base_dir, f)
        s = os.lstat(fp)

        # Don't cross fs boundaries
        if s.st_dev != dev:
            return

        if s.st_ino == inode:
            links.append(f)

        # Recurse on directories
        if stat.S_ISDIR(s.st_mode):
            for c in os.listdir(fp):
                _work(os.path.join(f, c))

    _work('')


    if len(links) != st_buf.st_nlink:
        raise RuntimeError(
                "Not all links of inode found in subtree '%s': %d != nlink (%d)" %
                (base_dir, len(links), st_buf.st_nlink))

    return links


def copy_from_base(base_dir, src_path, dst_dir):
    """
    Copies base_dir/src_path to dst_dir/src_path

    If src_path has link count > 1 and one of the hard links is present in the
    destination already, a link is created instead of the file being copied.
    Note that the function does not check if the file content actually matches,
    because it is designed for splitting a directory tree into multiple ones
    (and therefore assumes that the destination trees are only modified after
    the last call to `copy_from_base`).

    If not all hard links of a file are found in the source directory tree, a
    RuntimeError is thrown.

    NOTE: Copying hardlinks would actually need tests... but there's no time
    for it.

    :param base_dir:
    :param src_path:
    :param dst_dir:
    """
    path_components = []

    while src_path and src_path != '/' and src_path != base_dir:
        src_path, last = os.path.split(src_path)

        if not last:
            continue

        path_components.append(last)

    path_components.reverse()
    gradual_path = ''

    for comp in path_components:
        gradual_path = os.path.join(gradual_path, comp)

        src = os.path.join(base_dir, gradual_path)
        dst = os.path.join(dst_dir, gradual_path)

        s = os.lstat(src)

        if stat.S_ISDIR(s.st_mode):
            if not os.path.isdir(dst):
                os.mkdir(dst)

            shutil.copystat(src, dst)
            os.chown(dst, uid=s.st_uid, gid=s.st_gid)
            os.chmod(dst, mode=s.st_mode & 0o7777)

        else:
            # Check for hard links where the file might have been copied
            # already.
            file_present = False
            target_lnk = None

            if s.st_nlink > 1:
                hard_links = find_all_hard_links(base_dir, s)

                # If the file is already present, create a link to it.
                for h in hard_links:
                    if h == gradual_path:
                        continue

                    target_lnk = os.path.join(dst_dir, h)
                    if os.path.lexists(target_lnk):
                        file_present = True
                        break

            if file_present:
                # Create another link
                os.link(target_lnk, dst, follow_symlinks=False)

            else:
                if stat.S_ISLNK(s.st_mode):
                    os.symlink (os.readlink(src), dst)
                elif stat.S_ISREG(s.st_mode):
                    shutil.copyfile(src, dst)
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

                shutil.copystat(src, dst, follow_symlinks=False)

                # copystat does not copy owner, group and suid/guid bits
                os.chown(dst, uid=s.st_uid, gid=s.st_gid, follow_symlinks=False)

                if not stat.S_ISLNK(s.st_mode):
                    os.chmod(dst, mode=s.st_mode & 0o7777)


def traverse_directory_tree(base, action, skip_hidden=False, element = ''):
    """
    With respect to directories, this function does an pre-order traversal.
    Nothing else would be suitable for general purpose directory structures,
    as they are hierarchical.

    action gets a path relative to base.

    :param skip_hidden: Skip hidden files and directories and their contents
    :param element: A parameter that transports information to recursive calls.
        It should not be used by external users.
    """

    if element:
        action (element)

    abs_element = os.path.join(base, element)

    s = os.lstat(abs_element)

    if stat.S_ISDIR(s.st_mode):
        for e in os.listdir (abs_element):
            if not skip_hidden or not e.startswith('.'):
                traverse_directory_tree(base, action, skip_hidden, os.path.join(element, e))


def mkdir_p(path, mode=0o777, base="/"):
    """
    Create the directory given in path and all its ancessors shall they be
    missing. If path is not absolute, it is expanded to an absolute path using
    the current working directory. Then base is prepended to path. This works
    with absolute and relative paths alike, but remember that relative paths
    are expanded first.

    :param path: Path to the directory to create
    :param mode: Maximum permissions of the new directory. The umask is
        subtracted first.
    :param base: Additional path prefix, see above.
    """
    path_components = []

    # If the path is not absolute, make it so. This won't interfere with base,
    # because it can be prepended to a path starting with a slash.
    path = os.path.abspath(path)

    while path and path != '/':
        path, component = os.path.split(path)

        if component:
            path_components.append(component)

    path_components.reverse()
    p = base

    for component in path_components:
        p = os.path.join(p, component)

        if not os.path.isdir(p):
            # The directory could have been created after the check
            try:
                os.mkdir(p, mode=mode)
            except FileExistsError:
                pass


def rm_r(path):
    """
    Delete a directory and all its content. If it does not exist, raise an
    exception. If the directory lies on cephfs and has snapshots, these are
    deleted, too.
    """
    if os.path.exists(path) and\
            stat.S_ISDIR(os.stat(path, follow_symlinks=False).st_mode):
        # Delete content
        for e in os.listdir(path):
            if e != '.' and e != '..':
                rm_r(os.path.join(path, e))

        # Delete cephfs snapshots
        snappath = os.path.join(path, '.snap')
        if os.path.exists(snappath) and\
                stat.S_ISDIR(os.stat(snappath, follow_symlinks=False).st_mode):

            for r in os.listdir(snappath):
                if r != '.' and r != '..' and r[0] != '_':
                    os.rmdir(os.path.join(snappath, r))

        # Delete directory
        os.rmdir(path)

    else:
        # Delete other file
        os.unlink(path)

def rm_rf(path):
    """
    Similar to rm_r, but does not raise an exception if the directory does not
    exist but silently do nothing.
    """

    # exists() returns False for broken symbolic links ...
    if os.path.exists(path) or os.path.islink(path):
        rm_r(path)

def clean_directory(path):
    """
    Remove the given directory's content, but not the directory itself. Hence
    it's like rm_r but without removing the base directory and throwing an
    exception if path is not a directory. If the directory lies on cephfs and
    has snapshots, these won't be deleted (that's different to what rm_r does).
    However the snapshots of children are deleted.
    """
    for e in os.listdir(path):
        if e != '.' and e != '..':
            rm_r(os.path.join(path, e))

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

def make_snapshot(path, name):
    return fs.make_snapshot(path, name)

def delete_snapshot(path, name):
    return fs.delete_snapshot(path, name)

def list_snapshots(path):
    return fs.list_snapshots(path)

def restore_snapshot(path, name):
    return fs.restore_snapshot(path, name)


def simplify_path_static(path):
    """
    Simplify a path without touching the filesystem. This essentially removes
    double slashes and trailing slashes. Hence it's static because it does not
    require dynamic information only available from filesystems being online.
    """
    result = ''
    last_char = None

    for char in path:
        if last_char != '/' or char != '/':
            result += char

        last_char = char

    if len(result) > 1 and result[-1] == '/':
        result = result[:-1]

    return result
