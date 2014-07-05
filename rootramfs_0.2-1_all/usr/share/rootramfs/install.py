#!/usr/bin/python3
# coding=utf8


__author__ = 'volodja'


import os
import re
import sys
import atexit


is_need_restore             = False
file_name_fstab             = "/etc/fstab"
file_name_fstab_rootramfs   = "/etc/fstab.rootramfs"
file_name_fstab_backup      = "/etc/fstab.rootramfsbackup"
file_name_hook              = "/usr/share/initramfs-tools/hooks/rootramfshook"
file_name_loader            = "/scripts/loader"


def printList(name, list_):
    print(name + ":")
    for row in list_:
        print(str(row).replace("\n", ""))


# выполняет шелл команду
def executeShellCommand(command):
    print("exec: " + command)
    result_pipe = os.popen(command)
    result_     = result_pipe.readlines()
    result      = []
    for line in result_:
        result.append(line.replace('\n', ''))
    printList("result", result)
    return result


# читает /etc/fstab в 2хмерный массив(return) пропуская строки "#..."
# @return:    fstab table
def readFSTab():
    print("read " + file_name_fstab + " ...")
    file_fstab      = open(file_name_fstab)
    fstab_text      = file_fstab.readlines()
    fstab           = []
    file_fstab.close()

    for line in fstab_text:
        if line[0] != "#":
            fstab_line = re.split(r"\s+", line.replace("\n", "").replace("UUID=", ""))
            fstab.append(fstab_line)

    #printList("fstab", fstab)
    print("read " + file_name_fstab + " OK")
    return fstab


# читает вывод blkid и возвращает в виде двухмерного массива
# @return:    blkid table
def readBlkID():
    print("read blkid devices ...")
    blkid_result    = executeShellCommand("blkid")
    blkid           = []
    for line in blkid_result:
        row = line.replace(":", "").replace("\"", "").replace("UUID=", "").replace("TYPE=", "") .split(" ")
        row.remove('')

        row_result = []
        for column in row:
            if column[0:6] != "LABEL=":
                row_result.append(column)
        row = row_result
                
        blkid.append(row)

    if len(blkid) == 0:
        print("error: empty blkid result")
        exit(1)

    print("read blkid devices OK")
    printList("blkid", blkid)
    return blkid


# выбирает валидные строки из таблицы fstab соответствующие стандартным существующим точкам монтирования
# если не найденаточка монтирования "/boot" на отдельном устройстве, то завершается работа скрипта 
def selectSystemFSTab(fstab):
    print("search system partitions ...")
    fstab_system    = ["/", "/boot", "/home", "/tmp", "/usr", "/var", "/srv", "/opt", "/usr/local"]
    fstab_select    = []
    is_found_boot   = False
    
    for row_fstab in fstab:
        if len(row_fstab) < 6:
            continue
        if row_fstab[1] == "/boot":
            is_found_boot = True
            continue
        for  row_fstab_system in fstab_system:
            if row_fstab[1] == row_fstab_system:
                fstab_select.append(row_fstab)

    #printList("fstab_select", fstab_select)
    
    if is_found_boot:
        print("found separate boot mount point, OK")
    else:
        print("boot mount point not found, need separate boot mount point")
        exit(1) #----->
    
    print("search system partitions OK")
    return fstab_select


# конвертирует названия устройств в fstab в UUID формат
# @return: fstab UUID format
def convertFSTabToUUIDFSTab(fstab):
    print("convert fstab devices to UUID ...")
    blkid       = readBlkID()
    fstab_uuid  = []

    for row_fstab in fstab:
        for row_blkid in blkid:
            if  row_fstab[0] == row_blkid[0]:
                row_fstab[0] =  row_blkid[1]
                break
        fstab_uuid.append(row_fstab)

    #printList("fstab_uuid", fstab_uuid)
    print("convert fstab devices to UUID OK")
    return fstab_uuid


