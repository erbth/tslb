import os
from tslb.management_shell import *
from tslb import rootfs
from tslb import tclm
from tslb import Architecture


class RootDirectory(Directory):
    def __init__(self):
        super().__init__()
        self.name = "rootfs"


    def listdir(self):
        return [
            ImagesDirectory(),
            ToolsDirectory(),
            ActionList(),
            ActionCreateEmpty(),
            ActionCowClone(),
            ActionDelete()
        ]


class ActionList(Action):
    """
    List all rootfs images and their comments.
    """
    def __init__(self):
        super().__init__()
        self.name = "list"

    def run(self, *args):
        c1,c2 = (len("id"), len("comment"))
        text = []

        for i in rootfs.list_images():
            img = rootfs.Image(i)
            text.append((i, img.comment if img.comment else '', img.in_available_list))

            c1,c2 = (max(c1, len(str(i))), max(c2, len(img.comment if img.comment else '')))

        print(" %-*s  %-*s  published " % (c1, 'id', c2, 'comment'))
        print('-' * (c1 + c2 + 4) + "-----------")

        text.sort()

        for i,name,published in text:
            print(" %-*s  %-*s  %s" % (c1, i, c2, name, "Yes" if published else "No"))


class ActionCreateEmpty(Action):
    """
    Create a new rootfs image.
    """
    def __init__(self):
        super().__init__(writes=True)
        self.name = "create_empty"


    def run(self, *args):
        img = None

        try:
            img = rootfs.create_empty_image()
        except Exception as e:
            print("\033[31mFAILED\033[0m: %s" % e)
            return

        print("Created image %d." % img.id)


class ActionCowClone(Action):
    """
    Cow-clones an existing image.
    """
    def __init__(self):
        super().__init__(writes=True)
        self.name = "cow_clone"


    def run(self, *args):
        if len(args) != 2:
            print("Usage: %s <source image id>" % args[0])
            return

        src = None
        try:
            src = int(args[1])

            if src < 0:
                raise ValueError

        except ValueError:
            print('The image id must be an unsigned integer, not "%s".' % args[1])
            return

        try:
            src = rootfs.Image(src)
        except:
            print("The source image does not exist.")
            return

        img = None
        try:
            img = rootfs.cow_clone_image(src)
        except Exception as e:
            print("\033[31mFAILED\033[0m: %s" % e)
            return

        print("COW-cloned image %d from %d." % (img.id, src.id))


class ActionDelete(Action):
    """
    Delete an image.
    """
    def __init__(self):
        super().__init__(writes=True)
        self.name = "delete"


    def run(self, *args):
        if len(args) != 2:
            print("Usage: %s <image id>" % args[0])
            return

        img_id = None
        try:
            img_id = int(args[1])

            if img_id < 0:
                raise ValueError

        except ValueError:
            print('The image id must be an unsigned integer, not "%s".' % args[1])
            return

        try:
            rootfs.delete_image(img_id)

        except Exception as e:
            print("\033[31mFAILED\033[0m: %s" % e)
            return

        print("Deleted image %d." % img_id)


#************************** Presenting an image *******************************
class ImagesDirectory(Directory):
    """
    A directory that houses all rootfs images.
    """
    def __init__(self):
        super().__init__()
        self.name = "imgs"


    def listdir(self):
        imgs = rootfs.list_images()
        imgs.sort()

        return [ImageDirectory(img) for img in imgs]


class ImageDirectory(Directory):
    """
    A directory that represents a rootfs image in the directory of rootfs
    imsages. It contains a rootfs image factory that creates (and locks) images
    if required.
    """
    def __init__(self, img_id):
        super().__init__()

        self.img_id = int(img_id)
        self.name = str(img_id)


    def listdir(self):
        return [
            ImageCommentProperty(self.img_id),
            ImagePublishedProperty(self.img_id),
            ImageHasRoBaseProperty(self.img_id),

            ImageListPackagesAction(self.img_id),
            ImagePublishAction(self.img_id, True),
            ImagePublishAction(self.img_id, False),
            ImageRemoveRoBaseAction(self.img_id),
            ImageListChildrenAction(self.img_id),
            ImageFlattenAction(self.img_id),
            ImageMountAction(self.img_id),
            ImageRunBashAction(self.img_id)
        ]


class ImageBaseFactory:
    """
    A base class that contains a rootfs image factory that creates (and locks)
    images if required.
    """
    def create_image(self, acquire_X=False):
        """
        :param acquire_X: The image is created with a lock held in exclusive
            mode.
        """
        if acquire_X:
            tclm.define_lock('tslb.rootfs.images.{:d}'.format(self.img_id))\
                .acquire_X()

        return rootfs.Image(self.img_id, acquired_X=acquire_X)


class ImageCommentProperty(Property, ImageBaseFactory):
    """
    Present an image's comment.
    """
    def __init__(self, img_id):
        super().__init__(writable=True)
        self.img_id = img_id
        self.name = "comment"


    def read(self):
        c = self.create_image().comment
        return '' if not c else ('"' + c + '"')


    def write(self, value):
        self.create_image(True).set_comment(value)


class ImagePublishedProperty(Property, ImageBaseFactory):
    """
    A read only property that indicates if the image is published.
    """
    def __init__(self, img_id):
        super().__init__()
        self.img_id = img_id
        self.name = "published"


    def read(self):
        return "Yes" if self.create_image().in_available_list else "No"


class ImageHasRoBaseProperty(Property, ImageBaseFactory):
    """
    A read only property that indicates if the images has an ro_base snapshot.
    """
    def __init__(self, img_id):
        super().__init__()
        self.img_id = img_id
        self.name = "has_ro_base"


    def read(self):
        return "Yes" if self.create_image().has_ro_base else "No"


