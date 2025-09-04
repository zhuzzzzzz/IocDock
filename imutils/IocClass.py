import os
import yaml
import tarfile
import datetime
import configparser

from imutils.IMConfig import *
from imutils.IMError import IMIOCError
from imutils.IMFunc import (try_makedirs, file_remove, dir_remove, file_copy, dir_copy,
                            condition_parse, multi_line_parse, format_normalize,
                            relative_and_absolute_path_to_abs, )


class IocStateManager:
    def __init__(self, dir_path, verbose, **kwargs):
        """
        Initialize an IOC project state manager and read state information file from given path.

        :param dir_path: path to project directory.
        :param verbose: whether to show details about program processing.
        """

        # self.dir_path: directory for IOC project.
        # self.info_file_path

        if not dir_path or not os.path.isdir(dir_path):
            print(f'IocStateManager.__init__: Incorrect initialization parameters: dir_path="{dir_path}".')

        self.dir_path = dir_path
        self.verbose = verbose
        self.info_file_path = os.path.join(self.dir_path, IOC_STATE_INFO_FILE)

        self.conf = None
        self.state = ''
        self.state_info = ''
        self.read_config(create=kwargs.get('create', False))
        self.state = self.get_config('state')
        self.state_info += self.get_config('state_info')

    def create_new(self):
        self.conf = configparser.ConfigParser()
        self.set_config('state', STATE_NORMAL)  # STATE_NORMAL, STATE_WARNING, STATE_ERROR
        self.set_config('state_info', '')
        self.set_config('status', 'created')
        self.set_config('snapshot', 'untracked')  # untracked, tracked
        self.set_config('is_exported', 'false')
        self.write_config()

    def create_error(self):
        self.conf = configparser.ConfigParser()
        self.set_config('state', STATE_ERROR)  # STATE_NORMAL, STATE_WARNING, STATE_ERROR
        self.set_config('state_info', 'unknown')
        self.set_config('status', 'unknown')
        self.set_config('snapshot', 'unknown')
        self.set_config('is_exported', 'unknown')
        self.write_config()

    def read_config(self, create):
        if os.path.exists(self.info_file_path):
            conf = configparser.ConfigParser()
            if conf.read(self.info_file_path):
                self.conf = conf
                if self.verbose:
                    print(f'IocStateManager.read_config: Read state info file "{self.info_file_path}".')
            else:
                if create:
                    self.create_new()
                    if self.verbose:
                        print(f'IocStateManager.read_config: Create state info file "{self.info_file_path}".')
                else:
                    self.create_error()
                    state_info = f'unrecognized state info file.'
                    prompt = f'unrecognized state info "{self.info_file_path}".'
                    self.set_state_info(state=STATE_ERROR, state_info=state_info, prompt=prompt)
        else:
            if create:
                self.create_new()
                if self.verbose:
                    print(f'IocStateManager.read_config: Create state info file "{self.info_file_path}".')
            else:
                self.create_error()
                state_info = f'state info file lost.'
                prompt = f'state info file "{self.info_file_path}" lost.'
                self.set_state_info(state=STATE_ERROR, state_info=state_info, prompt=prompt)

    def write_config(self):
        self.normalize_config()
        with open(self.info_file_path, 'w') as f:
            self.conf.write(f)

    def set_config(self, option, value, section='STATE'):
        section = section.upper()  # sections should only be uppercase.
        if self.conf:
            if section not in self.conf:
                self.conf.add_section(section)
        else:
            self.conf = configparser.ConfigParser()
            self.conf.add_section(section)
        self.conf.set(section, option, value)

    def get_config(self, option, section="STATE"):
        value = ''  # undefined option will return ''.
        if self.conf.has_option(section, option):
            value = self.conf.get(section, option)
        return value

    def check_config(self, option, value, section='STATE'):
        if self.conf:
            if section in self.conf.sections():
                # common check logic
                for key, val in self.conf.items(section):
                    if key == option and val == value:
                        return True
        return False

    def show_config(self):
        if self.conf:
            for section in self.conf.sections():
                print(f'[{section}]')
                for key, value in self.conf.items(section):
                    if len(multi_line_parse(value)) > 1:
                        temp_value = f'\n{value.strip()}'
                    else:
                        temp_value = value.strip()
                    temp_value = temp_value.replace('\n', '\n\t')
                    print(f'{key}: {temp_value}')
                else:
                    print('')

    def normalize_config(self):
        temp_conf = configparser.ConfigParser()
        for section in self.conf.sections():
            if not temp_conf.has_section(section):
                temp_conf.add_section(section.upper())
            for option in self.conf.options(section):
                temp = self.conf.get(section, option)
                temp_conf.set(section.upper(), option, format_normalize(temp))
        else:
            self.conf = temp_conf

    def remove(self):
        file_remove(self.info_file_path, verbose=False)

    def set_state_info(self, state, state_info, prompt=''):
        if self.state_info:
            prefix_newline = '\n'
        else:
            prefix_newline = ''
        state_info = f'{prefix_newline}[{state}] [{datetime.datetime.now().strftime("%Y/%m/%d-%H:%M:%S")}] {state_info}'
        if prompt:
            state_info = state_info + '\n' + '>>> prompt | ' + prompt + '\n'
        if state == STATE_ERROR:
            self.state = state
            self.state_info += state_info
        elif state == STATE_WARNING:
            if not self.state == STATE_ERROR:
                self.state = state
            else:
                self.state = STATE_ERROR
            self.state_info += state_info
        else:
            return
        self.set_config('state', self.state)
        self.set_config('state_info', self.state_info)
        self.write_config()


