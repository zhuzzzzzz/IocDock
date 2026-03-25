import os
import yaml
import docker
import getpass
import imutils.IMConfig as IMConfig
from imutils.IMFunc import try_makedirs, file_remove
from imutils.IMSecret import PasswordFileManager, enter_password
from imutils.SocketClient import socket_client, client_check_connection


def gen_inventory_files(verbose=False):
    try_makedirs(IMConfig.ANSIBLE_INVENTORY_PATH, verbose=verbose)

    # for cluster
    if IMConfig.CLUSTER_MANAGER_NODES or IMConfig.CLUSTER_WORKER_NODES:
        yaml_data = {}
        # for swarm manager nodes
        if IMConfig.CLUSTER_MANAGER_NODES:
            group_name = "manager"
            group_dict = {}
            hosts_dict = {
                host: {"ansible_ssh_host": ip}
                for host, ip in IMConfig.CLUSTER_MANAGER_NODES.items()
            }
            group_dict["hosts"] = hosts_dict
            yaml_data[group_name] = group_dict
        # for swarm worker nodes
        if IMConfig.CLUSTER_WORKER_NODES:
            group_name = "worker"
            group_dict = {}
            hosts_dict = {
                host: {"ansible_ssh_host": ip}
                for host, ip in IMConfig.CLUSTER_WORKER_NODES.items()
            }
            group_dict["hosts"] = hosts_dict
            yaml_data[group_name] = group_dict
        with open(IMConfig.CLUSTER_INVENTORY_FILE_PATH, "w", encoding="utf-8") as f:
            yaml.dump(yaml_data, f, allow_unicode=True, sort_keys=False)
    else:
        if os.path.isfile(IMConfig.CLUSTER_INVENTORY_FILE_PATH):
            file_remove(IMConfig.CLUSTER_INVENTORY_FILE_PATH, verbose=verbose)

    # for other nodes
    if IMConfig.DEFAULT_NODES:
        yaml_data = {}
        group_name = "ungrouped"
        group_dict = {}
        hosts_dict = {
            host: {"ansible_ssh_host": ip}
            for host, ip in IMConfig.DEFAULT_NODES.items()
        }
        group_dict["hosts"] = hosts_dict
        yaml_data[group_name] = group_dict
        with open(IMConfig.DEFAULT_INVENTORY_FILE_PATH, "w", encoding="utf-8") as f:
            yaml.dump(yaml_data, f, allow_unicode=True, sort_keys=False)
    else:
        if os.path.isfile(IMConfig.DEFAULT_INVENTORY_FILE_PATH):
            file_remove(IMConfig.DEFAULT_INVENTORY_FILE_PATH, verbose=verbose)


def create_remote_user():
    # Prompt for credentials
    print("Enter remote user password(Leave blank to use ANSIBLE_CREATE_PASSWORD).")
    password = enter_password()
    if not password:
        if IMConfig.ANSIBLE_CREATE_PASSWORD:
            password = IMConfig.ANSIBLE_CREATE_PASSWORD
        else:
            print("Failed. Password not provided and ANSIBLE_CREATE_PASSWORD not set.")
            return
    print("Starting to create remote user...")
    os.system(
        f"cd {IMConfig.ANSIBLE_PATH}; "
        f"ansible-playbook setup-cluster.yaml -i inventory/ -kK "
        f'-e "skip_set_up_ssh_connection=true skip_set_up_basic_environment=true skip_set_up_swarm=true '
        f'for_user={IMConfig.ANSIBLE_FOR_USER} create_password={password} ansible_ssh_user={IMConfig.ANSIBLE_SSH_USER}"'
    )


def set_up_ssh_connection():
    print("Starting to set up ssh connection...")
    os.system(
        f"cd {IMConfig.ANSIBLE_PATH}; "
        f"ansible-playbook setup-cluster.yaml -i inventory/ -kK "
        f'-e "skip_create_remote_user=true skip_set_up_basic_environment=true skip_set_up_swarm=true '
        f'for_user={IMConfig.ANSIBLE_FOR_USER} ansible_ssh_user={IMConfig.ANSIBLE_SSH_USER}"'
    )


def set_up_basic_environment():
    print("Starting to set up basic environment...")
    os.system(
        f"cd {IMConfig.ANSIBLE_PATH}; "
        f"ansible-playbook setup-cluster.yaml -i inventory/ -kK "
        f'-e "skip_create_remote_user=true skip_set_up_ssh_connection=true skip_set_up_swarm=true '
        f'for_user={IMConfig.ANSIBLE_FOR_USER} ansible_ssh_user={IMConfig.ANSIBLE_SSH_USER}"'
    )


def set_up_cluster():
    # Prompt for credentials
    print("Enter remote user password(Leave blank to use ANSIBLE_CREATE_PASSWORD).")
    password = enter_password()
    if not password:
        if IMConfig.ANSIBLE_CREATE_PASSWORD:
            password = IMConfig.ANSIBLE_CREATE_PASSWORD
        else:
            print("Failed. Password not provided and ANSIBLE_CREATE_PASSWORD not set.")
            return
    print("Starting to set up cluster...")
    os.system(
        f"cd {IMConfig.ANSIBLE_PATH}; "
        f"ansible-playbook setup-cluster.yaml -i inventory/ -kK "
        f'-e "for_user={IMConfig.ANSIBLE_FOR_USER} create_password={password} ansible_ssh_user={IMConfig.ANSIBLE_SSH_USER}"'
    )


