#!/bin/bash

print_log=false
push_image=false
no_build=false
build_args=()

# load extra build args from .buildargs if present
if [ -f "$build_dir/.buildargs" ]; then
    while IFS= read -r line || [ -n "$line" ]; do
        line="${line#"${line%%[![:space:]]*}"}"
        line="${line%"${line##*[![:space:]]}"}"
        [[ -z "$line" || "$line" =~ ^# ]] && continue
        if [[ ! "$line" =~ ^[A-Za-z_][A-Za-z0-9_]*= ]]; then
            echo "Warning: skipping invalid .buildargs entry: '$line'"
            continue
        fi
        build_args+=(--build-arg "$line")
    done < "$build_dir/.buildargs"
fi

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
        --no-build)
            no_build=true
            shift
            ;;
        --build-arg=*)
            build_args+=(--build-arg "${1#--build-arg=}")
            shift
            ;;
        *)
            echo "Unknown option: $1"
            echo "Usage: $0 [--release=VERSION] [--print-log] [--push-image] [--no-build] [--build-arg=KEY=VALUE]"
            exit 1
            ;;
    esac
done

if [ "$no_build" = true ]; then
    if ! docker image inspect "$image_name:$release_version" >/dev/null 2>&1; then
        echo Local image \"$image_name:$release_version\" not found, build it before pushing.
        exit 1
    fi
    echo Skip building, use local image \"$image_name:$release_version\".
else
    echo Building image \"$image_name:$release_version\"...
    if [ "$print_log" = true ]; then
        set -x
        docker build --progress=plain "${build_args[@]}" \
        -t "$image_name:$release_version" "$build_dir" 2>&1 | tee "BuildLog.$image_name:$release_version"
        return_code=${PIPESTATUS[0]}
        { set +x; } 2>/dev/null
    else
        set -x
        docker build "${build_args[@]}" -t "$image_name:$release_version" "$build_dir"
        return_code=$?
        { set +x; } 2>/dev/null
    fi

    if [ $return_code -ne 0 ]; then
        echo Build image \"$image_name:$release_version\" failed.
        exit 1
    else
        echo Build image \"$image_name:$release_version\" succeeded.
    fi
fi

if [ "$push_image" = true ]; then
    release_prefix=`IocManager config REGISTRY_COMMON_NAME`
    if [ -n "$release_prefix" ]; then
        echo Try to tag and push image to registry...
        set -x
        docker image tag "$image_name:$release_version" "$release_prefix/$image_name:$release_version"
        return_code=$?
        { set +x; } 2>/dev/null
        if [ $return_code -ne 0 ]; then
            echo Tag image \"$image_name:$release_version\" failed.
            exit 1
        fi
        set -x
        docker image push "$release_prefix/$image_name:$release_version"
        return_code=$?
        { set +x; } 2>/dev/null
        if [ $return_code -ne 0 ]; then
            echo Push image \"$release_prefix/$image_name:$release_version\" failed.
            exit 1
        fi
    fi
fi
