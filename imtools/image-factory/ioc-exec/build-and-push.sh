#!/bin/bash

script_abs=$(readlink -f "$0")
script_dir=$(dirname $script_abs)

base_version=7.0.8.1 # If base image is not exist, this variable will be used to set the base tarball version.
base_release_version=1.0.0 # From which release version of base image this image will be built.
release_version=1.0.0 # Default release version.

# Parse command-line arguments
while [[ $# -gt 0 ]]; do
    case "$1" in
        --base-version=*)
            base_version="${1#*=}"
            shift
            ;;
        --base-release=*)
            base_release_version="${1#*=}"
            shift
            ;;
        --release=*)
            release_version="${1#*=}"
            shift
            ;;
        --modules=*)
            install_modules="${1#*=}"
            shift
            ;;
        *)
            echo "Unknown option: $1"
            echo "Usage: $0 [--base-version=VERSION] [--base-release=VERSION] [--release=VERSION]"
            exit 1
            ;;
    esac
done

# prepare base image
IMAGE_NAME=base:$base_release_version
if docker images --format "{{.Repository}}:{{.Tag}}" | grep -q "^${IMAGE_NAME}$"; then
    echo "Find EPICS base image \"$IMAGE_NAME\"."
else
    echo "EPICS base image \"$IMAGE_NAME\" does not exist. Try to build it..."
    set -ex
    cd ../base
    ./build-and-push.sh --base=$base_version --release=$base_release_version
    cd $script_dir
    set +ex
fi

# build image for IOC execution environment
echo Building image \"ioc-exec:$release_version\"...
set -x
docker build --progress=plain \
--build-arg BASE_RELEASE_VERSION=$base_release_version \
--build-arg INSTALL_MODULES=$install_modules \
-t ioc-exec:$release_version . 2>&1 | tee build.log
return_code=${PIPESTATUS[0]}
set +x
if [ $return_code -ne 0 ]; then 
	echo Build image \"ioc-exec:$release_version\" failed.
	exit 1
fi


# push image if $release_prefix is defined
release_prefix=`IocManager config REGISTRY_COMMON_NAME`
# tag and push image to registry
if [ -n "$release_prefix" ]; then 
	docker image tag ioc-exec:$release_version $release_prefix/ioc-exec:$release_version
	docker image push $release_prefix/ioc-exec:$release_version
fi