class IOC:
    def __init__(self, dir_path=None, read_mode=False, verbose=False, **kwargs):
        """
        Initialize an IOC project manager and read config file from given path.

        :param dir_path: path to project directory.
        :param read_mode: init by read-only mode.
        :param verbose: whether to show details about program processing.
        :param kwargs: extra arguments.
            "create" to indicate a creation operation.
            "state_info_ini_dir" to indicate dir of state info file when reading config file not in repository dir.
            "no_exec_get_src" to control the behavior of get_src_file().
        """

        # self.dir_path: directory for IOC project.
        # self.src_path
        # self.config_file_path
        # self.project_path: directory for separating editing files and non-editing files.
        # self.settings_path
        # self.logs_path
        # self.startup_path
        # self.db_path
        # self.boot_path
        # self.snapshot_path
        # self.config_snapshot_file
        # self.src_snapshot_path
        # self.dir_path_for_mount
        # self.config_file_path_for_mount
        # self.settings_path_in_docker
        # self.logs_path_in_docker
        # self.startup_path_in_docker

        if verbose:
            if read_mode:
                print(f'IOC.__init__: Start initializing at "{dir_path}" in read-only mode.')
            else:
                print(f'IOC.__init__: Start initializing at "{dir_path}".')
        if not dir_path or not os.path.isdir(dir_path):
            print(f'IOC.__init__: Invalid initialization parameters: dir_path="{dir_path}".')
            return

        self.read_mode = read_mode
        self.verbose = verbose
        self.dir_path = os.path.normpath(dir_path)

        self.src_path = os.path.join(self.dir_path, 'src')
        self.config_file_path = os.path.join(self.dir_path, IOC_CONFIG_FILE)
        self.project_path = os.path.join(dir_path, 'project')
        self.settings_path = os.path.join(self.project_path, 'settings')
        self.logs_path = os.path.join(self.project_path, 'logs')
        self.startup_path = os.path.join(self.project_path, 'startup')
        self.db_path = os.path.join(self.startup_path, 'db')
        self.boot_path = os.path.join(self.startup_path, 'iocBoot')

        self.state_manager = IocStateManager(dir_path=kwargs.get('state_info_ini_dir', self.dir_path),
                                             verbose=self.verbose, create=kwargs.get('create', False))

        self.conf = None
        if not self.read_mode:
            self.read_config(create=kwargs.get('create', False))
        else:
            self.read_config(create=False)

        self.name = self.get_config('name')
        if self.name != os.path.basename(self.dir_path):
            old_name = self.name
            self.name = os.path.basename(self.dir_path)
            print(f'IOC.__init__: Set attribute "self.name" from "{old_name}" to "{self.name}" '
                  f'according to project top-level path basename.')

        self.snapshot_path = os.path.join(SNAPSHOT_PATH, self.name)
        self.config_snapshot_file = os.path.join(self.snapshot_path, IOC_CONFIG_FILE)
        self.src_snapshot_path = os.path.join(self.snapshot_path, 'src')

        self.dir_path_for_mount = os.path.join(MOUNT_PATH,
                                               self.get_config('host') if self.get_config('host') else 'swarm',
                                               self.name)
        self.config_file_path_for_mount = os.path.join(self.dir_path_for_mount, IOC_CONFIG_FILE)
        self.startup_path_for_mount = os.path.join(self.dir_path_for_mount, 'startup')

        self.settings_path_in_docker = os.path.join(CONTAINER_IOC_RUN_PATH, self.name, 'settings')
        self.logs_path_in_docker = os.path.join(CONTAINER_IOC_RUN_PATH, self.name, 'logs')
        self.startup_path_in_docker = os.path.join(CONTAINER_IOC_RUN_PATH, self.name, 'startup')

        self.get_src_file(init_mode=True, no_exec=kwargs.get('no_exec_get_src', False))

        if not self.read_mode:
            #
            if not self.state_manager.check_config('state', 'normal'):
                if self.verbose:
                    print(f'IOC.__init__: Try repairing IOC "{self.name}".')
                self.try_repair()

        if self.verbose:
            print(f'IOC.__init__: Finished initializing for IOC "{self.name}".')

    def create_new(self):
        self.make_directory_structure()
        self.set_default_settings()

    def make_directory_structure(self):
        try_makedirs(self.src_path, self.verbose)
        try_makedirs(self.settings_path, self.verbose)
        try_makedirs(self.logs_path, self.verbose)
        try_makedirs(self.db_path, self.verbose)
        try_makedirs(self.boot_path, self.verbose)

    def set_default_settings(self):
        self.set_config('name', os.path.basename(self.dir_path))
        self.set_config('host', '')
        self.set_config('image', '')
        self.set_config('bin', DEFAULT_IOC)
        self.set_config('module', DEFAULT_MODULES)
        self.set_config('description', '')
        self.set_config('db_file', '', section='SRC')
        self.set_config('protocol_file', '', section='SRC')
        self.set_config('others_file', '', section='SRC')
        self.set_config('load', '', section='DB')
        self.set_config('report_info', 'true', section='SETTING')
        self.set_config('caputlog_json', 'false', section='SETTING')
        self.set_config('epics_env', '', section='SETTING')
        self.set_config('labels', '', section='DEPLOY')
        self.set_config('cpu-limit', RESOURCE_IOC_CPU_LIMIT, section='DEPLOY')
        self.set_config('memory-limit', RESOURCE_IOC_MEMORY_LIMIT, section='DEPLOY')
        self.set_config('cpu-reserve', '', section='DEPLOY')
        self.set_config('memory-reserve', '', section='DEPLOY')
        self.set_config('constraints', '', section='DEPLOY')
        self.write_config()

    # read config or create a new config or set error.
    def read_config(self, create):
        if os.path.exists(self.config_file_path):
            conf = configparser.ConfigParser()
            if conf.read(self.config_file_path):
                self.conf = conf
                if self.verbose:
                    print(f'IOC.read_config: Read config file "{self.config_file_path}".')
            else:
                state_info = 'unrecognized config file.'
                prompt = f'unrecognized config file "{self.config_file_path}".'
                self.state_manager.set_state_info(state=STATE_ERROR, state_info=state_info, prompt=prompt)
        else:
            if create:
                self.conf = configparser.ConfigParser()
                self.create_new()
                if self.verbose:
                    print(f'IOC.read_config: Create config file "{self.config_file_path}" with default settings.')
            else:
                state_info = 'config file lost.'
                prompt = f'config file "{self.config_file_path}" lost.'
                self.state_manager.set_state_info(state=STATE_ERROR, state_info=state_info, prompt=prompt)

    def write_config(self):
        self.normalize_config()
        with open(self.config_file_path, 'w') as f:
            self.conf.write(f)

    def set_config(self, option, value, section='IOC'):
        section = section.upper()  # sections should only be uppercase.
        if self.conf:
            if section not in self.conf:
                self.conf.add_section(section)
        else:
            self.conf = configparser.ConfigParser()
            self.conf.add_section(section)
        self.conf.set(section, option, value)

    def get_config(self, option, section="IOC"):
        value = ''  # undefined option will return ''.
        if self.conf and self.conf.has_option(section, option):
            value = self.conf.get(section, option)
        return value

    def check_config(self, option, value, section='IOC'):
        if self.conf:
            if section in self.conf.sections():
                # check logic special to 'module' option of section 'IOC'.
                if option == 'module' and section == 'IOC':
                    if value == '':
                        if self.get_config('module') == '':
                            return True
                        else:
                            return False
                    elif value.lower() in self.get_config('module').lower():
                        return True
                    else:
                        return False
                # common check logic
                for key, val in self.conf.items(section):
                    if key == option and val == value:
                        return True
        return False

    def show_config(self):
        print(f' "{self.name}" '.center(70, '='))
        self.state_manager.show_config()  # show state info
        if self.conf:
            for section in self.conf.sections():
                print(f'[{section}]')
                for key, value in self.conf.items(section):
                    if len(multi_line_parse(value)) > 1:
                        temp_value = f'\n{value.strip()}'
                    else:
                        temp_value = value.strip()
                    temp_value = temp_value.replace('\n', '\n\t')
                    print(f'{key}: {temp_value}')
                else:
                    print('')

    def normalize_config(self):
        temp_conf = configparser.ConfigParser()
        for section in self.conf.sections():
            if not temp_conf.has_section(section):
                temp_conf.add_section(section.upper())
            for option in self.conf.options(section):
                temp = self.conf.get(section, option)
                temp_conf.set(section.upper(), option, format_normalize(temp))
        else:
            self.conf = temp_conf

    def remove(self, all_remove=False):
        # remove entire project in mount dir
        dir_remove(self.dir_path, self.verbose)
        if all_remove:
            dir_remove(self.snapshot_path, self.verbose)
            # remove entire project in mount dir
            dir_remove(self.dir_path_for_mount, self.verbose)
            print(f'Success. IOC "{self.name}" removed completely.')
        else:
            print(f'Success. IOC "{self.name}" removed.')

    def add_module_template(self, template_type):
        if template_type.lower() == 'asyn':
            if not self.conf.has_section('RAW'):
                self.add_raw_cmd_template()
            cmd_before_dbload = (f'drvAsynIPPortConfigure("L0","192.168.0.23:4001",0,0,0)\n'
                                 f'drvAsynSerialPortConfigure("L0","/dev/tty.PL2303-000013FA",0,0,0)\n'
                                 f'asynSetOption("L0", -1, "baud", "9600")\n'
                                 f'asynSetOption("L0", -1, "bits", "8")\n'
                                 f'asynSetOption("L0", -1, "parity", "none")\n'
                                 f'asynSetOption("L0", -1, "stop", "1")\n'
                                 f'asynSetOption("L0", -1, "clocal", "Y")\n'
                                 f'asynSetOption("L0", -1, "crtscts", "Y")\n')
            cmd_at_dbload = f'dbLoadRecords("db/asynRecord.db","P=xxx,R=:asyn,PORT=xxx,ADDR=xxx,IMAX=xxx,OMAX=xxx")\n'
            copy_str = f'templates/db/asynRecord.db:src/asynRecord.db:wr'
            self.set_config('cmd_before_dbload', cmd_before_dbload, section='RAW')
            self.set_config('cmd_at_dbload', cmd_at_dbload, section='RAW')
            self.set_config('file_copy', copy_str, section='RAW')
            self.write_config()
            return True
        elif template_type.lower() == 'stream':
            if not self.conf.has_section('RAW'):
                self.add_raw_cmd_template()
            cmd_before_dbload = (f'epicsEnvSet("STREAM_PROTOCOL_PATH", {self.startup_path_in_docker})\n'
                                 f'drvAsynIPPortConfigure("L0","192.168.0.23:4001",0,0,0)\n'
                                 f'drvAsynSerialPortConfigure("L0","/dev/tty.PL2303-000013FA",0,0,0)\n'
                                 f'asynSetOption("L0", -1, "baud", "9600")\n'
                                 f'asynSetOption("L0", -1, "bits", "8")\n'
                                 f'asynSetOption("L0", -1, "parity", "none")\n'
                                 f'asynSetOption("L0", -1, "stop", "1")\n'
                                 f'asynSetOption("L0", -1, "clocal", "Y")\n'
                                 f'asynSetOption("L0", -1, "crtscts", "Y")\n')
            cmd_at_dbload = f''
            copy_str = f'src/protocol_file.proto:startup/protocol_file.proto:r'
            self.set_config('cmd_before_dbload', cmd_before_dbload, section='RAW')
            self.set_config('cmd_at_dbload', cmd_at_dbload, section='RAW')
            self.set_config('file_copy', copy_str, section='RAW')
            self.write_config()
            return True
        else:
            return False

    def add_raw_cmd_template(self):
        sc = 'RAW'
        if self.conf.has_section(sc):
            print(f'IOC("{self.name}").add_raw_cmd_template: Failed. Section "{sc}" already exists.')
            return False
        self.set_config('cmd_before_dbload', '', sc)
        self.set_config('cmd_at_dbload', '', sc)
        self.set_config('cmd_after_iocinit', '', sc)
        self.set_config('file_copy', '', sc)
        return True

    # From given path copy source files and update ioc.ini settings according to file suffix specified.
    # src_p: existed path from where to get source files, absolute path or relative path, None to use IOC src path.
    def get_src_file(self, src_dir=None, init_mode=False, print_info=False, no_exec=False):
        if no_exec:
            return

        init_mode = init_mode or self.read_mode
        if self.verbose:
            if init_mode:
                print(f'IOC("{self.name}").get_src_file: Start in IOC init mode.')
            else:
                print(f'IOC("{self.name}").get_src_file: Start.')

        if not os.path.isdir(self.src_path):
            print(f'IOC("{self.name}").get_src_file: Failed. Source path of project "{self.src_path}" not exist.')
            state_info = 'source directory lost.'
            prompt = 'source directory was lost and an empty dir was created.'
            self.state_manager.set_state_info(STATE_ERROR, state_info=state_info, prompt=prompt)
            try_makedirs(self.src_path, verbose=self.verbose)

        if init_mode:
            db_list = self.get_config('db_file', 'SRC')
            proto_list = self.get_config('proto_file', 'SRC')
            others_list = self.get_config('others_file', 'SRC')
            file_list = list(filter(None, db_list.split(','))) + list(filter(None, proto_list.split(','))) + list(
                filter(None, others_list.split(',')))
            for item in file_list:
                item = item.strip()
                if item not in os.listdir(self.src_path):
                    state_info = 'source file lost.'
                    prompt = f'source file "{item}" lost.'
                    self.state_manager.set_state_info(STATE_ERROR, state_info=state_info, prompt=prompt)
            if self.verbose:
                print(f'IOC("{self.name}").get_src_file: Finished in IOC init mode.')
            return

        src_p = relative_and_absolute_path_to_abs(src_dir, self.src_path)
        if not os.path.exists(src_p):
            print(f'IOC("{self.name}").get_src_file: Failed. Dir path "{src_p}" not exist.')
            return

        if self.verbose:
            print(f'IOC("{self.name}").get_src_file: Collect files from "{src_p}".')

        db_list = ''
        proto_list = ''
        others_list = ''
        # When add file from other directory, to get the files already in self.src_path first.
        if src_p != self.src_path:
            for item in os.listdir(self.src_path):
                if item.endswith(DB_SUFFIX):
                    db_list += f'{item}, '
                elif item.endswith(PROTO_SUFFIX):
                    proto_list += f'{item}, '
                elif item.endswith(OTHER_SUFFIX):
                    others_list += f'{item}, '

        file_flag = False
        # Copy files from given path and set db file option, duplicate files will result in a warning message.
        for item in os.listdir(src_p):
            if item.endswith(DB_SUFFIX):
                if item not in db_list:
                    db_list += f'{item}, '
                    if src_p != self.src_path:
                        file_copy(os.path.join(src_p, item), os.path.join(self.src_path, item), 'rw', self.verbose)
                        file_flag = True
                        if self.verbose or print_info:
                            print(f'add "{item}".')
                else:
                    if src_p != self.src_path:
                        file_copy(os.path.join(src_p, item), os.path.join(self.src_path, item), 'rw', self.verbose)
                        file_flag = True
                    if self.verbose or print_info:
                        print(f'overwrite "{item}".')
            elif item.endswith(PROTO_SUFFIX):
                if item not in proto_list:
                    proto_list += f'{item}, '
                    if src_p != self.src_path:
                        file_copy(os.path.join(src_p, item), os.path.join(self.src_path, item), 'rw', self.verbose)
                        file_flag = True
                        if self.verbose or print_info:
                            print(f'add "{item}".')
                else:
                    if src_p != self.src_path:
                        file_copy(os.path.join(src_p, item), os.path.join(self.src_path, item), 'rw', self.verbose)
                        file_flag = True
                    if self.verbose or print_info:
                        print(f'overwrite "{item}".')
            elif item.endswith(OTHER_SUFFIX):
                if item not in others_list:
                    others_list += f'{item}, '
                    if src_p != self.src_path:
                        file_copy(os.path.join(src_p, item), os.path.join(self.src_path, item), 'rw', self.verbose)
                        file_flag = True
                        if self.verbose or print_info:
                            print(f'add "{item}".')
                else:
                    if src_p != self.src_path:
                        file_copy(os.path.join(src_p, item), os.path.join(self.src_path, item), 'rw', self.verbose)
                        file_flag = True
                    if self.verbose or print_info:
                        print(f'overwrite "{item}".')

        # Update the settings.
        db_list = db_list.rstrip(', ')
        proto_list = proto_list.rstrip(', ')
        others_list = others_list.rstrip(', ')
        if db_list:
            self.set_config('db_file', db_list, 'SRC')
            if self.verbose or print_info:
                print(f'IOC("{self.name}").get_src_file: Managed db files "{db_list}".')
        if proto_list:
            self.set_config('protocol_file', proto_list, 'SRC')
            if self.verbose or print_info:
                print(f'IOC("{self.name}").get_src_file: Managed protocol files "{proto_list}".')
        if others_list:
            self.set_config('others_file', others_list, 'SRC')
            if self.verbose or print_info:
                print(f'IOC("{self.name}").get_src_file: Managed other files "{others_list}".')
        if any((db_list, proto_list, others_list)):
            self.write_config()

        if self.verbose or print_info:
            if not file_flag:
                print(f'IOC("{self.name}").get_src_file: No file collected.')

    # Generate .substitutions file for st.cmd to load and prepare db files.
    def generate_substitutions_file(self):
        if self.verbose:
            print(f'IOC("{self.name}").generate_substitutions_file: Start.')
        try_makedirs(self.db_path, self.verbose)
        lines_to_add = []
        for load_line in multi_line_parse(self.get_config('load', 'DB')):
            db_file, *conditions = load_line.split(',')
            # print(conditions)
            db_file = db_file.strip()
            if db_file not in os.listdir(self.src_path):
                state_info = 'option "load" in section "DB" invalid.'
                prompt = f'db file "{db_file}" not found.'
                self.state_manager.set_state_info(state=STATE_WARNING, state_info=state_info, prompt=prompt)
                print(f'IOC("{self.name}").generate_substitutions_file: Failed. DB file "{db_file}" not found in '
                      f'path "{self.src_path}" while parsing string "{load_line}" in "load" option.')
                return False
            else:
                file_copy(os.path.join(self.src_path, db_file), os.path.join(self.db_path, db_file), 'r', self.verbose)
            ks = ''
            vs = ''
            for c in conditions:
                k, v = condition_parse(c)
                if k:
                    ks += f'{k}, '
                    vs += f'{v}, '
                else:
                    state_info = 'option "load" in section "DB" invalid.'
                    prompt = f'invalid macro definition in "{load_line}".'
                    self.state_manager.set_state_info(state=STATE_WARNING, state_info=state_info, prompt=prompt)
                    print(f'IOC("{self.name}").generate_substitutions_file: Failed. Bad load string '
                          f'"{load_line}" defined in {IOC_CONFIG_FILE}. You may need to check and set the attributes correctly.')
                    return False
            else:
                ks = ks.strip(', ')
                vs = vs.strip(', ')
            lines_to_add.append(f'\nfile db/{db_file} {{\n')
            lines_to_add.append(f'    pattern {{ {ks} }}\n')
            lines_to_add.append(f'        {{ {vs} }}\n')
            lines_to_add.append(f'}}\n')
        if lines_to_add:
            # write .substitutions file.
            file_path = os.path.join(self.db_path, f'{self.name}.substitutions')
            if os.path.exists(file_path):
                file_remove(file_path, verbose=False)
            try:
                with open(file_path, 'w') as f:
                    f.writelines(lines_to_add)
            except Exception as e:
                state_info = 'substitutions file generating failed.'
                self.state_manager.set_state_info(state=STATE_WARNING, state_info=state_info, prompt=f'{e}')
                print(f'IOC("{self.name}").generate_substitutions_file: Failed. '
                      f'Exception "{e}" occurs while trying to write "{self.name}.substitutions" file.')
                return False
            else:
                if self.verbose:
                    print(f'IOC("{self.name}").generate_substitutions_file: Create "{self.name}.substitutions".')
            # set readonly permission.
            os.chmod(file_path, 0o444)
            print(f'IOC("{self.name}").generate_substitutions_file: Success.')
            return True
        else:
            state_info = 'option "load" in section "DB" invalid.'
            prompt = 'empty load string.'
            self.state_manager.set_state_info(state=STATE_WARNING, state_info=state_info, prompt=prompt)
            print(f'IOC("{self.name}").generate_substitutions_file: Failed. '
                  f'Option "load" in section "DB" should be defined before generating "{self.name}.substitutions".')
            return False

    # Generate all startup files for running an IOC project.
    # This function should be called after that generate_check is passed.
    def generate_startup_files(self):
        if self.verbose:
            print(f'IOC("{self.name}").generate_startup_files: Start.')

        if not self.generate_check():
            print(f'IOC("{self.name}").generate_startup_files": Failed. Checks failed before generating startup files.')
            return

        lines_before_dbload = []
        lines_at_dbload = [f'cd {self.startup_path_in_docker}\n',
                           f'dbLoadTemplate "db/{self.name}.substitutions"\n', ]
        lines_after_iocinit = ['\niocInit\n\n']

        # specify interpreter.
        bin_IOC = self.get_config('bin')
        lines_before_dbload.append(f'#!{CONTAINER_IOC_PATH}/{bin_IOC}/bin/linux-x86_64/{bin_IOC}\n\n')

        # source envPaths.
        lines_before_dbload.append(f'cd {CONTAINER_IOC_PATH}/{bin_IOC}/iocBoot/ioc{bin_IOC}\n')
        lines_before_dbload.append(f'< envPaths\n\n')

        # register support components.
        lines_before_dbload.append(f'cd "${{TOP}}"\n')
        lines_before_dbload.append(f'dbLoadDatabase "dbd/{bin_IOC}.dbd"\n')
        lines_before_dbload.append(f'{bin_IOC}_registerRecordDeviceDriver pdbbase\n\n'.replace('-', '_'))

        # EPICS_env settings.
        # st.cmd
        # lines_before_dbload
        temp = ['#settings\n', ]
        for env_def in multi_line_parse(self.get_config("epics_env", "SETTING")):
            env_name, env_val = condition_parse(env_def)
            temp.append(f'epicsEnvSet("{env_name}","{env_val}")\n')
        else:
            temp.append('\n')
        lines_before_dbload.extend(temp)

        # autosave configurations.
        if self.check_config('module', 'autosave'):
            # st.cmd
            # lines_before_dbload
            temp = [
                '#autosave\n'
                f'epicsEnvSet REQ_DIR {self.settings_path_in_docker}/autosave\n',
                f'epicsEnvSet SAVE_DIR {self.logs_path_in_docker}/autosave\n',
                'set_requestfile_path("$(REQ_DIR)")\n',
                'set_savefile_path("$(SAVE_DIR)")\n',
                f'set_pass0_restoreFile("{self.name}-automake-pass0.sav")\n',
                f'set_pass1_restoreFile("{self.name}-automake-pass1.sav")\n',
                'save_restoreSet_DatedBackupFiles(1)\n',
                'save_restoreSet_NumSeqFiles(3)\n',
                'save_restoreSet_SeqPeriodInSeconds(600)\n',
                'save_restoreSet_RetrySeconds(60)\n',
                'save_restoreSet_CAReconnect(1)\n',
                'save_restoreSet_CallbackTimeout(-1)\n',
                '\n',
            ]
            lines_before_dbload.extend(temp)
            # st.cmd
            # lines after iocinit
            temp = [
                '#autosave after iocInit\n',
                f'makeAutosaveFileFromDbInfo("$(REQ_DIR)/{self.name}-automake-pass0.req","autosaveFields_pass0")\n',
                f'makeAutosaveFileFromDbInfo("$(REQ_DIR)/{self.name}-automake-pass1.req","autosaveFields")\n',
                f'create_monitor_set("{self.name}-automake-pass0.req",10)\n',
                f'create_monitor_set("{self.name}-automake-pass1.req",10)\n',
                '\n',
            ]
            lines_after_iocinit.extend(temp)
            # create log dir and request file dir
            try_makedirs(os.path.join(self.logs_path, 'autosave'), self.verbose)
            try_makedirs(os.path.join(self.settings_path, 'autosave'), self.verbose)

        # caputlog configurations.
        if self.check_config('module', 'caputlog'):
            # st.cmd
            # lines_before_dbload
            temp = [
                f'#caPutLog\n',
                f'asSetFilename("{self.startup_path_in_docker}/{self.name}.acf")\n',
                f'epicsEnvSet("EPICS_IOC_LOG_INET","127.0.0.1")\n',
                f'iocLogPrefix("{self.name} ")\n',
                f'iocLogInit()\n',
                '\n',
            ]
            lines_before_dbload.extend(temp)
            # st.cmd
            # lines after iocinit
            # check whether to use JSON format log.
            if self.check_config('caputlog_json', 'true', 'SETTING'):
                temp = [
                    '#caPutLog after iocInit\n',
                    'caPutJsonLogInit "127.0.0.1:7004" 0\n',
                    '\n',
                ]
            else:
                temp = [
                    '#caPutLog after iocInit\n',
                    'caPutLogInit "127.0.0.1:7004" 0\n',
                    '\n',
                ]
            lines_after_iocinit.extend(temp)
            # caPutLog .acf file
            file_path = os.path.join(self.startup_path, f'{self.name}.acf')
            template_file_path = os.path.join(TEMPLATE_PATH, 'caputlog.acf')
            file_copy(template_file_path, file_path, 'r', self.verbose)

        # status-ioc configurations.
        if self.check_config('module', 'status-ioc'):
            # st.cmd
            # lines_at_dbload
            lines_at_dbload.append(f'dbLoadRecords("db/status_ioc.db","IOC={self.name}")\n')
            # devIocStats .db
            file_path = os.path.join(self.db_path, 'status_ioc.db')
            template_file_path = os.path.join(DB_TEMPLATE_PATH, 'status_ioc.db')
            file_copy(template_file_path, file_path, 'r', self.verbose)

        # status-os configurations.
        if self.check_config('module', 'status-os'):
            # st.cmd
            # lines_at_dbload
            lines_at_dbload.append(f'dbLoadRecords("db/status_OS.db","HOST={self.name}:docker")\n')
            # devIocStats .db
            file_path = os.path.join(self.db_path, 'status_OS.db')
            template_file_path = os.path.join(DB_TEMPLATE_PATH, 'status_OS.db')
            file_copy(template_file_path, file_path, 'r', self.verbose)

        # raw commands configurations.
        if self.conf.has_section('RAW'):
            sc = 'RAW'
            # st.cmd
            # lines_before_dbload
            lines_before_dbload.append(f'{self.get_config("cmd_before_dbload", sc)}\n')
            lines_before_dbload.append('\n')
            # lines_at_dbload
            lines_at_dbload.append(f'{self.get_config("cmd_at_dbload", sc)}\n')
            # lines after iocinit
            lines_after_iocinit.append(f'{self.get_config("cmd_after_iocinit", sc)}\n')
            # file copy
            for item in multi_line_parse(self.get_config('file_copy', sc)):
                fs = item.split(sep=':')
                if len(fs) == 2:
                    src = fs[0]
                    dest = fs[1]
                    mode = 'r'
                else:  # len(fs) == 3 guaranteed by generate_check()
                    src = fs[0]
                    dest = fs[1]
                    mode = fs[2]
                if src.startswith('src/'):
                    src = os.path.join(self.src_path, src.removeprefix('src/'))
                else:  # src.startswith('templates/') guaranteed by generate_check()
                    src = os.path.join(TEMPLATE_PATH, src.removeprefix('templates/'))
                dest = os.path.join(self.project_path, dest)
                file_copy(src, dest, mode, self.verbose)

        # write report code at the end of st.cmd file if defined "report_info: true".
        if self.check_config('report_info', 'true', 'SETTING'):
            report_path = os.path.join(self.logs_path_in_docker, f"{self.name}.info")
            temp = [
                '#report info\n',
                f'system "touch {report_path}"\n',

                f'system "echo \\#date > {report_path}"\n',
                f'date >> {report_path}\n',
                f'system "echo >> {report_path}"\n',

                f'system "echo \\#ip >> {report_path}"\n',
                f'system "hostname -I >> {report_path}"\n',
                f'system "echo >> {report_path}"\n',

                f'system "echo \\#pv list >> {report_path}"\n',
                f'dbl >> {report_path}\n',
                f'system "echo >> {report_path}"\n',

                '\n'
            ]
            lines_after_iocinit.extend(temp)

        # generate .substitutions file.
        if not self.generate_substitutions_file():
            return

        # write st.cmd file.
        try_makedirs(self.boot_path, self.verbose)
        file_path = os.path.join(self.boot_path, 'st.cmd')
        if os.path.exists(file_path):
            file_remove(file_path, verbose=False)
        try:
            with open(file_path, 'w') as f:
                f.writelines(lines_before_dbload)
                f.writelines(lines_at_dbload)
                f.writelines(lines_after_iocinit)
        except Exception as e:
            print(f'IOC("{self.name}").generate_startup_files: Failed. '
                  f'Exception "{e}" occurs while trying to write st.cmd file.')
            state_info = 'write st.cmd file failed.'
            self.state_manager.set_state_info(state=STATE_WARNING, state_info=state_info)
            return
        # set readable and executable permission.
        os.chmod(file_path, 0o555)
        if self.verbose:
            print(f'IOC("{self.name}").generate_startup_files: Create "st.cmd".')

        #
        self.state_manager.set_config('status', 'generated')
        self.state_manager.set_config('state', 'normal')
        self.state_manager.set_config('state_info', '')
        self.state_manager.write_config()
        print(f'IOC("{self.name}").generate_startup_files": Success.')

    # Copy IOC startup files to mount dir for running in container.
    # force_overwrite: "True" will overwrite all files, "False" only files that are not generated during running.
    def export_for_mount(self, force_overwrite=False):
        if self.verbose:
            print(f'IOC("{self.name}").export_for_mount: Start.')

        if not self.state_manager.check_config('state', 'normal'):
            print(f'IOC("{self.name}").export_for_mount: Failed. '
                  f'Exporting operation must under "normal" state.')
            return
        if not (self.state_manager.check_config('status', 'generated') or
                self.state_manager.check_config('status', 'exported')):
            print(f'IOC("{self.name}").export_for_mount: Failed. '
                  f'Startup files should be generated before exporting.')
            return

        container_name = self.name
        host_name = self.get_config('host')
        if not host_name:
            host_name = SWARM_DIR

        top_path = os.path.join(MOUNT_PATH, host_name, container_name)
        if not os.path.isdir(top_path):
            file_to_copy = (IOC_CONFIG_FILE,)
            dir_to_copy = ('settings', 'logs', 'startup',)
            exec_type = 'created'
        elif os.path.isdir(top_path) and force_overwrite:
            file_to_copy = (IOC_CONFIG_FILE,)
            dir_to_copy = ('settings', 'logs', 'startup',)
            exec_type = 'overwritten'
        else:
            file_to_copy = (IOC_CONFIG_FILE,)
            dir_to_copy = ('startup',)
            exec_type = 'updated'

        try_makedirs(top_path, self.verbose)
        for item_file in file_to_copy:
            file_copy(os.path.join(self.dir_path, item_file), os.path.join(top_path, item_file),
                      verbose=self.verbose)
            os.chmod(os.path.join(top_path, item_file), mode=0o444)  # set readonly permission.
        for item_dir in dir_to_copy:
            if not dir_copy(os.path.join(self.project_path, item_dir), os.path.join(top_path, item_dir),
                            self.verbose):
                print(f'IOC("{self.name}").export_for_mount: Failed. '
                      f'Run this command again with "-v" option to see what happened in details.')
                state_info = 'exporting failed.'
                self.state_manager.set_state_info(state=STATE_WARNING, state_info=state_info)
                return
        else:
            print(f'IOC("{self.name}").export_for_mount: Success. Project files {exec_type} in "{top_path}".')

        self.state_manager.set_config('status', 'exported')
        self.state_manager.set_config('is_exported', 'true')
        self.state_manager.write_config()

    def add_snapshot_files(self):
        if self.verbose:
            print(f'IOC("{self.name}").add_snapshot_files: Start.')
        self.delete_snapshot_files()
        # snapshot for config file.
        try_makedirs(self.snapshot_path, self.verbose)
        if os.path.isfile(self.config_file_path):
            if not file_copy(self.config_file_path, self.config_snapshot_file, 'r', self.verbose):
                print(f'IOC("{self.name}").add_snapshot_files: Failed, snapshot file for config created failed.')
                self.state_manager.set_config('snapshot', 'error')
                state_info = f'snapshot files not create correctly.'
                self.state_manager.set_state_info(state=STATE_WARNING, state_info=state_info)
                return False
        else:
            print(f'IOC("{self.name}").add_snapshot_files: Failed, source file "{self.config_file_path}" not exist.')
            self.state_manager.set_config('snapshot', 'error')
            state_info = f'snapshot files not create correctly.'
            self.state_manager.set_state_info(state=STATE_WARNING, state_info=state_info)
            return False
        # snapshot for source files.
        try_makedirs(self.src_snapshot_path, self.verbose)
        for item in os.listdir(self.src_path):
            if not file_copy(os.path.join(self.src_path, item), os.path.join(self.src_snapshot_path, item), 'r',
                             self.verbose):
                print(f'IOC("{self.name}").add_snapshot_files: Failed, snapshot file '
                      f'"{os.path.join(self.src_snapshot_path, item)}" created failed.')
                self.state_manager.set_config('snapshot', 'error')
                state_info = f'snapshot files not create correctly.'
                self.state_manager.set_state_info(state=STATE_WARNING, state_info=state_info)
                return False

        print(f'IOC("{self.name}").add_snapshot_files: Success.')
        self.state_manager.set_config('snapshot', 'tracked')
        self.state_manager.write_config()
        return True

    def delete_snapshot_files(self):
        if os.path.isdir(self.snapshot_path):
            dir_remove(self.snapshot_path, verbose=False)
            self.state_manager.set_config('snapshot', 'untracked')
            self.state_manager.write_config()

    def restore_from_snapshot_files(self, restore_files: list, force_restore=False):
        if not isinstance(restore_files, list) or not list(filter(None, restore_files)):
            print(f'IOC("{self.name}").restore_from_snapshot_file: '
                  f'Failed, input arg "restore_files" must be a non-empty list.')
            return
        else:
            restore_files = list(set(restore_files))  # remove duplicates

        supported_items = []
        files_provided = {'config': '', 'src': []}
        if os.path.isfile(self.config_snapshot_file):
            files_provided['config'] = self.config_snapshot_file
            supported_items.append('ioc.ini')
        if os.path.isdir(self.src_snapshot_path):
            for item in os.listdir(self.src_snapshot_path):
                files_provided['src'].append(os.path.join(self.src_snapshot_path, item))
                supported_items.append(item)

        items_to_restore = []
        unsupported_items = []
        files_to_restore = {'config': '', 'src': []}
        if 'all' in restore_files:
            files_to_restore = files_provided
            items_to_restore = supported_items
        else:
            if 'ioc.ini' in restore_files:
                restore_files.remove('ioc.ini')
                files_to_restore['config'] = files_provided['config']  # as it is to restore, get path of ioc.ini
                if not files_provided['config']:  # if it is not provided, add to unsupported list
                    unsupported_items.append('ioc.ini')
                else:
                    items_to_restore.append('ioc.ini')
            for item in restore_files:
                item_path = os.path.join(self.src_snapshot_path, item)
                if item_path in files_provided:
                    files_to_restore['src'].append(item_path)
                    items_to_restore.append(item)
                else:
                    unsupported_items.append(item)

        supported_file_string = ''
        for item in items_to_restore:
            supported_file_string += f'"{item}", '
        else:
            supported_file_string = supported_file_string.rstrip()
            supported_file_string = supported_file_string.rstrip(',')
        unsupported_file_string = ''
        for item in unsupported_items:
            unsupported_file_string += f'"{item}", '
        else:
            unsupported_file_string = unsupported_file_string.rstrip()
            unsupported_file_string = unsupported_file_string.rstrip(',')

        if not supported_file_string:
            if 'all' in restore_files:
                print(f'IOC("{self.name}").restore_from_snapshot_file: '
                      f'Can\'t restore any snapshot files, as there exists no snapshot files.')
            else:
                print(f'IOC("{self.name}").restore_from_snapshot_file: '
                      f'Can\'t restore any snapshot files from {restore_files}, as they are not exist in snapshot.')
        else:
            if not force_restore:
                while not force_restore:
                    print(f'IOC("{self.name}").restore_from_snapshot_file: Start.\n\n'
                          f'The following files will be restored:\n'
                          f'{supported_file_string}.')
                    if unsupported_items:
                        print(f'\nThe following files will not be restored as they are not exist in snapshot path:\n'
                              f'{unsupported_file_string}.')
                    ans = input(f'\nconfirm to continue?[y|n]:')
                    if ans.lower() == 'n' or ans.lower() == 'no':
                        print(f'IOC("{self.name}").restore_from_snapshot_file": Restoring canceled.')
                        return
                    if ans.lower() == 'y' or ans.lower() == 'yes':
                        print(f'IOC("{self.name}").restore_from_snapshot_file": Execute restoring.')
                        force_restore = True
                        break
                    print('invalid input, please try again.')
            if force_restore:
                if files_to_restore['config']:
                    if not file_copy(files_to_restore['config'], self.dir_path, mode='rw', verbose=self.verbose):
                        print(f'Restoring "{files_to_restore["config"]}" failed.')
                    else:
                        print(f'Restoring "{files_to_restore["config"]}" succeed.')
                for item in files_to_restore['src']:
                    if not file_copy(item, self.src_path, mode='rw', verbose=self.verbose):
                        print(f'Restoring "{item}" failed.')
                    else:
                        print(f'Restoring "{item}" succeed.')

    # Checks before generating the IOC project startup files.
    def generate_check(self):
        if not os.path.isfile(self.config_file_path):
            return False

        check_flag = True

        # Check whether IOC executable binary is specified.
        sc = "IOC"
        if not self.get_config('bin'):
            state_info = f'option "bin" in section "{sc}" not set.'
            self.state_manager.set_state_info(state=STATE_WARNING, state_info=state_info)
            check_flag = False

        # Check whether modules to be installed are set correctly.
        sc = "IOC"
        module_list = self.get_config('module').strip().split(',')
        for s in module_list:
            if s == '':
                continue
            else:
                if s.strip().lower() not in MODULES_PROVIDED:
                    state_info = f'option "module" in section "{sc}" invalid.'
                    prompt = f'"{s.strip()}" is not supported.'
                    self.state_manager.set_state_info(state=STATE_WARNING, state_info=state_info, prompt=prompt)
                    check_flag = False

        # Check whether epics_env definitions are set correctly.
        sc = "SETTING"
        for env_def in multi_line_parse(self.get_config(option="epics_env", section=sc)):
            env_name, env_val = condition_parse(env_def)
            if not env_name:
                state_info = f'option "epics_env" in section "{sc}" invalid.'
                prompt = f'in "{env_def}".'
                self.state_manager.set_state_info(state=STATE_WARNING, state_info=state_info, prompt=prompt)
                check_flag = False

        # Check whether protocol_file definitions are set correctly.
        if self.conf.has_section('STREAM'):
            sc = "STREAM"
            ps = self.get_config(option='protocol_file', section=sc).split(',')
            for item in ps:
                item = item.strip()
                if item not in os.listdir(self.src_path):
                    state_info = f'option "protocol_file" in section "{sc}" invalid.'
                    prompt = f'protocol file "{item}" not found.'
                    self.state_manager.set_state_info(state=STATE_WARNING, state_info=state_info, prompt=prompt)
                    check_flag = False

        # Check whether file_copy definitions are set correctly.
        if self.conf.has_section('RAW'):
            sc = "RAW"
            for item in multi_line_parse(self.get_config('file_copy', sc)):
                fs = item.split(sep=':')
                if not (len(fs) == 2 or len(fs) == 3):
                    state_info = f'option "file_copy" in section "{sc}" invalid.'
                    prompt = f'in "{item}". try standard format: "dir/src_file":"dir/dest_file":[rwx].'
                    self.state_manager.set_state_info(state=STATE_WARNING, state_info=state_info, prompt=prompt)
                    check_flag = False
                    continue
                src = fs[0]
                if not (src.startswith('src/') or src.startswith('templates/')):
                    state_info = f'option "file_copy" in section "{sc}" invalid.'
                    prompt = f'in "{item}". source files can only be in "src/" or "templates/" directory.'
                    self.state_manager.set_state_info(state=STATE_WARNING, state_info=state_info, prompt=prompt)
                    check_flag = False

        return check_flag

    # Check differences between files in snapshot and repository.
    def check_snapshot_consistency(self, print_info=False):
        if not os.path.isdir(self.snapshot_path):
            if print_info:
                print(f'IOC("{self.name}").check_snapshot_consistency": No snapshot available.')
            return False, f'no snapshot'

        if print_info:
            if self.verbose:
                print(f'git diff --no-index --no-prefix {self.config_snapshot_file} {self.config_file_path}')
            res_config_file = os.system(
                f'git diff --no-index --no-prefix {self.config_snapshot_file} {self.config_file_path}')
            if self.verbose:
                print(f'git diff --no-index --no-prefix {self.src_snapshot_path} {self.src_path}')
            res_src_dir = os.system(f'git diff --no-index --no-prefix {self.src_snapshot_path} {self.src_path}')
        else:
            if self.verbose:
                print(
                    f'git diff --no-index --quiet {self.config_snapshot_file} {self.config_file_path} > /dev/null 2>&1')
            res_config_file = os.system(
                f'git diff --no-index --quiet {self.config_snapshot_file} {self.config_file_path} > /dev/null 2>&1')
            if self.verbose:
                print(f'git diff --no-index --quiet {self.src_snapshot_path} {self.src_path} > /dev/null 2>&1')
            res_src_dir = os.system(
                f'git diff --no-index --quiet {self.src_snapshot_path} {self.src_path} > /dev/null 2>&1')

        return (True, 'consistent') if (res_config_file == 0 and res_src_dir == 0) \
            else (False, 'inconsistent')

    def check_running_consistency(self, print_info=False):
        if not self.state_manager.check_config('is_exported', 'true'):
            if print_info:
                print(f'IOC("{self.name}").check_running_consistency": Please export project before checking.')
            return False, f'export required'

        if print_info:
            if self.verbose:
                print(f'git diff --no-index --no-prefix {self.config_file_path_for_mount} {self.config_file_path}')
            res_config_file = os.system(
                f'git diff --no-index --no-prefix {self.config_file_path_for_mount} {self.config_file_path}')
            if self.verbose:
                print(f'git diff --no-index --no-prefix {self.startup_path_for_mount} {self.startup_path}')
            res_startup_dir = os.system(
                f'git diff --no-index --no-prefix {self.startup_path_for_mount} {self.startup_path}')
        else:
            if self.verbose:
                print(f'git diff --no-index --quiet {self.config_file_path_for_mount} {self.config_file_path} '
                      f'> /dev/null 2>&1')
            res_config_file = os.system(
                f'git diff --quiet {self.config_file_path_for_mount} {self.config_file_path} > /dev/null 2>&1')
            if self.verbose:
                print(f'git diff --no-index --quiet {self.startup_path_for_mount} {self.startup_path} > /dev/null 2>&1')
            res_startup_dir = os.system(
                f'git diff --no-index --quiet {self.startup_path_for_mount} {self.startup_path} > /dev/null 2>&1')

        return (True, 'consistent') if (res_config_file == 0 and res_startup_dir == 0) \
            else (False, 'inconsistent')

    def try_repair(self):
        pass


