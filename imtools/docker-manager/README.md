



- Scripts ```set-docker-environment.sh``` should be run as root!
- $REGISTRY_IP and $REGISTRY_NAME in set-docker-environment.sh should be set according to settings of manager server.
- Run ```./set-docker-environment.sh``` only once for new system of workers.
- Run ```./set-docker-environment.sh manager``` only once for new system of manager.
- Run ```./start-docker-manager.sh``` to start/restart portainer manager and registry server.
- Run ```./start-compose-agent.sh``` to start/restart portainer portainer agent.
- Execute ```docker compose down``` in this directory to stop server.