def ping():
    os.system(
        f"ansible all -m ping -i {IMConfig.ANSIBLE_INVENTORY_PATH} -u {IMConfig.ANSIBLE_FOR_USER}"
    )


def ansible_touch_dir(dir_name, host_pattern):
    base_path = os.path.normpath(os.path.join(IMConfig.MANAGER_PATH, ".."))
    dir_path = os.path.join(base_path, dir_name)
    os.system(
        f'ansible {host_pattern} -m file -a "dest={dir_path} mode=777 state=directory" '
        f"-i {IMConfig.CLUSTER_INVENTORY_FILE_PATH} -u {IMConfig.ANSIBLE_FOR_USER}"
    )


def ansible_create_file(file_path, contents, host_pattern):
    os.system(
        f"ansible {host_pattern} -m copy -a \"content='{contents}' dest={file_path}\" "
        f"-i {IMConfig.CLUSTER_INVENTORY_FILE_PATH} -u {IMConfig.ANSIBLE_FOR_USER}"
    )


def ansible_nfs_mount(dir_name, host_pattern, become_password_file):
    base_path = os.path.normpath(os.path.join(IMConfig.MANAGER_PATH, ".."))
    dir_path = os.path.join(base_path, dir_name)
    if dir_name == "registry-data":
        os.system(
            f'ansible {host_pattern} -b -m mount -a "path={dir_path} src={IMConfig.REGISTRY_NFS_MOUNT_SRC} '
            f'fstype=nfs opts=rw,_netdev state=mounted" '
            f"-i {IMConfig.CLUSTER_INVENTORY_FILE_PATH} -u {IMConfig.ANSIBLE_FOR_USER} --become-password-file={become_password_file}"
        )
    elif dir_name == "IocDock-data":
        os.system(
            f'ansible {host_pattern} -b -m mount -a "path={dir_path} src={IMConfig.MOUNT_DIR_NFS_MOUNT_SRC} '
            f'fstype=nfs opts=rw,_netdev state=mounted" '
            f"-i {IMConfig.CLUSTER_INVENTORY_FILE_PATH} -u {IMConfig.ANSIBLE_FOR_USER} --become-password-file={become_password_file}"
        )
    else:
        print(
            f"ansible_nfs_mount({dir_name}, {host_pattern}): Failed, unsupported directory: {dir_name}."
        )


def docker_registry_login():
    # Prompt for credentials
    print("Please enter Registry Login credentials:")
    username = input(f"Username: ").strip()
    password = getpass.getpass("Password: ")
    os.system(
        f"ansible all -m community.docker.docker_login -a "
        f'"registry_url=https://{IMConfig.REGISTRY_COMMON_NAME} username={username} password={password} reauthorize=true" '
        f"-i {IMConfig.CLUSTER_INVENTORY_FILE_PATH} -u {IMConfig.ANSIBLE_FOR_USER}"
    )


def set_up_file_and_dir_for_every_host(become_password_file):
    docker_client = docker.from_env()
    node_info = {}
    nodes = docker_client.nodes.list()
    for node in nodes:
        node_info[node.attrs["Description"]["Hostname"]] = {
            "ip": node.attrs["Status"]["Addr"],
        }
    for node_name, node_info in node_info.items():
        ansible_create_file(
            IMConfig.NODE_IP_FILE, f'NODE_IP={node_info["ip"]}', node_name
        )
        ansible_touch_dir("alloy-data", node_name)
        ansible_touch_dir("IocDock-data", node_name)
        ansible_nfs_mount("IocDock-data", node_name, become_password_file)


def set_up_dir_according_to_labels(become_password_file):
    node_info = socket_client("node info", receive_type="json")
    for node_name, node_info in node_info.items():
        if node_info.get("labels", None):
            for key, value in node_info.get("labels").items():
                if key == "alertmanager" and value == "true":
                    ansible_touch_dir("alertManager-data", node_name)
                elif key == "grafana" and value == "true":
                    ansible_touch_dir("grafana-data", node_name)
                elif key == "loki" and value == "true":
                    ansible_touch_dir("loki-data", node_name)
                elif key == "prometheus" and value == "true":
                    ansible_touch_dir("prometheus-data", node_name)
                elif key == "registry" and value == "true":
                    ansible_touch_dir("registry-data", node_name)
                    ansible_nfs_mount("registry-data", node_name, become_password_file)


def set_up_file_and_dir():
    with PasswordFileManager() as pfm:
        set_up_file_and_dir_for_every_host(pfm.password_file)
        set_up_dir_according_to_labels(pfm.password_file)


if __name__ == "__main__":
    pass
    # gen_inventory_files(verbose=True)
    # ping()
    # docker_registry_login()
    ansible_create_file("~/.NodeInfo", "a=b", "manager")
    if client_check_connection():
        print(socket_client("ioc info", receive_type="json"))
    print(socket_client("service info", receive_type="json"))
    print(socket_client("node info", receive_type="json"))
    # set_up_file_and_dir_for_every_host()
    # set_up_dir_according_to_labels()
