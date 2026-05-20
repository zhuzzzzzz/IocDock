#!/bin/bash

export PYTHONDONTWRITEBYTECODE=1

#
current_user="${SUDO_USER:-$USER}"
program_user="iocdock"
script_abs=$(readlink -f "$0")
script_dir=$(dirname "$script_abs")

useradd -r -m -s /usr/sbin/nologin "$program_user" &>/dev/null
usermod -aG "$program_user" "$current_user"
usermod -aG docker "$program_user"

set -e

#
echo installing...
python3 -m compileall -q -f -j 0 "$script_dir"
home_path=$(./IocManager.py config HOME_PATH)
project_name=$(./IocManager.py config PROJECT_NAME)
mkdir -p "$home_path"
cp -r "$script_dir" "$home_path"
repository_path=$(./IocManager.py config REPOSITORY_PATH)
mkdir -p "$repository_path"
chown -R "$program_user:$program_user" "$home_path"
top_path="$home_path/$project_name"
cd "$top_path"

# install shell command completion.
echo installing shell command completion...
cd imtools/command-completion
. install-command-completion.sh
cd "$top_path"

# add command shell wrapper
echo add command shell wrapper...
cat > "/usr/local/bin/IocManager" << EOF
#!/bin/bash
exec sudo -u "$program_user" env PYTHONDONTWRITEBYTECODE=1 SSH_CONNECTION="\$SSH_CONNECTION"  /usr/bin/python3 "$home_path/$project_name/IocManager.py" "\$@"
EOF
chmod 755 "/usr/local/bin/IocManager"

# set sudoers rules
echo set sudoers.d rules...
sudoers_file="/etc/sudoers.d/${project_name}"
cat > "$sudoers_file" << EOF
%${program_user} ALL=(${program_user}) NOPASSWD: ALL
EOF
chmod 440 "$sudoers_file"
visudo -cf "$sudoers_file"

# set environment variables.
echo setting environment variables...
file_path=/etc/profile.d/IocDockSetup.sh
mount_path=$(./IocManager.py config MOUNT_PATH)
echo "export IOCDOCK_MANAGER_PATH=$top_path" > "$file_path"
echo "export IOCDOCK_REPOSITORY_PATH=$repository_path" >> "$file_path"
echo "export IOCDOCK_MOUNT_PATH=$mount_path" >> "$file_path"

# create systemd service file
echo "trying to stop and disable systemd service if exist..."
set +e
systemctl stop IocDockServer.service &>/dev/null
systemctl disable IocDockServer.service &>/dev/null
set -e
SERVICE_FILE=/etc/systemd/system/IocDockServer.service
echo "creating systemd service unit file..."
cat > "${SERVICE_FILE}" << EOF
[Unit]
Description=IocDockServer with a task server and a socket server
After=network.target docker.service
Requires=docker.service

[Service]
Type=simple
User=${program_user}
Group=${program_user}
WorkingDirectory=${top_path}
ExecStart=/usr/bin/python3 -u -m imutils.IocDockServer --server
Restart=on-failure
RestartSec=5s
StandardOutput=journal
StandardError=journal
SyslogIdentifier=IocDockServer
Environment="IOCDOCK_MANAGER_PATH=$top_path"
Environment="IOCDOCK_REPOSITORY_PATH=$repository_path"
Environment="IOCDOCK_MOUNT_PATH=$mount_path"

[Install]
WantedBy=multi-user.target
EOF
chmod 644 "${SERVICE_FILE}"
systemctl daemon-reload
systemctl enable IocDockServer.service
set +e
echo "trying to start systemd service..."
systemctl start IocDockServer.service
set -e

# copy settings.py and services.py if not exists in base directory.
if [ ! -f "$top_path/settings.py" ]; then
    echo "copying settings.py from imutils/ directory..."
    if cp "$top_path/imutils/settings.py" "$top_path/settings.py"; then
    chown "$program_user:$program_user" "$top_path/settings.py"
    chmod g+w "$top_path/settings.py"
    fi
fi
if [ ! -f "$top_path/services.py" ]; then
    echo "copying services.py from imutils/ directory..."
    if cp "$top_path/imutils/services.py" "$top_path/services.py"; then
    chown "$program_user:$program_user" "$top_path/services.py"
    chmod g+w "$top_path/services.py"
    fi
fi

# finished.
echo installation finished, you may need to re-login the shell or reboot the system.
#





