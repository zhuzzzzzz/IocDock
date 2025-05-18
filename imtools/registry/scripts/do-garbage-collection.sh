#!/bin/bash

# ./do-garbage-collection.sh [--dry-run] [--delete-untagged] [--quiet]


stack_name=$(IocManager config PREFIX_STACK_NAME)
repository_name=$(IocManager config REGISTRY_COMMON_NAME)


echo "Remove running registry instances."
docker service rm ${stack_name}_srv-registry &> /dev/null

echo "Executing garbage collection."
docker run \
	-v `pwd`/garbage-collection-config.yaml:/etc/distribution/config.yml \
        -v `pwd`/../../../../registry-data:/var/lib/registry \
	m.daocloud.io/docker.io/registry:3.0.0 \
	garbage-collect /etc/distribution/config.yml "$*"

echo 
