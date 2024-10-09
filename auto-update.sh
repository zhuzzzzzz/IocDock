#!/bin/bash

#######   Do As Following Instructions!!!   #######





#
script_abs=$(readlink -f "$0")
script_dir=$(dirname $script_abs)


# installing shell command completion.
cd imtools/command-completion
# !!!
script_abs_temp=$script_abs
script_dir_temp=$script_dir
. install-command-completion.sh
script_abs=$script_abs_temp
script_dir=$script_dir_temp
cd $script_dir


# set environment variable and add command searching path.
file_path=/etc/profile.d/IocManagerInstaller.sh
echo export MANAGER_PATH=$(pwd) > $file_path
if echo "$PATH" | grep -q "$(pwd)"; then
	echo "$(pwd) is already set in searching \$PATH."
else
	echo export PATH=\$PATH:$(pwd) >> $file_path
	echo "add searching path PATH=\$PATH:$(pwd)."
fi
source $file_path


# update IOC settings from old version to new version.
update_flag='true'
if [ "$update_flag" == 'true' ]; then
	./IocManager.py exec -b
	./IocManager.py update
fi


#
echo "Update finished."
# 


