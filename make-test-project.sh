#!/bin/bash

# run "./make-test-project.sh make" to generate IOC project test cases for compose deploy.
# run "./make-test-project.sh make swarm" to generate IOC project test cases for swarm deploy.
# run "./make-test-project.sh del" to delete IOC project test cases.

# command for testing communication of generated projects.
# camonitor ramper:worker_test_1_1 ramper:worker_test_1_2 ramper:worker_test_1_3 ramper:worker_test_2_1 ramper:worker_test_2_2 ramper:worker_test_2_3 


# set variables below to change generating configureation.
base_image="image.dals/base:beta-0.2.2"
ioc_image="image.dals/ioc-exec:beta-0.2.2"
create_host=("worker_test_1" "worker_test_2")
create_num=3

verbose="-v"

if [ "$1" == 'delete' -o "$1" == 'del' ]; then
	for item in "${create_host[@]}"; do 
		create_prefix=${item}_
	    	for ((i=1; i<=$create_num; i++)); do
			./IocManager.py remove "$create_prefix$i" -rf $verbose
			verbose=""
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
				./IocManager.py create "$create_prefix$i" -f "./imtools/template/test/ioc.ini" $verbose
				# add source files
				./IocManager.py exec "$create_prefix$i" --add-src-file --src-path ./imtools/template/test $verbose
				# set options
				./IocManager.py set "$create_prefix$i" -s db -o "load = ramper.db, name=$create_prefix$i" $verbose
				./IocManager.py set "$create_prefix$i" -o " host = swarm" $verbose
				./IocManager.py set "$create_prefix$i" -o " image = $ioc_image " $verbose
				# add set options here..
				
				
				# generate startup files
				./IocManager.py exec "$create_prefix$i" --gen-startup-file $verbose
				# copy files to default mount path 
				./IocManager.py exec "$create_prefix$i" -e --force-overwrite $verbose
				verbose=""
			done
		done
		echo 
		echo "####### something occurs below if IOC run-check failed #######" 
		./IocManager.py exec --run-check -v
		echo
		echo "####### generate compose files in default mount path #######"
		# generate compose files for swarm deploying
		./IocManager.py exec alliocs --gen-swarm-file -v
	else
		# default make test projects for compose deploy.
		for item in "${create_host[@]}"; do 
			create_prefix=${item}_
			for ((i=1; i<=$create_num; i++)); do
				echo 
				echo "####### $create_prefix$i #######" 
				# create IOC project
				./IocManager.py create "$create_prefix$i" -f "./imtools/template/test/ioc.ini" $verbose
				# add source files
				./IocManager.py exec "$create_prefix$i" --add-src-file --src-path ./imtools/template/test $verbose
				# set options
				./IocManager.py set "$create_prefix$i" -s db -o "load = ramper.db, name=$create_prefix$i" $verbose
				./IocManager.py set "$create_prefix$i" -o " host = $item " $verbose
				./IocManager.py set "$create_prefix$i" -o " image = $ioc_image " $verbose
				# add set options here..
				
				
				# generate startup files and export to default mount path.
				./IocManager.py exec "$create_prefix$i" --generate-and-export --force-overwrite $verbose
				verbose=""
			done
		done
		echo 
		echo "####### something occurs below if IOC run-check failed #######" 
		./IocManager.py exec --run-check -v
		echo
		echo "####### generate compose files in default mount path #######"
		# generate compose files in default mount path 
		./IocManager.py exec --gen-compose-file --hosts ${create_host[@]} --base $base_image -v
	fi
fi


