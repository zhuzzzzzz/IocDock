#!/bin/bash

# ./automake.sh pack
# ./automake.sh uninstall
# ./automake.sh install

# Edit here to choose which module to be installed, then edit checkDependency.sh to set dependency correctly.
# ordered name(path name) list of modules to be installed, set this variable if add new modules.
#modules_to_install=("asyn" "StreamDevice")
modules_to_install=("seq" "asyn" "autosave" "caPutLog" "iocStats" "StreamDevice" "modbus" "s7nodave" "BACnet")



script_abs=$(readlink -f "$0")
script_dir=$(dirname $script_abs)

# set arg "pack" to package and compress the reviewed EPIECS modules.
if [ "$1" == "pack" ]; then
	./automake.sh uninstall
	for item in ${modules_to_install[*]}
	do
		zip -r $item.zip $item-*/ &> /dev/null
		if [ $? -eq 0 ]; then 
			echo "$item" are packed.
		else
			echo Failed to pack "$item".
			exit 1
		fi
	done
	echo 'all reviewed EPIECS modules are packed.'
	for item in ${modules_to_install[*]}
	do
		echo remove dir \"$item-*/\".
		rm -rf $item-*
	done
	exit 0
fi

# set arg "uninstall" to uninstall all EPIECS modules.
if [ "$1" == "uninstall" ]; then
	echo uninstall all the reviewed EPIECS modules firstly ...
	for item in ${modules_to_install[*]}
	do
		if test -d $item-* -a -d $item-*/lib; then
			cd $item-*
			make distclean &> /dev/null
			if [ $? -eq 0 ]; then 
				echo "$item" are unistalled.
			else
				echo Failed to unistall "$item".
				exit 1
			fi
			cd $script_dir
		fi
	done
	echo remove RELEASE.local ...
	rm RELEASE.local -f
	exit 0
fi

# set arg "install" to install all EPIECS modules.
if [ "$1" != "install" ]; then
	echo 'Unrecognized parameters.'
	exit 1
else
	for item in `ls | grep .zip`
	do
		unzip -o $item &> /dev/null
		if [ $? -eq 0 ]; then 
			echo "$item" are unpacked.
		else
			echo Failed to unpack "$item".
			exit 1
		fi
	done
fi

# check modules and execute make to install, accept only one input arg: relative module dir path.
check_install(){
if test $# -eq 0 
then
	echo check_install got no input argument.
elif test $# -gt 1 
then
	echo check_install only accpet one argument, but "$#" were given: "$*".
else
	#echo `readlink -f $1`
	# if a sub-directory lib/ exists, assume it has been installed.
	if test -d $1 -a -d $1/lib
	then
		echo $1 has already installed, skipped.
	elif test -d $1
	then
		echo move to path \"$1/\" to install ...
		cd $script_dir/$1
		make
		if test $? -eq 0
		then
			echo $1 successfully installed.
		else
			echo $1 install failed.
		fi
		cd $script_dir
	fi
fi
}


for item in ${modules_to_install[*]}
do
	./checkDependency.sh $item
	if [ $? -eq 0 ]
	then
		pkg=`ls | grep -i $item-`
		if test -z $pkg
		then
			echo $item was set to install, but not found!
		else
			check_install $pkg
		fi
	else
		echo "dependency check failed for $item, execute automake.sh stopped."
	fi
done






