#!/bin/bash

#######   Do As Following Instructions!!!   #######




# for shell command completion.
cd imtools
. install-command-completion.sh
cd ..


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


# 


