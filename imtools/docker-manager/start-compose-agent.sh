#!/bin/bash

echo Stop Compose project first if exists. 
docker compose -f compose-agent.yaml down
echo Start Compose project. 
docker compose -f compose-agent.yaml up -d
