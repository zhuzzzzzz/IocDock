#!/bin/bash

if [ "$(id -u)" -ne 0 ]; then
    echo "error: this script must be run as root." >&2
    exit 1
fi

current_user="${SUDO_USER:-$USER}"
program_user="iocdock"
install_dir="/opt/IocDockHome/IocDock"

set -x

systemctl stop IocDockServer.service
systemctl disable IocDockServer.service
rm -f /etc/systemd/system/IocDockServer.service
rm -f /tmp/IocDock.sock
systemctl daemon-reload

rm -f /etc/bash_completion.d/IocManagerCompletion
rm -f /usr/local/bin/IocManager
rm -f /etc/sudoers.d/IocDock
rm -f /etc/profile.d/IocDockSetup.sh

gpasswd -d "$current_user" "$program_user"
gpasswd -d "$program_user" docker

set +x

# remove installation directory
if [ -d "$install_dir" ]; then
    echo ""
    echo "installation directory: $install_dir"
    read -rp "remove installation directory? [y/N]: " answer
    if [ "$answer" = "y" ] || [ "$answer" = "Y" ]; then
        rm -rf "$install_dir"
        echo "installation directory removed."
    else
        echo "installation directory kept."
    fi
fi

# finished.
echo "uninstallation finished, you may need to re-login or reboot the system."
#
