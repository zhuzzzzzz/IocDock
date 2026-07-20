#!/bin/bash

if [ "$(id -u)" -ne 0 ]; then
    echo "error: this script must be run as root." >&2
    exit 1
fi

export PYTHONDONTWRITEBYTECODE=1

# check prerequisites
if ! command -v python3 &>/dev/null; then
    echo "error: python3 is required but not found." >&2
    exit 1
fi

#
script_abs=$(readlink -f "$0")
script_dir=$(dirname "$script_abs")

current_user="${SUDO_USER:-$USER}"
program_user="iocdock"
expected_id=9981

find_excludes='\( -path /dev -o -path /proc -o -path /sys -o -path /run -o -path /var/lib/docker -o -path /var/lib/containerd \) -prune -o'

# check if expected_id is occupied by another user or group
id_conflict=0

# check if expected_id is occupied by another group
existing_group=$(getent group "$expected_id" 2>/dev/null | cut -d: -f1)
if [ -n "$existing_group" ] && [ "$existing_group" != "$program_user" ]; then
    echo "error: gid $expected_id is already used by group '$existing_group'." >&2
    id_conflict=1
fi

# check if expected_id is occupied by another user
existing_user=$(getent passwd "$expected_id" 2>/dev/null | cut -d: -f1)
if [ -n "$existing_user" ] && [ "$existing_user" != "$program_user" ]; then
    echo "error: uid $expected_id is already used by user '$existing_user'." >&2
    id_conflict=1
fi

if [ "$id_conflict" -ne 0 ]; then
    # build find filter based on which ids conflict
    if [ -n "$existing_user" ] && [ "$existing_user" != "$program_user" ] && \
       [ -n "$existing_group" ] && [ "$existing_group" != "$program_user" ]; then
        find_filter="\\( -uid $expected_id -o -gid $expected_id \\)"
        chown_cmd="chown <new_uid>:<new_gid>"
    elif [ -n "$existing_user" ] && [ "$existing_user" != "$program_user" ]; then
        find_filter="-uid $expected_id"
        chown_cmd="chown <new_uid>"
    else
        find_filter="-gid $expected_id"
        chown_cmd="chgrp <new_gid>"
    fi

    cat >&2 << EOF

error: id $expected_id is occupied by another user or group.
       please reassign the conflicting user/group and then re-run this script.

  step 1 - change the conflicting user/group to a new id:

$([ -n "$existing_group" ] && [ "$existing_group" != "$program_user" ] && echo "    sudo groupmod -g <new_gid> $existing_group")
$([ -n "$existing_user" ] && [ "$existing_user" != "$program_user" ] && echo "    sudo usermod -u <new_uid> -g <new_gid> $existing_user")

  step 2 - migrate file ownership for '$existing_user' / '$existing_group':

    after step 1, files previously owned by that user/group will show numeric ids
    instead of the username. review which files are affected:

    sudo find / $find_excludes $find_filter -ls

    WARNING: the command below will recursively modify file ownership across the
    filesystem. review the file list above carefully before executing, or use your
    own method to fix ownership for specific directories.

    sudo find / $find_excludes $find_filter -exec $chown_cmd {} +

EOF
    exit 1
fi

# check if iocdock group exists with wrong gid
id_mismatch=0
current_gid=""
current_uid=""

if getent group "$program_user" &>/dev/null; then
    current_gid=$(getent group "$program_user" | cut -d: -f3)
    if [ "$current_gid" != "$expected_id" ]; then
        echo "error: group '$program_user' exists with gid $current_gid, expected $expected_id." >&2
        id_mismatch=1
    fi
fi

# check if iocdock user exists with wrong uid
if id "$program_user" &>/dev/null; then
    current_uid=$(id -u "$program_user")
    if [ "$current_uid" != "$expected_id" ]; then
        echo "error: user '$program_user' exists with uid $current_uid, expected $expected_id." >&2
        id_mismatch=1
    fi
fi

if [ "$id_mismatch" -ne 0 ]; then
    # build find filter based on which ids need fixing
    if [ -n "$current_uid" ] && [ "$current_uid" != "$expected_id" ] && \
       [ -n "$current_gid" ] && [ "$current_gid" != "$expected_id" ]; then
        find_filter="\\( -uid $current_uid -o -gid $current_gid \\)"
        chown_cmd="chown $expected_id:$expected_id"
    elif [ -n "$current_uid" ] && [ "$current_uid" != "$expected_id" ]; then
        find_filter="-uid $current_uid"
        chown_cmd="chown $expected_id"
    else
        find_filter="-gid $current_gid"
        chown_cmd="chgrp $expected_id"
    fi

    cat >&2 << EOF

