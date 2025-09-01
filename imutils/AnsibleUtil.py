import os
import yaml
import imutils.IMConfig as IMConfig
from imutils.IMFunc import try_makedirs, file_remove


def gen_inventory_files(verbose=False):
    try_makedirs(IMConfig.ANSIBLE_INVENTORY_PATH, verbose=verbose)

    # for cluster
    if IMConfig.CLUSTER_MANAGER_NODES or IMConfig.CLUSTER_WORKER_NODES:
        yaml_data = {}
        # for swarm manager nodes
        if IMConfig.CLUSTER_MANAGER_NODES:
            group_name = 'manager'
            group_dict = {}
            hosts_dict = {host: {'ansible_ssh_host': ip} for host, ip in IMConfig.CLUSTER_MANAGER_NODES.items()}
            group_dict['hosts'] = hosts_dict
            yaml_data[group_name] = group_dict
        # for swarm worker nodes
        if IMConfig.CLUSTER_WORKER_NODES:
            group_name = 'worker'
            group_dict = {}
            hosts_dict = {host: {'ansible_ssh_host': ip} for host, ip in IMConfig.CLUSTER_WORKER_NODES.items()}
            group_dict['hosts'] = hosts_dict
            yaml_data[group_name] = group_dict
        with open(IMConfig.CLUSTER_INVENTORY_FILE_PATH, "w", encoding="utf-8") as f:
            yaml.dump(yaml_data, f, allow_unicode=True, sort_keys=False)
    else:
        if os.path.isfile(IMConfig.CLUSTER_INVENTORY_FILE_PATH):
            file_remove(IMConfig.CLUSTER_INVENTORY_FILE_PATH, verbose=verbose)

    # for other nodes
    if IMConfig.DEFAULT_NODES:
        yaml_data = {}
        group_name = 'ungrouped'
        group_dict = {}
        hosts_dict = {host: {'ansible_ssh_host': ip} for host, ip in IMConfig.DEFAULT_NODES.items()}
        group_dict['hosts'] = hosts_dict
        yaml_data[group_name] = group_dict
        with open(IMConfig.DEFAULT_INVENTORY_FILE_PATH, "w", encoding="utf-8") as f:
            yaml.dump(yaml_data, f, allow_unicode=True, sort_keys=False)
    else:
        if os.path.isfile(IMConfig.DEFAULT_INVENTORY_FILE_PATH):
            file_remove(IMConfig.DEFAULT_INVENTORY_FILE_PATH, verbose=verbose)


def ping():
    os.system(f'ansible all -m ping -i {IMConfig.ANSIBLE_INVENTORY_PATH} -u {IMConfig.FOR_USER}')


def ansible_touch_dir(dir_name, host_pattern):
    base_path = os.path.normpath(os.path.join(IMConfig.MANAGER_PATH, '..'))
    dir_path = os.path.join(base_path, dir_name)
    os.system(f'ansible {host_pattern} -m file -a "dest={base_path} mode=775 state=directory" '
              f'-i {IMConfig.CLUSTER_INVENTORY_FILE_PATH} -u {IMConfig.FOR_USER}')
    os.system(f'ansible {host_pattern} -m file -a "dest={dir_path} mode=777 state=directory" '
              f'-i {IMConfig.CLUSTER_INVENTORY_FILE_PATH} -u {IMConfig.FOR_USER}')


def ansible_create_file(file_path, contents, host_pattern):
    os.system(f'ansible {host_pattern} -m copy -a "content=\'{contents}\' dest={file_path}" '
              f'-i {IMConfig.CLUSTER_INVENTORY_FILE_PATH} -u {IMConfig.FOR_USER}')


def docker_registry_login():
    os.system(f'ansible all -m community.docker.docker_login -a '
              f'"registry_url=https://{IMConfig.REGISTRY_COMMON_NAME} username=admin password=admin reauthorize=true" '
              f'-i {IMConfig.CLUSTER_INVENTORY_FILE_PATH} -u {IMConfig.FOR_USER}')


if __name__ == '__main__':
    pass
    # gen_inventory_files(verbose=True)
    # ping()
    # docker_registry_login()
    ansible_create_file("~/.NodeInfo", "a=b", "manager")
