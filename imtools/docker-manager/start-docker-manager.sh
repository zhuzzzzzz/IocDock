#!/bin/bash

if [ ! $(hostname) == 'docker-manager'  -a ! $1 == '-f'  ]; then
	echo Failed. docker-manager should only run in host docker-manager!
	exit
fi

echo Stop Compose project first if exists. 
docker compose -f compose-server.yaml down
docker compose -f compose-registry.yaml down
echo Start Compose project. 
docker compose -f compose-server.yaml up -d
docker compose -f compose-registry.yaml up -d