def gen_swarm_files(iocs, verbose):
    """
    Generate Docker Compose file for swarm deploying at swarm data dir for specified IOC projects.

    :param iocs: IOC projects specified to generate compose file.
    :param verbose:
    """
    if verbose:
        print(f'gen_swarm_files: Start. Processing with iocs="{iocs}", verbosity="{verbose}".')

    if not iocs:
        print(f'gen_swarm_files: Failed. No IOC project specified.')
        return

    top_path = os.path.join(MOUNT_PATH, SWARM_DIR)
    if not os.path.isdir(top_path):
        print(f'gen_swarm_files: Failed. Working directory {top_path} is not exist!')
        return
    else:
        if verbose:
            print(f'gen_swarm_files: Working at {top_path}.')

    processed_dir = []
    for service_dir in os.listdir(top_path):
        if not (iocs == ['alliocs'] or service_dir in iocs):
            continue
        service_path = os.path.join(top_path, service_dir)

        # read ioc.ini and get deployment setting.
        ioc_settings = {'service_dir': service_dir}
        ioc_ini_path = os.path.join(service_path, IOC_CONFIG_FILE)
        if not os.path.exists(ioc_ini_path):
            if verbose:
                print(f'gen_swarm_files: Skip directory "{service_dir}" as there is no valid IOC config file.')
            continue
        try:
            temp_ioc = IOC(dir_path=service_path, read_mode=True, verbose=verbose,
                           state_info_ini_dir=os.path.join(REPOSITORY_PATH, service_dir), no_exec_get_src=True)
            if not temp_ioc.check_config(section='IOC', option='host', value='swarm'):
                print(f'gen_swarm_files: Warning. IOC "{service_dir}" not defined in swarm mode, skipped.')
                continue
            if not temp_ioc.get_config(section='IOC', option='image'):
                print(f'gen_swarm_files: Warning. Option "image" not defined for IOC "{service_dir}", skipped.')
                continue
            else:
                ioc_settings['image'] = temp_ioc.get_config(section='IOC', option='image')
            # get resources settings
            ioc_settings['cpu-reserve'] = temp_ioc.get_config(section='DEPLOY', option='cpu-reserve')
            ioc_settings['memory-reserve'] = temp_ioc.get_config(section='DEPLOY', option='memory-reserve')
            ioc_settings['cpu-limit'] = temp_ioc.get_config(section='DEPLOY', option='cpu-limit')
            ioc_settings['memory-limit'] = temp_ioc.get_config(section='DEPLOY', option='memory-limit')
            # make resources dict
            reservations_dict = {}
            limits_dict = {}
            resources_dict = {}
            if ioc_settings['cpu-reserve']:
                reservations_dict['cpus'] = ioc_settings['cpu-reserve']
            if ioc_settings['memory-reserve']:
                reservations_dict['memory'] = ioc_settings['memory-reserve']
            if ioc_settings['cpu-limit']:
                limits_dict['cpus'] = ioc_settings['cpu-limit']
            if ioc_settings['memory-limit']:
                limits_dict['memory'] = ioc_settings['memory-limit']
            if reservations_dict:
                resources_dict['reservations'] = reservations_dict
            if limits_dict:
                resources_dict['limits'] = limits_dict
            # labels
            labels_to_add = {}
            for label_line in multi_line_parse(temp_ioc.get_config(section='DEPLOY', option='labels')):
                k, v = condition_parse(label_line)
                if k:
                    labels_to_add[k] = v
                else:
                    print(f'gen_swarm_files: Warning. '
                          f'Invalid label definition "{label_line}" for IOC "{service_dir}", skipped.')
        except IMIOCError as e:
            print(f'gen_swarm_files: Warning. Exception raised "{e}" while Parsing "{ioc_ini_path}", skipped.')
            continue

        # yaml file title, name of Compose Project must match pattern '^[a-z0-9][a-z0-9_-]*$'
        yaml_data = {
            'services': {},
            'networks': {},
        }
        # add services according to IOC projects.
        temp_yaml = {
            'image': ioc_settings['image'],
            'entrypoint': [
                'bash',
                '-c',
                f'cd RUN/{ioc_settings["service_dir"]}/startup/iocBoot; ./st.cmd;'
            ],
            'tty': True,
            'stdin_open': True,
            'networks': ['hostnet'],
            'volumes': [
                {
                    'type': 'bind',
                    'source': f'../{ioc_settings["service_dir"]}',
                    'target': f'{os.path.join(CONTAINER_IOC_RUN_PATH, ioc_settings["service_dir"])}',
                },
                {
                    'type': 'bind',
                    'source': f'.',
                    'target': f'{os.path.join(CONTAINER_IOC_RUN_PATH, LOG_FILE_DIR)}',
                },
                {
                    'type': 'bind',
                    'source': '/etc/localtime',
                    'target': '/etc/localtime',
                    'read_only': True
                },  # set correct timezone for linux kernel
            ],
            'labels': {'service-type': 'ioc', },
            'deploy': {
                'replicas': 1,
                'placement':
                    {
                        'constraints': [
                            'node.role==worker',
                        ],
                    },
                'update_config':
                    {
                        'parallelism': 1,
                        'delay': '10s',
                        'failure_action': 'rollback',
                    },
            }
        }
        # reservations dict.
        if resources_dict:
            temp_yaml['deploy']['resources'] = resources_dict
        # labels dict
        if labels_to_add:
            temp_yaml['labels'].update(labels_to_add)
        #
        yaml_data['services'].update({f'srv-{ioc_settings["service_dir"]}': temp_yaml})
        # add network for each stack.
        temp_yaml = {
            'external': True,
            'name': 'host',
        }
        yaml_data['networks'].update({f'hostnet': temp_yaml})
        # write yaml file
        file_path = os.path.join(top_path, service_dir, IOC_SERVICE_FILE)
        if os.path.exists(file_path):
            file_remove(file_path, verbose=False)
        with open(file_path, 'w') as file:
            yaml.dump(yaml_data, file, default_flow_style=False)
        # set readonly permission.
        os.chmod(file_path, 0o444)

        processed_dir.append(service_dir)
        print(f'gen_swarm_files: Create swarm file for service "{service_dir}".')
    else:
        if iocs == ['alliocs']:
            print(f'gen_swarm_files: Finished creating swarm files for all IOC projects.')
        else:
            for item in iocs:
                if item not in processed_dir:
                    print(f'gen_swarm_files: Failed to create swarm files for IOC project "{item}", '
                          f'may be it is not correctly set.')