class ImageListPackagesAction(Action, ImageBaseFactory):
    """
    List the packages in an images.
    """
    def __init__(self, img_id):
        super().__init__()
        self.name = 'list_packages'
        self.img_id = img_id


    def run(self, *args):
        pkgs = sorted([(n, Architecture.to_str(a), str(v)) for n,a,v in self.create_image().packages])

        c1,c2,c3 = (0,0,0)

        for name, arch, version in pkgs:
            c1,c2,c3 = (max(c1,len(name)), max(c2,len(arch)), max(c3,len(version)))

        for name, arch, version in pkgs:
            print("%-*s @ %-*s : %-*s" % (c1, name, c2, arch, c3, version))


class ImagePublishAction(Action, ImageBaseFactory):
    """
    Publish- or unpublish images.

    :param int img_id: The image's id
    :param bool publish: True if the image should be published, False if it
        should be unpublished.
    """
    def __init__(self, img_id, publish):
        super().__init__(writes=True)
        self.publish = bool(publish)
        self.name = "publish" if self.publish else "unpublish"
        self.img_id = img_id


    def run(self, *args):
        img = self.create_image(acquire_X=True)

        if self.publish:
            img.publish()
        else:
            img.unpublish()


class ImageRemoveRoBaseAction(Action, ImageBaseFactory):
    """
    Remove the image's ro_base snapshot if it has one.
    """
    def __init__(self, img_id):
        super().__init__(writes=True)
        self.img_id = img_id
        self.name = "remove_ro_base"


    def run(self, *args):
        img = self.create_image(True)
        
        try:
            img.remove_ro_base()

        except Exception as e:
            print("\033[31mFAILED\033[0m: %s" % e)


class ImageListChildrenAction(Action, ImageBaseFactory):
    """
    List COW-clones of this image.
    """
    def __init__(self, img_id):
        super().__init__(writes=False)
        self.img_id = img_id
        self.name = "list_children"


    def run(self, *args):
        img = self.create_image(False)
        print("Children:")
        for c in img.list_children():
            print("  %s" % c)


class ImageFlattenAction(Action, ImageBaseFactory):
    """
    Flatten an image.
    """
    def __init__(self, img_id):
        super().__init__(writes=False)
        self.img_id = img_id
        self.name = "flatten"


    def run(self, *args):
        img = self.create_image(False)

        try:
            img.flatten()

        except Exception as e:
            print("\033[31mFAILED\033[0m: %s" % e)


class ImageMountAction(Action, ImageBaseFactory):
    """
    Mounts the image until the user signals that it should be unmounted.
    """
    def __init__(self, img_id):
        super().__init__(writes=False)
        self.name = "mount"
        self.img_id = img_id

        # Find out if this can alter the image, i.e. if it has no ro_base.
        # Because if that is possible, an X lock shall be acquired.
        self.writes = not self.create_image().has_ro_base


    def run(self, *args):
        img = self.create_image(self.writes)

        try:
            img.mount('mgmt_shell')

            try:
                print('Mounted image %d at "%s".' % (self.img_id, img.get_mountpoint('mgmt_shell')))
                print('Press return to unmount.')
                input()

            finally:
                img.unmount('mgmt_shell')

        except Exception as e:
            print("\033[31mFAILED\033[0m: %s" % e)


class ImageRunBashAction(Action, ImageBaseFactory):
    """
    Mounts the image and pseudo file systems, chrootes to the image and
    executes a bash shell.
    """
    def __init__(self, img_id):
        super().__init__()
        self.name = "run_bash"
        self.img_id = img_id

        # Find out if this procedure can alter the image, i.e. if it has no
        # ro_base. Because if that is possible, the function should acquire an
        # exclusive lock such that the user can actually alter the image.
        self.writes = not self.create_image().has_ro_base


    def run(self, *args):
        try:
            # Import the package builder.
            from tslb import package_builder as pb

            # Acquire a lock on the image and mount it.
            img = self.create_image(self.writes)
            img.mount('mgmt_shell')

            try:
                mountpoint = img.get_mountpoint('mgmt_shell')
                print('Mounted image %d at "%s".' % (self.img_id, mountpoint))

                try:
                    pb.mount_pseudo_filesystems(mountpoint)

                    def f():
                        return os.execlp('bash', 'bash', '--login', '+h')

                    pb.execute_in_chroot(mountpoint, f)

                finally:
                    pb.unmount_pseudo_filesystems(mountpoint, raises=True)

            finally:
                img.unmount('mgmt_shell')

        except Exception as e:
            print("\033[31mFAILED\033[0m: %s" % e)


#********************************** Tools *************************************
class ToolsDirectory(Directory):
    """
    A directory with tools for rootfs images.
    """
    def __init__(self):
        super().__init__()
        self.name = "tools"


    def listdir(self):
        return [
            ActionToolsDeleteProbablyUnused(),
            ActionToolsDeleteProbablyRecreatable()
        ]


class ActionToolsDeleteProbablyUnused(Action):
    """
    Delete all images that have no comment and are not published. Child images
    are flattened.
    """
    def __init__(self):
        super().__init__(writes=True)
        self.name = "delete_probably_unused"


    def run(self, *args):
        try:
            rootfs.delete_probably_unused_images()
            print("\033[32mok.\033[0m")
        except Exception as e:
            print("\033[31mFAILED\033[0m: %s" % e)


class ActionToolsDeleteProbablyRecreatable(Action):
    """
    Delete all published images without a comment. Child images are flattened.
    """
    def __init__(self):
        super().__init__(writes=True)
        self.name = "delete_probably_recreatable"


    def run(self, *args):
        try:
            rootfs.delete_probably_recreatable_images()
            print("\033[32mok.\033[0m")
        except Exception as e:
            print("\033[31mFAILED\033[0m: %s" % e)
