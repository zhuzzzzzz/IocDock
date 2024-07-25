#!/bin/bash

script_abs=$(readlink -f "$0")
script_dir=$(dirname $script_abs)

repository_path=$script_dir/../ioc-repository/
mount_path=$script_dir/../../ioc-for-docker/

temp_name="IocManagerCompletion"

cat ./command-completion.sh > ./$temp_name
echo "export REPOSITORY_PATH=$(readlink -f "$repository_path")" >> ./$temp_name # $REPOSITORY_PATH for finding IOC projects.
echo "export MOUNT_PATH=$(readlink -f "$mount_path")" >> ./$temp_name # $MOUNT_PATH for finding hosts.

sudo cp ./$temp_name /etc/bash_completion.d/

. ./$temp_name