def get_all_ioc(dir_path=None, from_list=None, read_mode=False, verbose=False):
    """
    Get IOC projects at given path from given name list. Return all IOC projects if name list not given.

    :param dir_path: top path to find all ioc projects
    :param from_list: return ioc projects from given list
    :param read_mode: whether to initialize an IOC in read-only mode
    :param verbose: verbosity
    :return: a list of IOC class objects.
    """
    ioc_list = []
    if not dir_path:
        try_makedirs(REPOSITORY_PATH, verbose=verbose)
        dir_path = REPOSITORY_PATH
    items = os.listdir(dir_path)
    if from_list:
        temp_items = []
        for i in items:
            if i in from_list:
                temp_items.append(i)
        else:
            items = temp_items
    items.sort()  # sort according to name string.
    for ioc_name in items:
        subdir_path = os.path.join(dir_path, ioc_name)
        if os.path.isdir(subdir_path):
            ioc_temp = IOC(dir_path=subdir_path, read_mode=read_mode, verbose=verbose)
            ioc_list.append(ioc_temp)
    return ioc_list


def repository_backup(backup_mode, backup_dir, verbose):
    """
    Generate backup file of IOC project files into datetime tgz file.

    :param backup_mode: "src" to back up only config file and source files, "all" to back up all files.
    :param backup_dir: relative path or absolute path to store backup files.
    :param verbose:
    :return:
    """
    ioc_list = get_all_ioc(read_mode=True)
    if ioc_list:
        backup_path = relative_and_absolute_path_to_abs(backup_dir, IOC_BACKUP_DIR)  # default: ./ioc-backup/
        if not os.path.exists(backup_path):
            try_makedirs(backup_path, verbose)
        now_time = datetime.datetime.now().strftime("%Y%m%d%H%M%S")
        tar_dir = os.path.join(backup_path, now_time)

        try:
            for ioc_item in ioc_list:
                # make temporary directory.
                ioc_tar_dir = os.path.join(tar_dir, ioc_item.name)
                try_makedirs(ioc_tar_dir, verbose)
                # copy config file, state info file and "src" dir anyway.
                file_copy(ioc_item.config_file_path, os.path.join(ioc_tar_dir, IOC_CONFIG_FILE), mode='rw',
                          verbose=verbose)
                file_copy(ioc_item.state_manager.info_file_path, os.path.join(ioc_tar_dir, IOC_STATE_INFO_FILE),
                          mode='rw',
                          verbose=verbose)
                dir_copy(ioc_item.src_path, os.path.join(ioc_tar_dir, 'src'), verbose=verbose)
                # copy "project" dir if backup_mode == "all".
                if backup_mode == 'all':
                    # copy from repository
                    dir_copy(ioc_item.startup_path, os.path.join(ioc_tar_dir, 'project', 'startup'), verbose=verbose)
                    # copy from running data
                    ioc_run_path = os.path.join(MOUNT_PATH, ioc_item.get_config('host'), ioc_item.name)
                    dir_copy(os.path.join(ioc_run_path, 'logs'), os.path.join(ioc_tar_dir, 'project', 'logs'),
                             verbose=verbose)
                    dir_copy(os.path.join(ioc_run_path, 'settings'), os.path.join(ioc_tar_dir, 'project', 'settings'),
                             verbose=verbose)
            else:
                with tarfile.open(os.path.join(backup_path, f'{now_time}.ioc.tar.gz'), "w:gz") as tar:
                    tar.add(tar_dir, arcname=os.path.basename(tar_dir))
                dir_remove(tar_dir, verbose=verbose)
                print(f'repository_backup: Finished. Backup file created at {backup_path} in "{backup_mode}" mode.')
        except Exception as e:
            print(f'repository_backup: Failed. Exception raised: {e}.')
            dir_remove(tar_dir, verbose=verbose)
    else:
        print(f'repository_backup: Skipped. No IOC project in repository.')