# добавляет к таблице fstab колонку слева с путями устройств /dev/ram[0..]
# @return: fstab_ram
def addRAMDevicesColumnToFSTab(fstab):
    print("add ram devices to fstab ...")
    fstab_ram   = []
    i           = 0
    for row_fstab in fstab:
        row_fstab.append("/dev/ram" + str(i))
        i = i + 1
        fstab_ram.append(row_fstab)

    #printList("fstab_ram", fstab_ram)
    print("add ram devices to fstab OK")
    return fstab_ram


# добавляет к таблице fstab колонку справа с размерами устройств /dev/ram[0..]
# @return: fstab_size
def addDevicesSizeColumnToFSTab(fstab):
    print("calculate partitions size ...")
    fstab_size  = []
    for row_fstab in fstab:
        size = executeShellCommand("blockdev --getsize64 /dev/disk/by-uuid/" + row_fstab[0])[0]
        if len(size) == 0:
            print("blockdev --getsize64 /dev/disk/by-uuid/" + row_fstab[0] + " return Null")
            exit(1)
        row_fstab.append(size)
        fstab_size.append(row_fstab)

    #printList("fstab_size", fstab_size)
    print("calculate partitions size OK")
    return fstab_size


# создает hook-обработчик, выполняемый при изменении initrd
def createHook(fstab):
    print("create " + file_name_hook + " ...")
    rootramfshook   = file_name_hook
    file_hook       = open(rootramfshook, "wt")
    loader_text     = []
    size            = 16 * 1024 * 1024
    i               = 1

    for row_fstab in fstab:
        size = size + int(row_fstab[6])

    print("required ram size: " + str(size) + " bytes")
    ram_total_text  = executeShellCommand("cat /proc/meminfo")
    ram_total       = 0

    for row_ram_total_text in ram_total_text:
        if row_ram_total_text[0:9] == "MemTotal:":
            ram_total = int(row_ram_total_text.replace("MemTotal:", "").replace("kB", "").replace(" ", ""))

    if ram_total == 0:
        print("error read MemTotal")
        exit(1)

    if ram_total * 1024 < size + 512 * 1024 * 1024:
        print("not enough memory, need to add another " + str((size + 512 * 1024 * 1024) - ram_total * 1024) + " bytes")
        exit(1)

    #создание скрипта initrd:/scripts/loader загрузки разделов в оперативку
    loader_text.append("mkdir -p /ram &&")
    loader_text.append("mount -t tmpfs -o size=" + str(size) + " none /ram &&")

    for row_fstab in fstab:
        device  = row_fstab[0].replace("UUID=", "")
        loader_text.append("echo 'load " + str(i) + " of " + str(len(fstab)) + " block device " + device + "' &&")
        loader_text.append("dd if=/dev/disk/by-uuid/" + device + " of=/ram/" + device + " bs=8388608 &&")
        i       = i + 1

    for row_fstab in fstab:
        if row_fstab[1] == "/":
            loader_text.append("mount -t " + row_fstab[2] + " -o loop /ram/" + row_fstab[0] + " /root &&")
            loader_text.append("mkdir -p /root/ram &&")
            loader_text.append("mount -o bind /ram /root/ram &&")

    loader_text.append("mount -o remount -o ro /root &&")
    loader_text.append("echo 'done' && sleep 1 && exit 0")
    loader_text.append("echo 'fail' && exit 1")
    
    #создание скрипта initrd-hook, /usr/share/initramfs-tools/hooks/rootramfshook
    #и вставка в него кода для создания скрипта initrd:/scripts/loader
    hook_text = []
    
# #!/bin/sh
# 
# set -e
# 
# PREREQ="cryptroot"
# 
# prereqs()
# {
# <------>echo "$PREREQ"
# }
# 
# case $1 in
# prereqs)
# <------>prereqs
# <------>exit 0
# <------>;;
# esac

    prereq_text = "" 
    prereq_text = prereq_text + "#!/bin/sh\n"
    prereq_text = prereq_text + "\n"
