#!/bin/bash

script_abs=$(readlink -f "$0")
script_dir=$(dirname $script_abs)

modules_arg=""
for arg in "$@"; do
	case $arg in
		--modules=*) modules_arg="$arg" ;;
	esac
done

echo "uninstall all modules ..."
for item in `ls`
do
	if test -d $item -a -d $item/lib
	then
		cd $item
		make distclean > /dev/null || echo "WARNING: distclean failed for $item"
		cd $script_dir
	fi
done

echo "executing automake.sh ..."
if [ -n "$modules_arg" ]; then
	./automake.sh "$modules_arg" install |& grep -i -e "check_install" -e "move to path" -e "successfully installed" -e "install failed" -e "already installed" \
	 -e "EPICS_BASE not defined" -e "needed by" -e "needs no other package" -e "not found." -e "found but not an epics module" \
	 -e "failed to unpack" -e "unpacked successfully"
else
	./automake.sh install |& grep -i -e "check_install" -e "move to path" -e "successfully installed" -e "install failed" -e "already installed" \
	 -e "EPICS_BASE not defined" -e "needed by" -e "needs no other package" -e "not found." -e "found but not an epics module" \
	 -e "failed to unpack" -e "unpacked successfully"
fi
