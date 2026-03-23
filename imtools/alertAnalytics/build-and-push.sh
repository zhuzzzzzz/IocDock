#!/bin/bash

image_name="alert-analytics"
release_version=0.1.1
print_log=false
push_image=false

# Parse command-line arguments
while [[ $# -gt 0 ]]; do
    case "$1" in
        --release=*)
            release_version="${1#*=}"
            shift
            ;;
        --print-log)
            print_log=true
            shift 
            ;;
        --push-image)
            push_image=true
            shift
            ;;
        *)
            echo "Unknown option: $1"
            echo "Usage: $0 [--release=VERSION] [--print-log] [--push-image]"
            exit 1
            ;;
    esac
done

echo Building image \"$image_name:$release_version\"...
# build image for alert-analytics
if [ "$print_log" = true ]; then
    set -x
    docker build --progress=plain \
    -t $image_name:$release_version . 2>&1 | tee BuildLog.$image_name:$release_version
    return_code=${PIPESTATUS[0]}
    { set +x; } 2>/dev/null
else
    set -x
    docker build -t $image_name:$release_version .
    return_code=$?
    { set +x; } 2>/dev/null
fi

if [ $return_code -ne 0 ]; then 
	echo Build image \"$image_name:$release_version\" failed.
	exit 1
else
	echo Build image \"$image_name:$release_version\" succeeded.
fi

if [ "$push_image" = true ]; then 
    # push image if $push_image is true and $release_prefix is defined
    release_prefix=`IocManager config REGISTRY_COMMON_NAME`
    # tag and push image to registry
    if [ -n "$release_prefix" ]; then
        echo Try to tag and push image to registry...
        set -x
        docker image tag $image_name:$release_version $release_prefix/$image_name:$release_version
        docker image push $release_prefix/$image_name:$release_version
        { set +x; } 2>/dev/null
    fi
fi