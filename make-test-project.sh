#!/bin/bash

# run "./make-test-project.sh make" to generate IOC project test cases for swarm deploy.
# run "./make-test-project.sh make swarm" to generate IOC project test cases for swarm deploy.
# run "./make-test-project.sh del" to delete IOC project test cases.

# command for testing communication of generated projects.
# camonitor ramper:worker_test_1 ramper:worker_test_2 ramper:worker_test_3 ramper:worker_test_4 ramper:worker_test_5 


# set variables below to change generating configureation.
base_image="image.dals/base:beta-0.2.2"
ioc_image="image.dals/ioc-exec:beta-0.2.2"
create_ioc=("worker_test_1" "worker_test_2" "worker_test_3" "worker_test_4" "worker_test_5")


if [ "$1" == 'delete' -o "$1" == 'del' ]; then
	verbose="-v"
	for item in "${create_ioc[@]}"; do 
		./IocManager.py remove "$item" -rf $verbose
		verbose=""
	done
elif [ "$1" == 'create' -o "$1" == 'make' ]; then
	#  remove first.
	verbose="-v"
	for item in "${create_ioc[@]}"; do 
		./IocManager.py remove "$item" -rf $verbose
		verbose=""
	done
	# make
	verbose="-v"
	if [ "$2" == "swarm" -o "$2" == "" ]; then
		# make test projects for swarm deploy.
		for item in "${create_ioc[@]}"; do 
			echo 
			echo "####### $item #######" 
			# create IOC project
			./IocManager.py create "$item" -f "./templates/test/ioc.ini" $verbose
			# add source files
			./IocManager.py exec "$item" --add-src-file ./templates/test $verbose
			# set options
			./IocManager.py set "$item" -s db -o "load = ramper.db, name=$item" $verbose
			./IocManager.py set "$item" -o " host = swarm" $verbose
			./IocManager.py set "$item" -o " image = $ioc_image " $verbose
			./IocManager.py set "$item" -s deploy -o "memory-reserve=100M" $verbose
			./IocManager.py set "$item" -s deploy -o "labels=test=true" $verbose
			# add set options here..
			
			
			
			# generate startup files
			./IocManager.py exec "$item" --gen-startup-file $verbose
			# copy files to default mount path 
			./IocManager.py exec "$item" --export-for-mount --force-overwrite $verbose
			# generate compose file for swarm deploying
			./IocManager.py exec "$item" --gen-swarm-file $verbose
			# add snapshot
			./IocManager.py exec "$item" --add-snapshot-file $verbose
			verbose=""
		done
		echo
	fi
fi


