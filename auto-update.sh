#!/bin/bash

#######   Do As Following Instructions!!!   #######






script_abs=$(readlink -f "$0")
script_dir=$(dirname $script_abs)


# for shell command completion.
cd imtools/command-completion

# !!!
script_abs_temp=$script_abs
script_dir_temp=$script_dir
. install-command-completion.sh
script_abs=$script_abs_temp
script_dir=$script_dir_temp
cd $script_dir

# add command search path and set environment variable.
file_path=/etc/profile.d/IocManagerInstaller.sh
echo export MANAGER_PATH=$(pwd) > $file_path
if echo "$PATH" | grep -q "$(pwd)"; then
	echo "$(pwd) is already set in \$PATH."
else
	echo export PATH=\$PATH:$(pwd) >> $file_path
	echo "set PATH=\$PATH:$(pwd)."
fi
source $file_path

echo "Update finished."
# 