#     prereq_text = prereq_text + "set -e\n\n"
#     prereq_text = prereq_text + "PREREQ=\"cryptroot\"\n\n"
#     prereq_text = prereq_text + "prereqs()\n"
#     prereq_text = prereq_text + "{\n"
#     prereq_text = prereq_text + "\techo \"$PREREQ\"\n"
#     prereq_text = prereq_text + "}\n\n"
#     prereq_text = prereq_text + "case $1 in\n"
#     prereq_text = prereq_text + "prereqs)\n"
#     prereq_text = prereq_text + "\tprereqs\n"
#     prereq_text = prereq_text + "\texit 0\n"
#     prereq_text = prereq_text + "\t;;\n"
#     prereq_text = prereq_text + "esac\n\n"
    
    hook_text.append(prereq_text)
    
    hook_text.append('echo "\\n\\' + "\n")
    for row_loader in loader_text:
        hook_text.append(row_loader + '\\n\\' + "\n")
        
    hook_text.append('\n" >    $DESTDIR"' + file_name_loader + '" && ')   # + "\n"
    hook_text.append('chmod +x $DESTDIR"' + file_name_loader + '" && \n') # + "\n"
    
#     hook_text.append(
# ''' echo \'74c74,75
# < \tmount ${roflag} ${FSTYPE:+-t ${FSTYPE} }${ROOTFLAGS} ${ROOT} ${rootmnt}
# ---
# > \t#mount ${roflag} ${FSTYPE:+-t ${FSTYPE} }${ROOTFLAGS} ${ROOT} ${rootmnt}
# > \t/scripts/loader
# ' | patch -sf $DESTDIR"/scripts/local" || echo "fail patch"
# ''')

    patch_text = ""
    patch_text = patch_text + "cp \"" + file_name_fstab_rootramfs + "\" \"" + file_name_fstab +"\" && "
    patch_text = patch_text + "patch -sf $DESTDIR/scripts/local /usr/share/rootramfs/initrd.scripts.local.patch || echo \"SKIP\n\""
    patch_text = patch_text + "patch -sf /usr/share/initramfs-tools/hooks/cryptroot /usr/share/rootramfs/usr.share.initramfs-tools.hooks.cryptroot.patch || echo \"SKIP\n\""
#     patch_text = patch_text + "cp \"" + file_name_fstab_rootramfs + "\" \"" + file_name_fstab +"\""
#     patch_text = patch_text + " && echo -ne \"" 
#     patch_text = patch_text + "\x39\x32\x2c\x39\x33\x64\x39\x31"
#     patch_text = patch_text + "\x0a\x3c\x20\x09\x75\x6d\x6f\x75"
#     patch_text = patch_text + "\x6e\x74\x20\x24\x7b\x72\x6f\x6f"
#     patch_text = patch_text + "\x74\x6d\x6e\x74\x7d\x0a\x3c\x20"
#     patch_text = patch_text + "\x09\x2f\x73\x63\x72\x69\x70\x74"
#     patch_text = patch_text + "\x73\x2f\x6c\x6f\x61\x64\x65\x72\x0a\""
#     patch_text = patch_text + " | patch -sf $DESTDIR'/scripts/local' || echo 'fail patch initrd:/scripts/local'"

    hook_text.append(patch_text)
    file_hook.writelines(hook_text)
    
    executeShellCommand("chmod +x " + rootramfshook)
    print("create " + file_name_hook + " OK")
    #modify cryptsetup cryptroot hook
    executeShellCommand("patch -sf /usr/share/initramfs-tools/hooks/cryptroot /usr/share/rootramfs/usr.share.initramfs-tools.hooks.cryptroot.patch || echo \"SKIP\n\"")


