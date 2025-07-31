import os
import yaml
import imutils.IMConfig as IMConfig
from imutils.IMFunc import try_makedirs, file_remove


def set_up_ssh_connection(verbose=False):
    home_dir = os.path.expanduser("~")
    key_path = os.path.join(home_dir, '.ssh', 'id_rsa')
    pubkey_path = os.path.join(home_dir, '.ssh', 'id_rsa.pub')
    if os.path.isfile(key_path) and os.path.isfile(pubkey_path):
        if verbose:
            print('Key pair exists.')
    else:
        os.system(f'ssh-keygen -t rsa -b 4096 -f ~/.ssh/id_rsa -N ""')
    #
    file_path = os.path.join(IMConfig.ANSIBLE_PATH, 'set-up-ssh-connection.yaml')
    os.system(f'sed -i -r "s/for_user: .*/for_user: {IMConfig.REMOTE_USER_NAME}/" {file_path}')
    os.system(f'sed -i -r "s/remote_user: .*/remote_user: {IMConfig.REMOTE_USER_NAME}/" {file_path}')
    os.system(f'cd {IMConfig.ANSIBLE_PATH}; ansible-playbook set-up-ssh-connection.yaml -i inventory/ -k')


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
            vars_dict = {'ansible_ssh_user': IMConfig.REMOTE_USER_NAME}
            group_dict['hosts'] = hosts_dict
            group_dict['vars'] = vars_dict
            yaml_data[group_name] = group_dict
        # for swarm worker nodes
        if IMConfig.CLUSTER_WORKER_NODES:
            group_name = 'worker'
            group_dict = {}
            hosts_dict = {host: {'ansible_ssh_host': ip} for host, ip in IMConfig.CLUSTER_WORKER_NODES.items()}
            vars_dict = {'ansible_ssh_user': IMConfig.REMOTE_USER_NAME}
            group_dict['hosts'] = hosts_dict
            group_dict['vars'] = vars_dict
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
        vars_dict = {'ansible_ssh_user': IMConfig.REMOTE_USER_NAME}
        group_dict['hosts'] = hosts_dict
        group_dict['vars'] = vars_dict
        yaml_data[group_name] = group_dict
        with open(IMConfig.DEFAULT_INVENTORY_FILE_PATH, "w", encoding="utf-8") as f:
            yaml.dump(yaml_data, f, allow_unicode=True, sort_keys=False)
    else:
        if os.path.isfile(IMConfig.DEFAULT_INVENTORY_FILE_PATH):
            file_remove(IMConfig.DEFAULT_INVENTORY_FILE_PATH, verbose=verbose)


if __name__ == '__main__':
    gen_inventory_files(verbose=True)
    set_up_ssh_connection(verbose=True)