def restore_backup(backup_path, force_overwrite, verbose):
    """
    Restore IOC projects into repository from tgz backup file.

    :param backup_path: path of tgz backup file.
    :param force_overwrite: whether to force overwrite when existing IOC project conflicts with the backup file.
    :param verbose:
    :return:
    """
    extract_path = relative_and_absolute_path_to_abs(backup_path)
    if not os.path.isfile(extract_path):
        print(f'restore_backup: Failed. File "{extract_path}" to extract not exists.')
        return

    # make temporary directory.
    temp_dir = relative_and_absolute_path_to_abs(f'/tmp/tar_temp_{datetime.datetime.now().strftime("%Y%m%d%H%M%S")}')
    try_makedirs(temp_dir, verbose=verbose)
    # extract tgz files into temporary directory.
    try:
        with tarfile.open(extract_path, 'r:gz') as tar:
            tar.extractall(temp_dir)
    except Exception as e:
        print(f'restore_backup: Failed. Failed to extract "{extract_path}", {e}.')
        dir_remove(temp_dir, verbose=verbose)
        return
    else:
        if verbose:
            print(f'restore_backup: File extracted at {temp_dir}.')
        temp_in_dir = os.path.join(temp_dir, os.listdir(temp_dir)[0])
        print(f'restore_backup: Start restoring from backup file "{os.path.basename(temp_in_dir)}".')

    try:
        # restore IOC projects. if IOC conflicts, skip or overwrite according to force_overwrite.
        ioc_existed = [ioc_item.name for ioc_item in get_all_ioc(read_mode=True)]
        for ioc_item in os.listdir(temp_in_dir):
            backup_ioc_dir = os.path.join(temp_in_dir, ioc_item)
            current_ioc_dir = os.path.join(REPOSITORY_PATH, ioc_item)
            restore_flag = False
            if os.path.isdir(backup_ioc_dir) and os.path.exists(os.path.join(backup_ioc_dir, IOC_CONFIG_FILE)):
                if ioc_item not in ioc_existed:
                    print(f'restore_backup: Restoring IOC project "{ioc_item}".')
                    dir_copy(backup_ioc_dir, current_ioc_dir, verbose=verbose)
                    restore_flag = True
                elif ioc_item in ioc_existed and not force_overwrite:
                    while True:
                        ans = input(f'restore_backup: "{ioc_item}" already exists, overwrite '
                                    f'it(this will remove the original IOC project files)?[y|n]:')
                        if ans.lower() == 'yes' or ans.lower() == 'y':
                            overwrite_flag = True
                            print(f'restore_backup: choose to overwrite "{ioc_item}".')
                            break
                        elif ans.lower() == 'no' or ans.lower() == 'n':
                            overwrite_flag = False
                            print(f'restore_backup: choose to skip "{ioc_item}".')
                            break
                        else:
                            print(f'restore_backup: wrong input, please enter your answer again.')
                    if overwrite_flag:
                        dir_copy(backup_ioc_dir, current_ioc_dir, verbose=verbose)
                        restore_flag = True
                else:
                    print(f'restore_backup: Restoring IOC project "{ioc_item}", local project will be overwrite.')
                    dir_copy(backup_ioc_dir, current_ioc_dir, verbose=verbose)
                    restore_flag = True
            else:
                if verbose:
                    print(f'restore_backup: Skip invalid directory "{ioc_item}".')
            if restore_flag:
                print(f'restore_backup: Restoring IOC project "{ioc_item}" finished.')
                temp_ioc = IOC(dir_path=current_ioc_dir, read_mode=True, verbose=verbose)
                # set status for restored IOC.
                temp_ioc.state_manager.set_config('status', 'restored')
                temp_ioc.write_config()
    except Exception as e:
        # remove temporary directory finally.
        print(f'\nrestore_backup: Falided. Exception raised: {e}.')
        dir_remove(temp_dir, verbose=verbose)
    else:
        # remove temporary directory finally.
        print(f'restore_backup: Restoring Finished.')
        dir_remove(temp_dir, verbose=verbose)
