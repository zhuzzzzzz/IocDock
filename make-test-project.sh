#!/bin/bash

# run "./make-test-project.sh make" to generate IOC project test cases.
# run "./make-test-project.sh del" to delete IOC project test cases.
# set variables below to change generating configureation.

base_image="image.dals/base:beta-0.1.1"
ioc_image="image.dals/ioc-exec:beta-0.1.1"
create_host=("worker-standard" "worker_test" "worker_test1" "worker_test2")
create_num=3


if [ "$1" == 'delete' -o "$1" == 'del' ]; then
	for item in "${create_host[@]}"; do 
		create_prefix=${item}_
	    	for ((i=1; i<=$create_num; i++)); do
			./IocManager.py remove "$create_prefix$i" -rf
		done
	done
elif [ "$1" == 'create' -o "$1" == 'make' ]; then
	for item in "${create_host[@]}"; do 
		create_prefix=${item}_
		for ((i=1; i<=$create_num; i++)); do
			echo 
			echo "####### $create_prefix$i #######" 
			# create IOC project
			./IocManager.py create "$create_prefix$i" -f "./imtools/template/test/test.ini"
			# add source files
			./IocManager.py exec "$create_prefix$i" -a --src-path ./imtools/template/test
			# set options
			./IocManager.py set "$create_prefix$i" -s db -o "load_a = ramper.db, name=$create_prefix$i" 
			./IocManager.py set "$create_prefix$i" -o " host = $item "
			./IocManager.py set "$create_prefix$i" -o " image = $ioc_image "
			# add set options here..
			
			
			# generate startup files
			./IocManager.py exec "$create_prefix$i" -s 
			# copy files to default mount path 
			./IocManager.py exec "$create_prefix$i" -e --force-overwrite
		done
	done
	echo 
	echo "####### something occurs below if IOC run-check failed #######" 
	for item in "${create_host[@]}"; do 
		create_prefix=${item}_
		echo 
		for ((i=1; i<=$create_num; i++)); do
			./IocManager.py exec "$create_prefix$i" --run-check
		done
	done
	echo
	echo "####### generate compose files in default mount path #######"
	# generate compose files in default mount path 
	./IocManager.py exec -c --base $base_image
fi


