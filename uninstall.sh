#!/bin/bash

set -x

rm /etc/bash_completion.d/IocManagerCompletion

rm /etc/profile.d/IocDockSetup.sh

rm /usr/bin/IocManager

systemctl stop IocDockServer.service
systemctl disable IocDockServer.service
rm /etc/systemd/system/IocDockServer.service

set +x

# finished.
echo uninstallation finished, you may need to re-login or reboot the system.
#