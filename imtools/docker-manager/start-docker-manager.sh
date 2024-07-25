#!/bin/bash

if [ ! $(hostname) == 'docker-manager'  -a ! $1 == '-f'  ]; then
	echo Failed. docker-manager should only run in host docker-manager!
	exit
fi

echo Stop Compose project first if exists. 
docker compose down
echo Start Compose project. 
docker compose up -d
