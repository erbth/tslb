#!/usr/bin/python3
"""
Save / restore a configuration of images
"""

import argparse
import uuid
from tslb import rootfs
from tslb import tclm


def save():
    id_ = str(uuid.uuid4())

    for imgid in rootfs.list_images():
        img = rootfs.Image(imgid)
        if img.in_available_list and not img.comment:
            print("Saving %s." % imgid)

            # Upgrade lock
            lk = img.db_lock
            with tclm.lock_Splus(lk):
                del img
                lk.acquire_X()
                img = rootfs.Image(imgid, acquired_X=True)

            # Unpublish and set comment
            img.unpublish()
            img.set_comment("saved: " + id_)

        del img

    return id_


def restore(id_):
    for imgid in rootfs.list_images():
        img = rootfs.Image(imgid)
        if not img.in_available_list and img.comment == "saved: " + id_:
            print("Restoring %s." % imgid)

            # Upgrade lock
            lk = img.db_lock
            with tclm.lock_Splus(lk):
                del img
                lk.acquire_X()
                img = rootfs.Image(imgid, acquired_X=True)

            # Unpublish and set comment
            img.publish()
            img.set_comment(None)

        del img

    return id_


def main():
    parser = argparse.ArgumentParser("Save and restore configurations of rootfs images")
    parser.add_argument("-s", "--save", action="store_true", help="Save configuration")
    parser.add_argument("-r", "--restore", metavar="<uuid>", help="Restore configuration")
    args = parser.parse_args()

    if bool(args.save) == bool(args.restore):
        print("Exactly one action must be specified (--save or --restore).")
        exit(1)

    if args.save:
        print("uuid: %s" % save())

    elif args.restore:
        restore(args.restore)

if __name__ == '__main__':
    main()
    exit(0)
