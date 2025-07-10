#!/bin/bash

script_abs=$(readlink -f "$0")
script_dir=$(dirname $script_abs)

base_version=7.0.8.1
release_prefix=image.dals
release_version=beta-0.2.3


# Check if the script is running as root.
if [ "$EUID" -ne 0 ]; then
    echo "This script must be run as root. "
    exit 1
fi


# Build image for EPICS base.
cd base
if [ -z `ls | grep "$base_version.tar.gz"` ]; then
	echo \"base-$base_version.tar.gz\" not found in \"base/\" dir.
	exit 1
fi
docker build --build-arg BASE=base-$base_version -t base:$release_version .
if [ $? -ne 0 ]; then 
	echo \"build image \"base:$release_version\" failed.\"
	exit 1
fi
cd $script_dir


# Build image for ioc-exec.
cd ioc-exec
docker build --build-arg BASE_IMAGE=base:$release_version -t ioc-exec:$release_version .
if [ $? -ne 0 ]; then 
	echo \"build image \"ioc-exec:$release_version\" failed.\"
	exit 1
fi
cd $script_dir


# if $release_prefix defined, tag and push images to registry.
if [ -n "$release_prefix" ]; then 
	docker image tag base:$release_version $release_prefix/base:$release_version
	docker image tag ioc-exec:$release_version $release_prefix/ioc-exec:$release_version
	docker image push $release_prefix/base:$release_version
	docker image push $release_prefix/ioc-exec:$release_version
fi





