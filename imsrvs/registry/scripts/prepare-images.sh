#!/bin/bash

do_pull=true
do_push=true

# Parse command-line arguments
while [[ $# -gt 0 ]]; do
    case "$1" in
        --pull)
            do_pull=true
            do_push=false
            shift
            ;;
        --push)
            do_pull=false
            do_push=true
            shift
            ;;
        *)
            echo "Unknown option: $1"
            echo "Usage: $0 [--pull | --push]"
            exit 1
            ;;
    esac
done

release_prefix=`IocManager config REGISTRY_COMMON_NAME`
echo $release_prefix
if [ -z "$release_prefix" ]; then
    echo "Failed to get REGISTRY_COMMON_NAME, check settings.py."
    exit 1
fi

declare -A image_dict
image_dict["registry:3.0.0"]="m.daocloud.io/docker.io/registry:3.0.0"
image_dict["cadvisor:v0.57.0"]="ghcr.io/google/cadvisor:v0.57.0"
image_dict["node-exporter:v1.9.1"]="quay.io/prometheus/node-exporter:v1.9.1"
image_dict["alloy:v1.9.2"]="m.daocloud.io/docker.io/grafana/alloy:v1.9.2"
image_dict["prometheus:v3.5.0"]="m.daocloud.io/docker.io/prom/prometheus:v3.5.0"
image_dict["alertmanager:v0.28.1"]="m.daocloud.io/docker.io/prom/alertmanager:v0.28.1"
image_dict["grafana:12.0.2-ubuntu"]="m.daocloud.io/docker.io/grafana/grafana:12.0.2-ubuntu"
image_dict["loki:3.5.2"]="m.daocloud.io/docker.io/grafana/loki:3.5.2"
image_dict["busybox:1.37.0"]="m.daocloud.io/docker.io/busybox:1.37.0"
image_dict["nginx:1.28"]="m.daocloud.io/docker.io/nginx:1.28"

for key in "${!image_dict[@]}"; do
    value=${image_dict[$key]}
    if [ "$do_pull" = true ]; then
        set -x
        docker pull $value || { { set +x; } 2>/dev/null; echo "Failed to pull image \"$value\"."; exit 1; }
        docker tag $value $release_prefix/$key || { { set +x; } 2>/dev/null; exit 1; }
        { set +x; } 2>/dev/null
    fi
    if [ "$do_push" = true ]; then
        if ! docker image inspect $release_prefix/$key >/dev/null 2>&1; then
            echo "Local image \"$release_prefix/$key\" not found, run \"$0 --pull\" first."
            exit 1
        fi
        set -x
        docker push $release_prefix/$key || { { set +x; } 2>/dev/null; echo "Failed to push image \"$release_prefix/$key\"."; exit 1; }
        { set +x; } 2>/dev/null
    fi
done