def patchFSTab(fstab):
    print("create " + file_name_fstab_rootramfs + " ...")
    if not os.path.isfile(file_name_fstab_backup):
        print("backup " + file_name_fstab + " to " + file_name_fstab_backup)
        cp = executeShellCommand("cp " + file_name_fstab + " " + file_name_fstab_backup)
        if len(cp) > 0:
            print("error backup " + file_name_fstab + ": " + str(cp))

    file_fstab      = open(file_name_fstab)
    fstab_text      = file_fstab.readlines()
    fstab_text_ram  = []

    file_fstab.close()

    for row_fstab_text in fstab_text:
        is_found = False
        for row_fstab in fstab:
            if re.split(r"\s+", row_fstab_text)[1] == row_fstab[1]  and  row_fstab_text[0] != "#":
                is_found = True

                if is_found:
                    fstab_text_ram.append("#" + row_fstab_text)
                    fstab_text_ram.append("/ram/" + row_fstab[0] + "\t" + row_fstab[1] + "\t" + row_fstab[2] + "\t" + row_fstab[3] + ",loop\t0\n")
                    break

        if not is_found:
            fstab_text_ram.append(row_fstab_text)

    fstab_text_ram.append("\n")
    file_fstab = open(file_name_fstab_rootramfs, "wt")
    file_fstab.writelines(fstab_text_ram)
    print("create " + file_name_fstab_rootramfs + " OK")
    #printList("fstab_text_ram_rootramfs", fstab_text_ram_rootramfs)


def restore():
    #TODO: restore over patch fstab instead restore backup
    print("restore ...")
    if os.path.isfile(file_name_fstab_backup):
        print("restore  " + file_name_fstab_backup + " to " + file_name_fstab)
        mv = executeShellCommand("mv " + file_name_fstab_backup + " " + file_name_fstab)
        executeShellCommand("rm " + file_name_fstab_rootramfs)
        executeShellCommand("patch -sf /usr/share/initramfs-tools/hooks/cryptroot /usr/share/rootramfs/usr.share.initramfs-tools.hooks.cryptroot.unpatch || echo \"SKIP\n\"")
        if len(mv) > 0:
            print("error restore " + file_name_fstab + ": " + str(mv))
        else:
            executeShellCommand("/usr/bin/rootramfs.py --sync /")

    if os.path.isfile(file_name_hook):
        print("remove " + file_name_hook)
        rm = executeShellCommand("rm " + file_name_hook)
        if len(rm) > 0:
            print("error remove " + file_name_hook + ": " + str(mv))

    print("restore OK")


def onExit():
    if is_need_restore:
        restore()
    else:
        print("all done")

    printList("update-initramfs -u", executeShellCommand("update-initramfs -u"))


if len(sys.argv) == 3:
    dpkg_script     = sys.argv[1]
    dpkg_command    = sys.argv[2]
    print("scritp:  " + dpkg_script)
    print("command: " + dpkg_command)

    if dpkg_script == "postinst":
        atexit.register(onExit)
        if dpkg_command == "configure":
            is_need_restore = True
            fstab = readFSTab()
            printList("fstab", fstab)
            fstab = selectSystemFSTab(fstab)
            printList("fstab", fstab)
            fstab = convertFSTabToUUIDFSTab(fstab)
            printList("fstab", fstab)
            fstab = addDevicesSizeColumnToFSTab(fstab)
            printList("fstab", fstab)

            createHook(fstab)
            patchFSTab(fstab)
            is_need_restore = False

        if dpkg_command == "abort-upgrade"  or  dpkg_command == "abort-remove"  or  dpkg_command == "abort-deconfigure":
            is_need_restore = True

    if dpkg_script == "prerm":
        atexit.register(onExit)
#        if dpkg_command == "remove"  or  
#            dpkg_command == "purge"  or  
#            dpkg_command == "upgrade"  or  
#            dpkg_command == "failed-upgrade"  or  
#            dpkg_command == "abort-install"  or  
#            dpkg_command == "abort-upgrade"  or  
#            dpkg_command == "disappear":
        is_need_restore = True
