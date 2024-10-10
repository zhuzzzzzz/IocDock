#!/bin/bash

# run "./make-test-project.sh make" to generate IOC project test cases for compose deploy.
# run "./make-test-project.sh make swarm" to generate IOC project test cases for swarm deploy.
# run "./make-test-project.sh del" to delete IOC project test cases.

# set variables below to change generating configureation.
base_image="image.dals/base:beta-0.2.2"
ioc_image="image.dals/ioc-exec:beta-0.2.2"
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
	if [ "$2" == "swarm" ]; then
		# make test projects for swarm deploy.
		for item in "${create_host[@]}"; do 
			create_prefix=${item}_
			for ((i=1; i<=$create_num; i++)); do
				echo 
				echo "####### $create_prefix$i #######" 
				# create IOC project
				./IocManager.py create "$create_prefix$i" -f "./imtools/template/test/ioc.ini"
				# add source files
				./IocManager.py exec "$create_prefix$i" --add-src-file --src-path ./imtools/template/test
				# set options
				./IocManager.py set "$create_prefix$i" -s db -o "load = ramper.db, name=$create_prefix$i; ramper.db, name=$create_prefix$i:2"
				./IocManager.py set "$create_prefix$i" -o " host = swarm"
				./IocManager.py set "$create_prefix$i" -o " image = $ioc_image "
				# add set options here..
				
				
				# generate startup files
				./IocManager.py exec "$create_prefix$i" --gen-startup-file 
				# copy files to default mount path 
				./IocManager.py exec "$create_prefix$i" -e --force-overwrite
			done
		done
		echo 
		echo "####### something occurs below if IOC run-check failed #######" 
		./IocManager.py exec "$create_prefix$i" --run-check
		echo
		echo "####### generate compose files in default mount path #######"
		# generate compose files for swarm deploying
		./IocManager.py exec --gen-swarm-file --ioc-list alliocs
	else
		# default make test projects for compose deploy.
		for item in "${create_host[@]}"; do 
			create_prefix=${item}_
			for ((i=1; i<=$create_num; i++)); do
				echo 
				echo "####### $create_prefix$i #######" 
				# create IOC project
				./IocManager.py create "$create_prefix$i" -f "./imtools/template/test/ioc.ini"
				# add source files
				./IocManager.py exec "$create_prefix$i" --add-src-file --src-path ./imtools/template/test
				# set options
				./IocManager.py set "$create_prefix$i" -s db -o "load = ramper.db, name=$create_prefix$i; ramper.db, name=$create_prefix$i:2"
				./IocManager.py set "$create_prefix$i" -o " host = $item "
				./IocManager.py set "$create_prefix$i" -o " image = $ioc_image "
				# add set options here..
				
				
				# generate startup files and export to default mount path.
				./IocManager.py exec "$create_prefix$i" --generate-and-export --force-overwrite 
			done
		done
		echo 
		echo "####### something occurs below if IOC run-check failed #######" 
		./IocManager.py exec "$create_prefix$i" --run-check
		echo
		echo "####### generate compose files in default mount path #######"
		# generate compose files in default mount path 
		./IocManager.py exec --gen-compose-file --hosts ${create_host[@]} --base $base_image
	fi
fi


