#!/bin/bash

# check dependency for given module and create RELEASE.local file.

# define a dict for modules and their dependencies. 
declare -A module_dict
module_dict["StreamDevice"]="asyn " # asyn needed by StreamDevice.
module_dict["modbus"]="asyn " # asyn needed by modbus.
module_dict["s7nodave"]="asyn " # asyn needed by s7nodave.

# a dict form path name to module package name, used in RELEASE.loacl, to define which modules are needed to install current module. set this variable if necessary when new modules added. 
declare -A package_name
package_name["asyn"]="ASYN"



script_abs=$(readlink -f "$0")
script_dir=$(dirname $script_abs)

if [ $EPICS_BASE ]
then 
	echo EPICS_BASE=$EPICS_BASE > $script_dir/RELEASE.local
else

	echo EPICS_BASE not defined in system.
	exit 1
fi

modules_needed=${module_dict["$1"]}
read -ra modules_needed <<< "$modules_needed"

if [ -n "${modules_needed[*]}" ]
then
for module in "${modules_needed[@]}"
do	
	pkg=`ls | grep -i $module-`
	if test -n "$pkg" -a -d "$pkg/lib"
	then 
		echo ${package_name["$module"]}=$script_dir/$pkg >> $script_dir/RELEASE.local
		echo package \""$module"\" needed by \""$1"\".
	elif test  -n "$pkg" -a ! -d "$pkg/lib"
	then
		echo package \""$module"\" found but not an epics module.
		exit 1
	else
		echo package \""$module"\" not found.
		exit 1
	fi
done 
else
echo package \""$1"\" needs no other package.
fi





