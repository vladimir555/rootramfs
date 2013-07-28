#!/usr/bin/python


__author__ = 'volodja'


import os
import re
import sys
#import getpass


def printList(name, list_):
    print(name + ":")
    for row in list_:
        print(str(row).replace("\n", ""))


def executeShellCommand(command):
    print("exec: " + command)
    result_pipe = os.popen(command)
    result_     = result_pipe.readlines()
    result      = []
    for line in result_:
        result.append(line.replace('\n', ''))
    return result


def readFSTab():
    file_fstab      = open("/etc/fstab")
    #file_fstab      = open("/etc/fstab.1")
    fstab_text      = file_fstab.readlines()
    fstab           = []
    file_fstab.close()

    for line in fstab_text:
        if line[0] != "#":
            fstab_line = re.split(r"\s+", line.replace("\n", "").replace("UUID=", ""))
            fstab.append(fstab_line)

    #printList("fstab", fstab)
    return fstab


def mountSyncFSTab():
    fstab           = readFSTab()
    mount           = executeShellCommand("mount")

    #print "fstab: " + str(fstab)
    #print("mount: " + str(mount))

    fstab_to_mount  = []
    for row_fstab in fstab:
        if len(row_fstab) < 2:
            continue
        is_need_mount   = True
        if row_fstab[1] == "/":
            mount_point = "/ram/sync"
        else:
            mount_point = "/ram/sync" + row_fstab[1]
        for row_mount in mount:
            if len(row_fstab) > 1  and  (row_fstab[0][0:4] != "/ram"  or  (row_fstab[0][0:4] == "/ram"  and  row_mount.split(" ")[2] == mount_point)):
                is_need_mount = False
                break
        if is_need_mount:
            fstab_to_mount.append(row_fstab)

    #print "fstab_to_mount = " + str(fstab_to_mount)
    #exit(0)
    for row_fstab in fstab_to_mount:
        mount = executeShellCommand("mkdir -p /ram/sync" + row_fstab[1] + " && mount -t " + row_fstab[2] +  
                               " /dev/disk/by-uuid/" + row_fstab[0][4:] + " /ram/sync" + row_fstab[1] + " || echo 'mount fail'")
        if len(mount) > 0:
            print("error: " + str(mount))
            exit(1)


def umountSyncFSTab():
    #fstab           = readFSTab()
    mount           = executeShellCommand("mount")
    fstab_to_umount = []
    is_was_root     = False

    for row_mount in mount:
        mount_point = str(row_mount.split(" ")[2])
        if mount_point[0:9] == "/ram/sync":
            if len(mount_point) > 9:
                fstab_to_umount.append(mount_point)
            else:
                is_was_root = True
    if is_was_root:
        fstab_to_umount.append("/ram/sync")

    for row_umount in fstab_to_umount:
        umount = executeShellCommand("umount " + row_umount)
        if len(umount) > 0:
            print("error: " + str(umount))
            exit(1)


def syncCommand(args, command_, is_reverse = False):
    paths       = []

    for row_args in args:
        paths.append(os.path.abspath(row_args))

    if is_reverse:
        dst = paths[0]
        src = "/ram/sync" + paths[0]
    else:
        src = paths[0]
        dst = "/ram/sync" + paths[0]

    if os.path.isdir(paths[0]):
        src     = src + "/"

    del paths[0]

    #user_name   = getpass.getuser()
    command     = command_ + " "
    command     = command + "--exclude '*/.gvfs' "
    command     = command + "--exclude '/run/user/*/gvfs' "
    command     = command + "--exclude '/media' "
    command     = command + "--exclude '/mnt' "
    command     = command + "--exclude '/dev' "
    command     = command + "--exclude '/sys' "
    command     = command + "--exclude '/proc' "
    command     = command + "--exclude '/selinux' "
    command     = command + "--exclude '/ram' "
    command     = command + "--exclude '/boot' "

    for row_paths in paths:
        command = command + "--exclude '" + row_paths + "' "

    command     = command + src + " " + dst + " | grep -v 'xfer#' && sync"
    rsync       = executeShellCommand(command)
    printList(command_, rsync)


def syncPath(args):
    syncCommand(args, "rsync --progress --delete -a")


def diffPath(args):
    syncCommand(args, "diff -r")


def resetPath(args):
    syncCommand(args, "rsync --progress --delete -a", True)


if len(sys.argv) >= 3  and  sys.argv[1] == "--sync":
    mountSyncFSTab()
    syncPath(sys.argv[2:])
    umountSyncFSTab()
    exit(0)

if len(sys.argv) >= 3  and  sys.argv[1] == "--reset":
    mountSyncFSTab()
    resetPath(sys.argv[2:])
    umountSyncFSTab()
    exit(0)

if len(sys.argv) >= 3  and  sys.argv[1] == "--diff":
    mountSyncFSTab()
    diffPath(sys.argv[2:])
    umountSyncFSTab()
    exit(0)


print("usage: rootramfs --sync  sync_path [exclude_path1] [exclude_path2] ...")
print("usage: rootramfs --reset sync_path [exclude_path1] [exclude_path2] ...")
print("usage: rootramfs --diff  sync_path [exclude_path1] [exclude_path2] ...")
