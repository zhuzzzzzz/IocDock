#!/bin/bash

script_abs=$(readlink -f "$0")
script_dir=$(dirname $script_abs)

echo "uninstall all modules ..."
for item in `ls`
do
	if test -d $item -a -d $item/lib
	then
		cd $item
		make distclean &> /dev/null
		cd $script_dir
	fi
done

echo "executing automake.sh ..."
./automake.sh install |& grep -i -e "check_install" -e "move to path" -e "successfully installed" -e "install failed" -e "already installed" -e "set to install, but not found" -e "dependency check failed" \
 -e "EPICS_BASE not defined" -e "needed by" -e "needs no other package" -e "not found." -e "found but not an epics module" 
