#!/bin/bash

#
current_user="${SUDO_USER:-$USER}"
script_abs=$(readlink -f "$0")
script_dir=$(dirname $script_abs)


# install shell command completion.
echo installing shell command completion...
cd imtools/command-completion
. install-command-completion.sh
cd $script_dir


# set environment variables.
echo setting environment variables...
export MANAGER_PATH=$script_dir
repository_path=$(./IocManager.py config REPOSITORY_PATH)
if [ $? -ne 0 ]; then
    echo "Failed. Failed to get \"REPOSITORY_PATH\" in configuration file." >&2
    exit 1
fi
mkdir $repository_path > /dev/null 2>&1
if [ $? -eq 0 ]; then
    chown $current_user:$current_user $repository_path
    chmod g+w $repository_path
fi
mount_path=$(./IocManager.py config MOUNT_PATH)
if [ $? -ne 0 ]; then
    echo "Failed. Failed to get \"MOUNT_PATH\" in configuration file." >&2
    exit 1
fi
file_path=/etc/profile.d/IocDockSetup.sh
echo "export MANAGER_PATH=$script_dir" > $file_path
echo "export REPOSITORY_PATH=$repository_path" >> $file_path
echo "export MOUNT_PATH=$mount_path" >> $file_path

# set log file permission.
echo setting log file permission...
file_path=$(./IocManager.py config OPERATION_LOG_FILE_PATH)
if [ $? -eq 0 ]; then
    chown $current_user:$current_user $file_path
    chmod g+w $file_path
fi

# add command soft link.
echo making file soft link for command...
ln -sf $script_dir/IocManager.py /usr/bin/IocManager

# create systemd service file
echo "trying to stop and disable systemd service if exist..."
systemctl stop IocDockServer.service
systemctl disable IocDockServer.service
SERVICE_FILE=/etc/systemd/system/IocDockServer.service
echo "creating systemd service unit file..."
cat > "${SERVICE_FILE}" << EOF
[Unit]
Description=IocDockServer with and socket server
After=network.target
Requires=docker.service

[Service]
Type=simple
User=${current_user}
Group=${current_user}
WorkingDirectory=${script_dir}
ExecStart=/usr/bin/python3 -u IocDockServer.py --server
Restart=on-failure
RestartSec=5s
StandardOutput=journal
StandardError=journal
SyslogIdentifier=IocDockServer
Environment="MANAGER_PATH=$script_dir"
Environment="REPOSITORY_PATH=$repository_path"
Environment="MOUNT_PATH=$mount_path"

[Install]
WantedBy=multi-user.target
EOF
chmod 644 "${SERVICE_FILE}"
systemctl daemon-reload
systemctl enable IocDockServer.service
systemctl start IocDockServer.service

# finished.
echo installation finished, you may need to re-login or reboot the system.
#





