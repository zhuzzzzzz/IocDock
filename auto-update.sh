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
script_abs=$(readlink -f "$0")
script_dir=$(dirname $script_abs)


# installing shell command completion.
echo installing shell command completion...
cd imtools/command-completion
# !!!
script_abs_temp=$script_abs
script_dir_temp=$script_dir
. install-command-completion.sh
script_abs=$script_abs_temp
script_dir=$script_dir_temp
cd $script_dir


# set environment variable. 
echo setting environment variable...
repository_path=$script_dir/ioc-repository/
mount_path=$script_dir/../ioc-for-docker/
file_path=/etc/profile.d/IocManagerInstaller.sh
echo "export MANAGER_PATH=$script_dir" > $file_path
echo "export REPOSITORY_PATH=$repository_path" >> $file_path # $REPOSITORY_PATH for finding IOC projects.
echo "export MOUNT_PATH=$mount_path" >> $file_path # $MOUNT_PATH for finding hosts.
source $file_path
# add command soft link.
echo making command soft link...
ln -sf $script_dir/IocManager.py /usr/bin/IocManager


#
echo "Update finished. You may need to reboot to make some settings to take effect."
# 


