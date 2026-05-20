#!/bin/bash

set -x

current_user="${SUDO_USER:-$USER}"
program_user="iocdock"

systemctl stop IocDockServer.service
systemctl disable IocDockServer.service
rm /etc/systemd/system/IocDockServer.service
systemctl daemon-reload

rm /etc/bash_completion.d/IocManagerCompletion
rm /usr/local/bin/IocManager
rm -f /etc/sudoers.d/IocDock
rm /etc/profile.d/IocDockSetup.sh

gpasswd -d "$current_user" "$program_user"
gpasswd -d "$program_user" docker

set +x

# finished.
echo uninstallation finished, you may need to re-login or reboot the system.
#