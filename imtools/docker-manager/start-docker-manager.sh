#!/bin/bash

echo Stop Compose project first if exists. 
docker compose down
echo Start Compose project. 
docker compose up -d
