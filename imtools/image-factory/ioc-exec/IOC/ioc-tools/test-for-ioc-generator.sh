#!/bin/bash

script_abs=$(readlink -f "$0")
script_dir=$(dirname $script_abs)

top_dir=$script_dir/..

echo "uninstall and re-install all IOC ..."
cd $top_dir
for item in `ls`
do
	if test -d $item -a -d $item/iocBoot
	then
		cd $item
		make distclean &> /dev/null
		make &> /dev/null
		if test $? -eq 0
		then
			echo IOC $item successfully installed.
		else
			echo IOC $item install failed.
		fi
		cd $top_dir
	fi
done


