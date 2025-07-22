#!/bin/bash

declare -A image_dict
image_dict["registry:3.0.0"]="m.daocloud.io/docker.io/registry:3.0.0"
image_dict["cadvisor:v0.52.1"]="m.daocloud.io/gcr.io/cadvisor/cadvisor:v0.52.1"
image_dict["node-exporter:v1.9.1"]="quay.io/prometheus/node-exporter:v1.9.1"
image_dict["alloy:v1.9.2"]="m.daocloud.io/docker.io/grafana/alloy:v1.9.2"
image_dict["prometheus:v3.5.0"]="m.daocloud.io/docker.io/prom/prometheus:v3.5.0"
image_dict["alertmanager:v0.28.1"]="m.daocloud.io/docker.io/prom/alertmanager:v0.28.1"
image_dict["grafana:12.0.2-ubuntu"]="m.daocloud.io/docker.io/grafana/grafana:12.0.2-ubuntu"
image_dict["loki:3.5.2"]="m.daocloud.io/docker.io/grafana/loki:3.5.2"
image_dict["busybox:1.37.0"]="m.daocloud.io/docker.io/busybox:1.37.0"

set -x


for item in $image_list; do
    docker pull $item
done
