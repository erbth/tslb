#!/usr/bin/python3
"""
Delete a configuration of rootfs images
"""

import argparse
from tslb import rootfs
from tslb import tclm


def delete(id_):
    for imgid in sorted(rootfs.list_images(), reverse=True):
        img = rootfs.Image(imgid)
        comment = img.comment
        in_available_list = img.in_available_list

        # Free locks
        del img

        if not in_available_list and comment == "saved: " + id_:
            print("Deleting %s." % imgid)
            rootfs.delete_image(imgid)

    return id_


def main():
    parser = argparse.ArgumentParser("Delete a configurations of rootfs images")
    parser.add_argument('uuid', metavar="<uuid>", help="Images to delete")
    args = parser.parse_args()

    delete(args.uuid)

if __name__ == '__main__':
    main()
    exit(0)
