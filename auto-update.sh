#!/bin/bash

#######   Do As Following Instructions   #######
#
### If you want to update IOC settings from old version to new version, do as followings. ###
## backup old IOC projects.
#	IocManager.py exec -b
## update IOC projects.
#	IocManager.py update
#


#
current_user="${SUDO_USER:-$USER}"
script_abs=$(readlink -f "$0")
script_dir=$(dirname $script_abs)


# installing shell command completion.
echo installing shell command completion...
cd imtools/command-completion
. install-command-completion.sh
cd $script_dir


# set environment variables. 
echo setting environment variables...
export MANAGER_PATH=$script_dir
repository_path=$(./IocManager.py config REPOSITORY_PATH)
if [ $? -ne 0 ]; then
    echo "Failed. Failed to get \"REPOSITORY_PATH\" in configuration file." >&2
    exit 1 
fi
mkdir $repository_path > /dev/null 2>&1
if [ $? -eq 0 ]; then
    chown $current_user:$current_user $repository_path
    chmod g+w $repository_path
fi
mount_path=$(./IocManager.py config MOUNT_PATH)
if [ $? -ne 0 ]; then
    echo "Failed. Failed to get \"MOUNT_PATH\" in configuration file." >&2
    exit 1 
fi
file_path=/etc/profile.d/IocDockSetup.sh
echo "export MANAGER_PATH=$script_dir" > $file_path
echo "export REPOSITORY_PATH=$repository_path" >> $file_path
echo "export MOUNT_PATH=$mount_path" >> $file_path

# set log file permission.
file_path=$(./IocManager.py config OPERATION_LOG_FILE_PATH)
if [ $? -eq 0 ]; then
    chown $current_user:$current_user $file_path
    chmod g+w $file_path
fi

# add command soft link.
echo making file soft link for command...
ln -sf $script_dir/IocManager.py /usr/bin/IocManager


# set nfs mounting.
# sudo vi /etc/exports
# /home/ubuntu/nfs-dir/IocDock-data 192.168.0.0/24(rw,sync,all_squash,no_subtree_check)
# sudo exportfs -a
# mount -t nfs ip-addr:/home/ubuntu/nfs-dir/IocDock-data dest-dir
# vi /etc/fstab
# server:/srv/nfs  /mnt/nfs_share  nfs  rw,_netdev,vers=4  0  0
# sudo mount -a

# finished.
echo "Update finished. To make some settings to take effect, you may need to re-open the shell or to reboot the system."
# 