error: the '$program_user' user or group already exists with an unexpected id.
       please fix this manually and then re-run this script.

  option A - delete and recreate (simplest, if no important files are owned by '$program_user'):

    sudo userdel -r $program_user
    sudo groupdel $program_user

  option B - change the uid/gid and migrate file ownership:

    step 1 - change the uid/gid:

$([ -n "$current_gid" ] && [ "$current_gid" != "$expected_id" ] && echo "      sudo groupmod -g $expected_id $program_user")
$([ -n "$current_uid" ] && [ "$current_uid" != "$expected_id" ] && echo "      sudo usermod -u $expected_id -g $expected_id $program_user")

    step 2 - migrate file ownership:

      after step 1, files previously owned by '$program_user' will show numeric ids
      instead of the username. review which files are affected:

      sudo find / $find_excludes $find_filter -ls

      WARNING: the command below will recursively modify file ownership across the
      filesystem. review the file list above carefully before executing, or use your
      own method to fix ownership for specific directories.

      sudo find / $find_excludes $find_filter -exec $chown_cmd {} +

EOF
    exit 1
fi

# all checks passed, create user and group
groupadd -r docker &>/dev/null
groupadd -g "$expected_id" "$program_user" &>/dev/null
useradd -r -u "$expected_id" -g "$expected_id" -m -s /usr/sbin/nologin "$program_user" &>/dev/null
usermod -aG "$program_user" "$current_user"
usermod -aG docker "$program_user"

set -e

# install system-level dependencies
echo "installing system-level dependencies..."
if command -v apt &>/dev/null; then
    py_version=$(python3 -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")
    apt install -y ansible sshpass python3-pip "python${py_version}-venv" python3-passlib
elif command -v yum &>/dev/null; then
    yum install -y ansible sshpass python3-pip python3-passlib
elif command -v dnf &>/dev/null; then
    dnf install -y ansible sshpass python3-pip python3-passlib
else
    echo "warning: unsupported package manager, please install ansible sshpass python3-pip python3-passlib manually."
fi

# install project files
echo "installing..."
python3 -m compileall -q -f -j 0 "$script_dir"
home_path=$("$script_dir/IocManager.py" config HOME_PATH)
project_name=$("$script_dir/IocManager.py" config PROJECT_NAME)
mkdir -p "$home_path"
cp -r "$script_dir/." "$home_path/$project_name"
rm -rf "$home_path/$project_name/.git" "$home_path/$project_name/.gitea" "$home_path/$project_name/.github" "$home_path/$project_name/.gitignore" "$home_path/$project_name/.claude"
repository_path=$("$script_dir/IocManager.py" config REPOSITORY_PATH)
mkdir -p "$repository_path"
top_path="$home_path/$project_name"

# create virtual environment and install dependencies
echo "creating virtual environment and installing dependencies..."
python3 -m venv "$top_path/venv"
"$top_path/venv/bin/pip" install --upgrade pip
"$top_path/venv/bin/pip" install -r "$top_path/requirements.txt"

chown -R "$program_user:$program_user" "$top_path"
cd "$top_path"

# install shell command completion.
echo "installing shell command completion..."
cd imtools/command-completion
. install-command-completion.sh
cd "$top_path"

# add command shell wrapper
echo "installing command shell wrapper..."
cat > "/usr/local/bin/IocManager" << EOF
#!/bin/bash
exec sudo -u "$program_user" env PYTHONDONTWRITEBYTECODE=1 SSH_CONNECTION="\$SSH_CONNECTION"  "$home_path/$project_name/venv/bin/python3" "$home_path/$project_name/IocManager.py" "\$@"
EOF
chmod 755 "/usr/local/bin/IocManager"

# set sudoers rules
echo "setting sudoers.d rules..."
sudoers_file="/etc/sudoers.d/${project_name}"
cat > "$sudoers_file" << EOF
%${program_user} ALL=(${program_user}) NOPASSWD: ALL
EOF
chmod 440 "$sudoers_file"
visudo -cf "$sudoers_file"

# set environment variables.
echo setting environment variables...
file_path=/etc/profile.d/IocDockSetup.sh
mount_path=$("$script_dir/IocManager.py" config MOUNT_PATH)
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
ExecStart=${top_path}/venv/bin/python3 -u -m imutils.IocDockServer --server
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
if ! systemctl restart IocDockServer.service; then
    echo "warning: IocDockServer.service failed to start."
    echo "         You may need to start the service manually after setting up the cluster by running the following command:"
    echo ""
    echo "         sudo systemctl start IocDockServer.service"
    echo ""
fi
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
echo "installation finished, you may need to re-login the shell or reboot the system."
#





