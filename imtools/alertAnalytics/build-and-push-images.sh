#!/bin/bash

script_abs=$(readlink -f "$0")
script_dir=$(dirname $script_abs)

release_prefix=`IocManager config REGISTRY_COMMON_NAME`
release_version=0.1.0

# Build image for alertAnalytics.
docker build -t alert-analytics:$release_version .
if [ $? -ne 0 ]; then 
	echo \"build image \"alert-analytics:$release_version\" failed.\"
	exit 1
fi


# if $release_prefix defined, tag and push images to registry.
if [ -n "$release_prefix" ]; then 
	docker image tag alert-analytics:$release_version $release_prefix/alert-analytics:$release_version
	docker image push $release_prefix/alert-analytics:$release_version
fi