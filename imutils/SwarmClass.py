import datetime
import os
from ruamel.yaml import YAML
import subprocess
import docker
from tabulate import tabulate

from imutils.IMConfig import *
from imutils.IMFunc import relative_and_absolute_path_to_abs, try_makedirs, file_copy, dir_copy
from imutils.ServiceDefinition import GlobalServicesList, LocalServicesList, CustomServicesList
from imutils.AnsibleClient import ansible_socket_client, client_check_connection


class SwarmManager:
    def __init__(self, verbose=False, **kwargs):
        try_makedirs(REPOSITORY_PATH, verbose=verbose)
        self.services = {item: SwarmService(name=item, service_type='ioc') for item in
                         os.listdir(REPOSITORY_PATH) if os.path.isdir(os.path.join(REPOSITORY_PATH, item))}
        for ss in GlobalServicesList:
            name = ss[0]
            if name in self.services.keys():
                print(f'SwarmManager: Warning! Service "{name}" defined in GlobalServicesList '
                      f'has the same name with existing services, skipped.')
                continue
            self.services[name] = SwarmService(name=name, service_type='global')
        for ss in LocalServicesList:
            name = ss[0]
            if name in self.services.keys():
                print(f'SwarmManager: Warning! Service "{name}" defined in LocalServicesList '
                      f'has the same name with existing services, skipped.')
                continue
            self.services[name] = SwarmService(name=name, service_type='local')
        for ss in CustomServicesList:
            name = ss[0]
            compose_file = ss[1]
            if name in self.services.keys():
                print(f'SwarmManager: Warning! Service "{name}" defined in CustomServicesList '
                      f'has the same name with existing services, skipped.')
                continue
            self.services[name] = SwarmService(name=name, service_type='custom', compose_file=compose_file)
        self.client = docker.from_env()
        self.running_services = self.get_services_from_docker()

        if verbose:
            print('Managed services:')
            print(self.services)

    def get_services_from_docker(self):
        services = self.client.services.list(filters={'label': f'com.docker.stack.namespace={PREFIX_STACK_NAME}'})
        return [item for item in services]

    @staticmethod
    def list_managed_services():
        res = ''
        try_makedirs(REPOSITORY_PATH, verbose=False)
        services_list = [item for item in os.listdir(REPOSITORY_PATH) if
                         os.path.isdir(os.path.join(REPOSITORY_PATH, item))]
        for ss in GlobalServicesList + LocalServicesList + CustomServicesList:
            if ss[0] in services_list:
                continue
            else:
                services_list.append(ss[0])
        for item in services_list:
            res += f'{item} '
        return res.rstrip()

    def list_running_services(self):
        temp_list = [item.name for item in self.running_services]
        temp_list.sort()
        for item in temp_list:
            print(f'{item}', end=' ')
        else:
            print()

    def show_info(self):
        if not client_check_connection():
            print(f'Failed to connect to IocDockServer.')
        socket_result_service = ansible_socket_client("service info", verbose=False)
        raw_print = [["Name", "ServiceName", "Type", "Replicas", "Status"], ]
        custom_print = []
        local_print = []
        global_print = []
        ioc_print = []
        for item in self.services.values():
            socket_info_service = socket_result_service.get(item.name, None)
            t_l = [item.name, item.service_name, item.service_type,
                   socket_info_service.get('replicas') if socket_info_service else item.replicas,
                   socket_info_service.get('status') if socket_info_service else item.current_state]
            if item.service_type == 'ioc':
                ioc_print.append(t_l)
            if item.service_type == 'global':
                global_print.append(t_l)
            if item.service_type == 'local':
                local_print.append(t_l)
            if item.service_type == 'custom':
                custom_print.append(t_l)
        ioc_print.sort(key=lambda x: x[0])
        global_print.sort(key=lambda x: x[0])
        local_print.sort(key=lambda x: x[0])
        custom_print.sort(key=lambda x: x[0])
        raw_print.extend(local_print)
        raw_print.extend(global_print)
        raw_print.extend(custom_print)
        raw_print.extend(ioc_print)
        print(tabulate(raw_print, headers="firstrow", tablefmt='plain'))
        print('')

    def deploy_global_services(self):
        for item in self.services.values():
            if item.service_type == 'global':
                if item.is_available:
                    if item.is_deployed:
                        print(f'SwarmManager: Skipped deploying "{item.service_name}", as it\'s been deployed.')
                        continue
                    else:
                        print(f'SwarmManager: Start to Deploy "{item.service_name}".')
                        print(f'=================================================================')
                        item.deploy()
                else:
                    print(f'SwarmManager: Failed to deploy "{item.service_name}", as it\'s not available.')

    def deploy_all_iocs(self):
        for item in self.services.values():
            if item.service_type == 'ioc':
                if item.is_available:
                    if item.is_deployed:
                        print(f'SwarmManager: Skipped deploying "{item.service_name}", as it\'s been deployed.')
                        continue
                    else:
                        print(f'SwarmManager: Start to Deploy "{item.service_name}".')
                        print(f'=================================================================')
                        item.deploy()
                else:
                    print(f'SwarmManager: Failed to deploy "{item.service_name}", as it\'s not available.')

    def remove_global_services(self):
        while True:
            ans = input(f'SwarmManager: Remove all deployed global services?!![y|n]:')
            if ans.lower() == 'y' or ans.lower() == 'yes':
                print(f'SwarmManager: All deployed global services will be removed.')
                break
            elif ans.lower() == 'n' or ans.lower() == 'no':
                return
            else:
                print(f'SwarmManager: Invalid input, please try again.')
        for item in self.services.values():
            if item.service_type == 'global':
                if item.is_available:
                    if item.is_deployed:
                        item.remove()

    def remove_all_iocs(self):
        while True:
            ans = input(f'SwarmManager: Remove all deployed IOC projects?!![y|n]:')
            if ans.lower() == 'y' or ans.lower() == 'yes':
                print(f'SwarmManager: All deployed IOC projects will be removed.')
                break
            elif ans.lower() == 'n' or ans.lower() == 'no':
                return
            else:
                print(f'SwarmManager: Invalid input, please try again.')
        for item in self.services.values():
            if item.service_type == 'ioc':
                if item.is_available:
                    if item.is_deployed:
                        item.remove()

    def remove_all_services(self):
        while True:
            ans = input(f'SwarmManager: Remove all deployed services in Swarm?!![y|n]:')
            if ans.lower() == 'y' or ans.lower() == 'yes':
                print(f'SwarmManager: All deployed services will be removed.')
                break
            elif ans.lower() == 'n' or ans.lower() == 'no':
                return
            else:
                print(f'SwarmManager: Invalid input, please try again.')
        for item in self.services.values():
            if item.is_deployed:
                item.remove()

    def update_deployed_services(self):
        print(f'Update all deployed services, this will cause all ioc services to be restarted.')
        ans = input(f'Confirm to execute the above operation[y|n]?')
        if ans.lower() == 'y' or ans.lower() == 'yes':
            for item in self.services.values():
                if item.service_type == 'ioc':
                    item.update()
        else:
            print(f'Operation exit.')
            return

    @staticmethod
    def gen_template_services(verbose):
        print(f'SwarmManager: Create deployment file for template services.')
        # hello
        template_path = os.path.join(COMPOSE_TEMPLATE_PATH, 'hello.yaml')
        os.system(f'sed -i -r '
                  f'"s/image: .*/image: registry.{PREFIX_STACK_NAME}\\/busybox:1.37.0/" '
                  f'{template_path}')

    @staticmethod
    def gen_global_services(verbose):
        #
        top_path = os.path.join(MOUNT_PATH, 'swarm')
        # make directory for iocLogServer
        try_makedirs(os.path.join(top_path, LOG_FILE_DIR))
        #
        try_makedirs(os.path.join(top_path, GLOBAL_SERVICE_FILE_DIR))
        try_makedirs(os.path.join(top_path, GLOBAL_SERVICE_FILE_DIR, 'config'))
        #

        excluded_item = []

        # setup alloy
        temp_service = SwarmService('alloy', service_type='global')
        if temp_service.is_deployed:  # check whether the directory being mounted.
            excluded_item.append('alloy')
        else:
            if 'config.alloy' in os.listdir(GLOBAL_SERVICES_CONFIG_FILE_PATH):
                #
                template_path = os.path.join(GLOBAL_SERVICES_CONFIG_FILE_PATH, 'config.alloy')
                #
                os.system(f'sed -i -r '
                          f'"s/url = .*/url = \\"http:\\/\\/{PREFIX_STACK_NAME}_srv-loki:3100\\/loki\\/api\\/v1\\/push\\"/" '
                          f'{template_path}')
                #
                cmd = (f'sed -i -r '
                       f'"s/regex = \\".*\\|test\\"/regex = \\"{PREFIX_STACK_NAME}\\|test\\"/" '
                       f'{template_path}')
                # print(cmd)
                os.system(cmd)
                file_path = os.path.join(top_path, GLOBAL_SERVICE_FILE_DIR, 'config', 'config.alloy')
                file_copy(template_path, file_path, mode='r', verbose=verbose)
                #
                template_path = os.path.join(GLOBAL_SERVICES_CONFIG_FILE_PATH, 'run.alloy')
                file_path = os.path.join(top_path, GLOBAL_SERVICE_FILE_DIR, 'config', 'run.alloy')
                file_copy(template_path, file_path, mode='rx', verbose=verbose)

        for item in GlobalServicesList:
            name = item[0]
            image = item[1] if len(item) > 1 else None
            temp_service = SwarmService(name, service_type='global')
            if f'{name}.yaml' in os.listdir(GLOBAL_SERVICES_PATH):
                if name in excluded_item or temp_service.is_deployed:
                    print(f'SwarmManager: Failed to create deployment file for "{name}" as it is running.')
                else:
                    template_path = os.path.join(GLOBAL_SERVICES_PATH, f'{name}.yaml')
                    # set image with prefix if provided
                    if image:
                        os.system(
                            f'sed -i -r 'f'"s/image: .*/image: {REGISTRY_COMMON_NAME}\\/{image}/" {template_path}')
                    # copy yaml file
                    file_path = os.path.join(top_path, GLOBAL_SERVICE_FILE_DIR, f'{name}.yaml')
                    file_copy(template_path, file_path, mode='r', verbose=verbose)
                    print(f'SwarmManager: Create deployment file for "{name}".')
            else:
                print(
                    f'SwarmManager: Failed to create deployment file for "{name}" as its template file dose not exist.')

    @staticmethod
    def gen_local_services(verbose):
        #
        top_path = os.path.join(MOUNT_PATH, 'swarm')
        excluded_item = []

        # setup registry
        temp_service = SwarmService('registry', service_type='local')
        if temp_service.is_deployed:  # check whether the directory being mounted.
            excluded_item.append('registry')
        else:
            # write shell variable file
            file_path = os.path.join(SERVICES_PATH, 'registry', 'scripts', REGISTRY_SHELL_VAR_FILE)
            with open(file_path, "w") as f:
                f.write(f'REGISTRY_COMMON_NAME={REGISTRY_COMMON_NAME}\n')
                f.write(f'REGISTRY_CERT_DOCKER_DIR={REGISTRY_CERT_DOCKER_DIR}\n')

        # setup prometheus
        temp_service = SwarmService('prometheus', service_type='local')
        if temp_service.is_deployed:  # check whether the directory being mounted.
            excluded_item.append('prometheus')
        else:
            # write shell variable file
            file_path = os.path.join(SERVICES_PATH, 'prometheus', 'config', 'rules-for-cAdvisor.yaml')
            os.system(f'sed -i -r '
                      f'"s/stack=~\'[^\']*\'/stack=~\'{PREFIX_STACK_NAME}\\|test\'/g" '
                      f'{file_path}')

        # setup alertManager
        temp_service = SwarmService('alertManager', service_type='local')
        if temp_service.is_deployed:
            excluded_item.append('alertManager')
        else:
            # write shell variable file
            file_path = os.path.join(SERVICES_PATH, 'alertManager', 'scripts', ALERT_MANAGER_SHELL_VAR_FILE)
            with open(file_path, "w") as f:
                f.write(f'ALERT_MANAGER_MASTER_IP={ALERT_MANAGER_MASTER_IP}\n')
                f.write(f'ALERT_MANAGER_MASTER_IP_PORT={ALERT_MANAGER_MASTER_IP}:{ALERT_MANAGER_MASTER_GOSSIP_PORT}\n')
            # set smtp account
            file_path = os.path.join(SERVICES_PATH, 'alertManager', 'config', 'alertManager-config.yaml')
            os.system(f'sed -i -r "s/smtp_from: .*/smtp_from: {ALERT_MANAGER_SMTP_EMAIL_SEND_ADDRESS}/" {file_path}')
            os.system(f'sed -i -r "s/smtp_smarthost: .*/smtp_smarthost: {ALERT_MANAGER_SMTP_SMART_HOST}/" {file_path}')
            os.system(f'sed -i -r '
                      f'"s/smtp_auth_username: .*/smtp_auth_username: {ALERT_MANAGER_SMTP_AUTH_USERNAME}/" {file_path}')
            yaml = YAML()
            yaml.preserve_quotes = True
            if ALERT_MANAGER_RECEIVE_EMAIL_LIST:
                with open(file_path, "r", encoding="utf-8") as f:
                    config_data = yaml.load(f)
                receiver_list = [
                    {
                        'name': 'default-mail',
                        'email_configs': [{'to': ALERT_MANAGER_RECEIVE_EMAIL_LIST[0]}, ],
                    },
                    {
                        'name': 'test-mail',
                        'email_configs': [{'to': email_item} for email_item in ALERT_MANAGER_RECEIVE_EMAIL_LIST],
                    },
                    {
                        'name': 'test-mail-send-resolve',
                        'email_configs': [
                            {'to': email_item,
                             'send_resolved': True} for email_item in ALERT_MANAGER_RECEIVE_EMAIL_LIST
                        ],
                    },
                ]
                config_data['receivers'] = receiver_list
                with open(file_path, "w", encoding="utf-8") as f:
                    yaml.dump(config_data, f)
            file_path = os.path.join(SERVICES_PATH, 'alertManager', 'config', 'smtp_password')
            if not os.path.isfile(file_path):
                if ALERT_MANAGER_SMTP_AUTH_PASSWORD:
                    with open(file_path, "w") as f:
                        f.write(ALERT_MANAGER_SMTP_AUTH_PASSWORD)
                else:
                    print(f'SwarmManager: Warning! For alertManager: Password file "smtp_password" not exist '
                          f'and "ALERT_MANAGER_SMTP_AUTH_PASSWORD" not set in IMConfig.py.')

        # setup loki
        temp_service = SwarmService('loki', service_type='local')
        if temp_service.is_deployed:
            excluded_item.append('loki')
        else:
            file_path = os.path.join(SERVICES_PATH, 'loki', 'config', 'loki-config.yaml')
            os.system(f'sed -i -r '
                      f'"s/url: .*_srv-prometheus/url: http:\\/\\/{PREFIX_STACK_NAME}_srv-prometheus/" '
                      f'{file_path}')
            os.system(f'sed -i -r '
                      f'"s/alertmanager_url: .*/alertmanager_url: http:\\/\\/{ALERT_MANAGER_MASTER_IP}:9093/" '
                      f'{file_path}')

        # setup grafana
        temp_service = SwarmService('grafana', service_type='local')
        if temp_service.is_deployed:
            excluded_item.append('grafana')
        else:
            src_path = os.path.join(SERVICES_PATH, 'grafana', 'datasources')
            file_path = os.path.join(src_path, 'loki.yaml')
            os.system(f'sed -i -r "s/url: .*/url: http:\\/\\/{PREFIX_STACK_NAME}_srv-loki:3100/" {file_path}')
            file_path = os.path.join(src_path, 'prometheus.yaml')
            os.system(f'sed -i -r "s/url: .*/url: http:\\/\\/{PREFIX_STACK_NAME}_srv-prometheus:9090/" {file_path}')

        # copy directory of all local services defined.
        for item in LocalServicesList:
            name = item[0]
            image = item[1] if len(item) > 1 else None
            temp_service = SwarmService(name, service_type='local')
            src_path = os.path.join(SERVICES_PATH, name)
            if os.path.isdir(src_path):
                if name in excluded_item or temp_service.is_deployed:
                    print(f'SwarmManager: Failed to create deployment directory for "{name}" as it is running.')
                else:
                    template_path = os.path.join(src_path, f'{name}.yaml')
                    # set image with prefix if provided
                    if image:
                        os.system(
                            f'sed -i -r 'f'"s/image: .*/image: {REGISTRY_COMMON_NAME}\\/{image}/" {template_path}')
                    dest_path = os.path.join(top_path, name)
                    dir_copy(src_path, dest_path, verbose=verbose)
                    print(f'SwarmManager: Create deployment directory for "{name}".')
            else:
                print(f'SwarmManager: Failed to create deployment directory for "{name}" '
                      f'as there is no valid dir exists in repository.')

    @staticmethod
    def get_deployed_swarm_services():
        result = subprocess.run(
            ['docker', 'service', 'ls', '-f', f'label=com.docker.stack.namespace={PREFIX_STACK_NAME}', '--format',
             '{{.Name}}'],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        output_list = result.stdout.splitlines()
        return output_list

    @staticmethod
    def show_deployed_services():
        os.system('docker stack ps -f "desired-state=running" -f "desired-state=ready" -f "desired-state=accepted" '
                  '--format "table {{.Name}}\t{{.Node}}\t{{.DesiredState}}\t{{.CurrentState}}\t{{.Error}}\t{{.Ports}}" '
                  + f' {PREFIX_STACK_NAME} ')

    @staticmethod
    def show_deployed_services_detail():
        os.system('docker stack ps '
                  '--format "table {{.Name}}\t{{.Node}}\t{{.DesiredState}}\t{{.CurrentState}}\t{{.Error}}\t{{.Ports}}" '
                  '--no-trunc '
                  + f' {PREFIX_STACK_NAME} ')

    @staticmethod
    def show_deployed_machines(show_detail=False):
        os.system('docker node ls --format "table {{if .Self}}*{{end}}{{.Hostname}}{{if .Self}}*{{end}}\t'
                  '{{.Status}}\t{{.Availability}}\t{{.ManagerStatus}}\t{{.TLSStatus}}\t{{.EngineVersion}}"')
        if show_detail:
            os.system("echo ;"
                      "echo '------------';"
                      "echo 'Node Details:';"
                      "echo '------------';"
                      "docker node inspect --format "
                      "'{{.Description.Hostname}}({{.Status.Addr}}):\t{{range $k, $v := .Spec.Labels}}{{$k}}={{$v}} {{else}}{{end}}'"
                      " $(docker node ls -q) ;"
                      "echo ;")

    @staticmethod
    def show_join_tokens():
        os.system('docker swarm join-token manager')
        os.system('docker swarm join-token worker')

    @staticmethod
    def backup_swarm():
        print(f'Starting swarm backup...')

        command_string = f'sudo systemctl stop docker'
        print(f'Executing command: "{command_string}"...')
        os.system(f'{command_string}')

        now_time = datetime.datetime.now().strftime("%Y%m%d%H%M%S")
        command_string = f'sudo tar -czvf {now_time}.swarm.tar.gz /var/lib/docker/swarm'
        print(f'Executing command: "{command_string}"...')
        os.system(f'{command_string}')

        repository_path = os.environ.get("MANAGER_PATH", default='')
        if repository_path:
            if not os.path.isdir(repository_path):
                print(f'backup_swarm: $MANAGER_PATH is not a valid directory, '
                      f'backup file created at current work path.')
                return
        else:
            print(f'backup_swarm: $MANAGER_PATH is not defined, backup file created at current work path.')
            return
        backup_path = os.path.normpath(os.path.join(repository_path, "..", SWARM_BACKUP_DIR))
        try_makedirs(backup_path)

        command_string = f'sudo mv ./{now_time}.swarm.tar.gz {backup_path}'
        print(f'Executing command: "{command_string}"...')
        os.system(f'{command_string}')

        command_string = f'sudo systemctl start docker'
        print(f'Executing command: "{command_string}"...')
        os.system(f'{command_string}')

        print(f'Finished swarm backup.')

    @staticmethod
    def restore_swarm(backup_file):
        print(f'Restoring swarm...')

        extract_path = relative_and_absolute_path_to_abs(backup_file)
        if not str(extract_path).endswith('.swarm.tar.gz'):
            print(f'restore_swarm: Failed. File "{extract_path}" is not a valid swarm backup file.')
            return
        if not os.path.isfile(extract_path):
            print(f'restore_swarm: Failed. File "{extract_path}" is not exists.')
            return

        print(f'unpack tar.gz file into swarm directory.')
        command_string = f'tar -zxvf {extract_path} -C /tmp/'
        print(f'Executing command: "{command_string}"...')
        os.system(f'{command_string}')

        if not os.path.isdir(f'/tmp/var/lib/docker/swarm'):
            print(f'restore_swarm: Failed. Backup file used for restoring is not a valid swarm backup.')
            return

        command_string = f'sudo systemctl stop docker'
        print(f'Executing command: "{command_string}"...')
        os.system(f'{command_string}')

        command_string = f'sudo rm -rf /var/lib/docker/swarm'
        print(f'Executing command: "{command_string}"...')
        ans = input(f'Confirm to execute the above operation[y|n]?')
        if ans.lower() == 'y' or ans.lower() == 'yes':
            os.system(f'{command_string}')
        else:
            print(f'Operation exit.')
            return

        command_string = f'sudo mv -f /tmp/var/lib/docker/swarm /var/lib/docker/swarm'
        print(f'Executing command: "{command_string}"...')
        os.system(f'{command_string}')

        command_string = f'sudo systemctl start docker'
        print(f'Executing command: "{command_string}"...')
        os.system(f'{command_string}')

        command_string = f'docker swarm init --force-new-cluster'
        print(f'Executing command: "{command_string}"...')
        os.system(f'{command_string}')

        print(f'Restoring finished.')


class SwarmService:
    def __init__(self, name, service_type, **kwargs):
        """
        :param name: service name.
        :param service_type:
            "ioc", or
            "global"(services that should run on each node), or
            "local"(services of swarm infrastructures), or
            "custom"(other services that also should run in this system)
        """
        self.name = name
        self.service_type = None
        self.service_name = f'{PREFIX_STACK_NAME}_srv-{name}'
        if service_type == 'ioc':
            self.service_type = 'ioc'
            self.dir_path = os.path.abspath(os.path.join(get_manager_path(), '..', MOUNT_DIR, SWARM_DIR, self.name))
            self.service_file = IOC_SERVICE_FILE
        elif service_type == 'global':
            self.service_type = 'global'
            self.dir_path = os.path.abspath(
                os.path.join(get_manager_path(), '..', MOUNT_DIR, SWARM_DIR, GLOBAL_SERVICE_FILE_DIR))
            self.service_file = f'{self.name}.yaml'
        elif service_type == 'local':
            self.service_type = 'local'
            self.dir_path = os.path.abspath(
                os.path.join(get_manager_path(), '..', MOUNT_DIR, SWARM_DIR, self.name))
            self.service_file = f'{self.name}.yaml'
        else:
            self.service_type = 'custom'
            compose_file_path = kwargs.get('compose_file')
            if not compose_file_path:
                # if no extra arg about compose_file path given, try to find it from ServiceDefinition.py.
                flag = False
                for item in CustomServicesList:
                    if self.name == item[0]:
                        compose_file_path = relative_and_absolute_path_to_abs(item[1])
                        self.dir_path = os.path.dirname(compose_file_path)
                        self.service_file = os.path.basename(compose_file_path)
                        flag = True
                        break
                if not flag:
                    self.dir_path = ""
                    self.service_file = ""
            else:
                compose_file_path = relative_and_absolute_path_to_abs(compose_file_path)
                self.dir_path = os.path.dirname(compose_file_path)
                self.service_file = os.path.basename(compose_file_path)

    def __repr__(self):
        return f'SwarmService("{self.name}", service_type="{self.service_type}")'

    @property
    def is_available(self):
        if os.path.isfile(os.path.join(self.dir_path, self.service_file)):
            return True
        else:
            return False

    @property
    def is_deployed(self):
        if self.service_name in SwarmManager.get_deployed_swarm_services():
            return True
        else:
            return False

    @property
    def current_state(self):
        if self.is_deployed:
            result = subprocess.run(
                ['docker', 'service', 'ps', '-f', f'desired-state=Running', '-f', f'desired-state=Ready', '--format',
                 '{{.CurrentState}}',
                 self.service_name],
                stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            if not result.stdout.splitlines():
                return 'Unknown'
            return result.stdout.splitlines()[0]
        else:
            if self.is_available:
                return 'Available. Not deployed'
            else:
                return 'Not Available'

    @property
    def replicas(self):
        if self.is_deployed:
            result = subprocess.run(
                ['docker', 'stack', 'services', PREFIX_STACK_NAME, '-f', f'name={self.service_name}', '--format',
                 '{{.Replicas}}', ],
                stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            return f'{result.stdout}{result.stderr}'
        else:
            return '-/-'

    def deploy(self):
        print(self)
        if self.is_available:
            if self.is_deployed:
                print(f'SwarmService("{self.name}").deploy_service: Service has already been deployed.')
            else:
                print(f'SwarmService("{self.name}").deploy_service: Service deploying ... ')
                command = (f'cd {self.dir_path}; '
                           f'docker stack deploy --compose-file {self.service_file} {PREFIX_STACK_NAME} '
                           f'--detach --with-registry-auth')
                os.system(command)
        else:
            print(f'SwarmService("{self.name}").deploy_service: Failed to deploy, service is not available.')

    def remove(self, remove_file=False):
        if self.is_deployed:
            print(f'SwarmService("{self.name}").remove_service: Removing this service.')
            os.system(f'docker service rm {self.service_name}')
            if remove_file:
                if os.path.isfile(os.path.join(self.dir_path, self.service_file)):
                    try:
                        os.remove(os.path.join(self.dir_path, self.service_file))
                    except Exception as e:
                        print(f'SwarmService("{self.name}").remove_service: Remove swarm file failed.')
                    else:
                        print(f'SwarmService("{self.name}").remove_service: Swarm file removed.')
        else:
            print(f'SwarmService("{self.name}").remove_service: Failed to remove, service is not deployed.')

    def show_info(self):
        if self.is_deployed:
            os.system(f'docker service inspect {self.service_name} --pretty')
        else:
            print(f'No information for "{self.name}" as it has not been deployed.')

    def show_ps(self):
        if self.is_deployed:
            os.system(f'docker service ps --no-trunc {self.service_name}')
        else:
            print(f'No information for "{self.name}" as it has not been deployed.')

    def show_logs(self):
        print(self)
        if self.is_deployed:
            if self.service_type == 'ioc' or 'iocLogServer' in self.service_name:
                os.system(f'docker service logs --follow --tail=1000 --raw {self.service_name}')
            else:
                os.system(f'docker service logs --follow --tail=1000 {self.service_name}')
        else:
            print(f'No logs for "{self.name}" as it has not been deployed yet.')

    def update(self):
        print(self)
        if self.is_deployed:
            command = (f'cd {self.dir_path}; '
                       f'docker stack deploy --compose-file {self.service_file} {PREFIX_STACK_NAME} --detach')
            os.system(command)
        else:
            print(f'Failed to update "{self.name}" as it has not been deployed yet.')


if __name__ == '__main__':
    # SwarmManager.show_deployed_services()
    # SwarmManager.show_join_tokens()
    # SwarmManager.show_deployed_info()
    # SwarmManager.show_deployed_machines()
    # print(SwarmManager.get_deployed_services())
    # s = SwarmService("log", 'global')
    # # print(s.get_logs())
    # s.show_ps()
    # s.show_info()
    # print(s.current_state)
    # SwarmManager().show_info()
    # print(SwarmManager().get_services_from_docker())
    # SwarmManager().list_running_services()
    # SwarmManager.backup_swarm()
    print(SwarmManager.get_deployed_swarm_services())
    print(SwarmManager.list_managed_services())
    print(SwarmService(name='alertManager', service_type='local').is_available)
