#!/bin/sh

set -e

. /scripts/AlertManagerVar

. /var/tmp/IocDock/NodeInfo

if [[ "$ALERT_MANAGER_MASTER_IP" == "$NODE_IP" ]]; then
    set -- /bin/alertmanager --cluster.listen-address=$ALERT_MANAGER_MASTER_IP_PORT "$@"
else
    set -- /bin/alertmanager --cluster.peer=$ALERT_MANAGER_MASTER_IP_PORT "$@" 
fi

echo "$@"
sleep 3
exec "$@"
