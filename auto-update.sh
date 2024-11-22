#!/bin/bash

#######   Do As Following Instructions   #######
#
### If you want to update IOC settings from old version to new version, do as the followings. ###
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
file_path=/etc/profile.d/IocManagerInstaller.sh
echo export MANAGER_PATH=$(pwd) > $file_path
source $file_path
# add command soft link.
echo making command soft link...
ln -sf $script_dir/IocManager.py /usr/bin/IocManager


#
echo "Update finished."
# 


