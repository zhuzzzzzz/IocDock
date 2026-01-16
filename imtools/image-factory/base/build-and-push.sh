#!/bin/bash

base_version=7.0.8.1
release_version=1.0.0
print_log=false

# Parse command-line arguments
while [[ $# -gt 0 ]]; do
    case "$1" in
        --base=*)
            base_version="${1#*=}"
            shift
            ;;
        --release=*)
            release_version="${1#*=}"
            shift
            ;;
        --print-log)
            print_log=true
            shift
            ;;
        *)
            echo "Unknown option: $1"
            echo "Usage: $0 [--base=VERSION] [--release=VERSION] [--print-log]"
            exit 1
            ;;
    esac
done

echo Building image \"base:$release_version\"...

# try to download EPICS base tarball
if [ -z `ls | grep "base-$base_version.tar.gz"` ]; then
    echo \"base-$base_version.tar.gz\" not found in \"base\" dir.
    echo Attempting to download base-$base_version.tar.gz...
    if ! wget https://epics.anl.gov/download/base/base-$base_version.tar.gz; then
        echo Download failed.
        exit 1
    fi
    echo Successfully downloaded \"base-$base_version.tar.gz\".
else
    echo Found \"base-$base_version.tar.gz\".
fi

# verify base.tar.gz before using it
echo "Verifying \"base-$base_version.tar.gz\"..."
if ! tar -tzf "base-$base_version.tar.gz" >/dev/null 2>&1; then
    echo "Verification failed for base-$base_version.tar.gz, removing this file..."
    rm -f "base-$base_version.tar.gz"
    exit 1
fi
echo "Verification passed for \"base-$base_version.tar.gz\"."

# build image for EPICS base
if [ "$print_log" = true ]; then
    set -x
    docker build --progress=plain \
    --build-arg BASE=base-$base_version \
    -t base:$release_version . 2>&1 | tee BuildLog.base:$release_version
    return_code=${PIPESTATUS[0]}
    { set +x; } 2>/dev/null
else
    set -x
    docker build --build-arg BASE=base-$base_version -t base:$release_version .
    return_code=$?
    { set +x; } 2>/dev/null
fi

if [ $return_code -ne 0 ]; then 
	echo Build image \"base:$release_version\" failed.
	exit 1
else
	echo Build image \"base:$release_version\" succeeded.
fi

# push image if $release_prefix is defined
release_prefix=`IocManager config REGISTRY_COMMON_NAME`
# tag and push image to registry
if [ -n "$release_prefix" ]; then
    echo Try to tag and push image to registry...
    set -x
	docker image tag base:$release_version $release_prefix/base:$release_version
	docker image push $release_prefix/base:$release_version
    { set +x; } 2>/dev/null
fi