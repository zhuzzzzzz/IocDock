import os
import filecmp
import configparser

from .IMFunc import try_makedirs, file_remove, dir_remove, file_copy, dir_copy, condition_parse, multi_line_parse, \
    format_normalize, relative_and_absolute_path_to_abs, dir_compare
from .IMConfig import *
from .IMError import IMValueError, IMIOCError


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
            raise IMValueError(f'Incorrect initialization parameters: IocStateManager(dir_path={dir_path}).')
        self.dir_path = dir_path
        self.verbose = verbose
        self.info_file_path = os.path.join(self.dir_path, IOC_STATE_INFO_FILE)

        self.conf = None
        self.state = ''
        self.state_info = ''
        self.read_config(create=kwargs.get('create', False))
        self.state = self.get_config('state')
        self.state_info += self.get_config('state_info')

    def read_config(self, create):
        if os.path.exists(self.info_file_path):
            conf = configparser.ConfigParser()
            if conf.read(self.info_file_path):
                self.conf = conf
                if self.verbose:
                    print(f'IocStateManager.read_config: Read state info file "{self.info_file_path}".')
                return
            else:
                self.set_state_info(state=STATE_ERROR, state_info='unrecognized state info file.')
                return
        else:
            if create:
                self.conf = configparser.ConfigParser()
                if self.verbose:
                    print(f'IocStateManager.read_config: Initialize a new state info file "{self.info_file_path}" '
                          f'with default settings.')
                self.set_config('state', STATE_NORMAL)  # STATE_NORMAL, STATE_WARNING, STATE_ERROR
                self.set_config('state_info', '')
                self.set_config('status', 'created')
                self.set_config('snapshot', 'untracked')  # untracked, tracked
                self.set_config('is_exported', 'false')
                self.write_config()
                return
            else:
                self.set_state_info(state=STATE_ERROR, state_info='state info file lost.')
                return

    def write_config(self):
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
            self.write_config()

    def remove(self, all_remove=False):
        file_remove(self.info_file_path, verbose=self.verbose)

    def set_state_info(self, state, state_info, prompt=''):
        if self.state_info:
            prefix_newline = '\n'
        else:
            prefix_newline = ''
        state_info = f'{prefix_newline}[{state}] {state_info}'
        if prompt:
            state_info = state_info + '\n' + '====>>>> ' + prompt + '\n'
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
        :param kwargs: extra arguments. "create" to indicate a creation operation.
        """

        # self.dir_path: directory for IOC project.
        # self.src_path
        # self.template_path
        # self.config_file_path
        # self.project_path: directory for separating editing files and non-editing files.
        # self.settings_path
        # self.log_path
        # self.startup_path
        # self.db_path
        # self.boot_path
        # self.snapshot_path
        # self.config_snapshot_file
        # self.src_snapshot_path
        # self.dir_path_for_mount
        # self.config_file_path_for_mount
        # self.settings_path_in_docker
        # self.log_path_in_docker
        # self.startup_path_in_docker

        if verbose and read_mode:
            print(f'IOC.__init__: Initializing at "{dir_path}" in read-only mode.')
        if verbose and not read_mode:
            print(f'IOC.__init__: Initializing at "{dir_path}".')

        self.read_mode = read_mode
        self.verbose = verbose
        if not dir_path or not os.path.isdir(dir_path):
            raise IMValueError(f'Incorrect initialization parameters: IOC(dir_path={dir_path}).')
        self.dir_path = os.path.normpath(dir_path)
        self.src_path = os.path.join(self.dir_path, 'src')
        self.template_path = TEMPLATE_PATH
        self.config_file_path = os.path.join(self.dir_path, IOC_CONFIG_FILE)
        self.project_path = os.path.join(dir_path, 'project')
        self.settings_path = os.path.join(self.project_path, 'settings')
        self.log_path = os.path.join(self.project_path, 'log')
        self.startup_path = os.path.join(self.project_path, 'startup')
        self.db_path = os.path.join(self.startup_path, 'db')
        self.boot_path = os.path.join(self.startup_path, 'iocBoot')

        self.state_manager = IocStateManager(dir_path=self.dir_path, verbose=self.verbose,
                                             create=kwargs.get('create', False))

        self.conf = None
        if not self.read_mode:
            self.read_config(create=kwargs.get('create', False))
        else:
            self.read_config(create=False)

        self.name = self.get_config('name')
        if self.name != os.path.basename(self.dir_path) and not self.read_mode:
            old_name = self.name
            self.name = os.path.basename(self.dir_path)
            self.set_config('name', self.name)
            self.write_config()
            print(f'IOC.__init__: Get wrong name "{old_name}" from config file "{self.config_file_path}", '
                  f'directory name of IOC project may has been manually changed to "{self.name}". '
                  f'IOC name has been automatically set in config file to follow that change.')

        self.snapshot_path = os.path.join(SNAPSHOT_PATH, self.name)
        self.config_snapshot_file = os.path.join(self.snapshot_path, IOC_CONFIG_FILE)
        self.src_snapshot_path = os.path.join(self.snapshot_path, 'src')

        self.dir_path_for_mount = os.path.join(MOUNT_PATH, self.get_config('host'), self.get_config('name'))
        self.config_file_path_for_mount = os.path.join(self.dir_path_for_mount, IOC_CONFIG_FILE)

        self.settings_path_in_docker = os.path.join(CONTAINER_IOC_RUN_PATH, self.name, 'settings')
        self.log_path_in_docker = os.path.join(CONTAINER_IOC_RUN_PATH, self.name, 'log')
        self.startup_path_in_docker = os.path.join(CONTAINER_IOC_RUN_PATH, self.name, 'startup')

        if not self.read_mode:
            # update currently managed source files.
            self.get_src_file()
            # normalize settings format.
            self.normalize_config()
            #
            if not self.state_manager.check_config('state', 'normal'):
                if self.verbose:
                    print(f'IOC.__init__: Try repairing IOC "{self.name}".')
                self.try_repair()

        if self.verbose:
            print(f'IOC.__init__: Initializing finished for IOC "{self.name}".\n')

    def create_new(self):
        self.make_directory_structure()
        self.add_default_settings()
        self.write_config()

    def make_directory_structure(self):
        try_makedirs(self.src_path, self.verbose)
        try_makedirs(self.settings_path, self.verbose)
        try_makedirs(self.log_path, self.verbose)
        try_makedirs(self.db_path, self.verbose)
        try_makedirs(self.boot_path, self.verbose)

    # read config or create a new config or set error.
    def read_config(self, create):
        if os.path.exists(self.config_file_path):
            conf = configparser.ConfigParser()
            if conf.read(self.config_file_path):
                self.conf = conf
                if self.verbose:
                    print(f'IOC.read_config: Read config file "{self.config_file_path}".')
            else:
                self.state_manager.set_state_info(state=STATE_ERROR, state_info='unrecognized config file.')
                raise IMIOCError(f'unrecognized config file "{self.config_file_path}".')
        else:
            if create:
                self.conf = configparser.ConfigParser()
                if self.verbose:
                    print(f'IOC.read_config: Initialize a new config file "{self.config_file_path}" '
                          f'with default settings.')
                self.create_new()
            else:
                self.state_manager.set_state_info(state=STATE_ERROR, state_info='config file lost.')
                raise IMIOCError(f'config file "{self.config_file_path}" lost.')

    def write_config(self):
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
        if self.conf.has_option(section, option):
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
            self.write_config()

    def remove(self, all_remove=False):
        if all_remove:
            # delete log file
            self.delete_snapshot_files()
            # remove entire project
            dir_remove(self.dir_path, self.verbose)
            print(f'Success. IOC "{self.name}" removed completely.')
        else:
            # delete auto-generated part
            for item in (self.project_path,):
                dir_remove(item, self.verbose)
            self.state_manager.set_config('status', 'removed')
            self.state_manager.write_config()
            self.check_snapshot_files()
            print(f'Success. IOC "{self.name}" removed, but "src" dir and config file preserved.')

    def add_default_settings(self):
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
            cmd_before_dbload = (f'epicsEnvSet("STREAM_PROTOCOL_PATH", {self.settings_path_in_docker})\n'
                                 f'drvAsynIPPortConfigure("L0","192.168.0.23:4001",0,0,0)\n'
                                 f'drvAsynSerialPortConfigure("L0","/dev/tty.PL2303-000013FA",0,0,0)\n'
                                 f'asynSetOption("L0", -1, "baud", "9600")\n'
                                 f'asynSetOption("L0", -1, "bits", "8")\n'
                                 f'asynSetOption("L0", -1, "parity", "none")\n'
                                 f'asynSetOption("L0", -1, "stop", "1")\n'
                                 f'asynSetOption("L0", -1, "clocal", "Y")\n'
                                 f'asynSetOption("L0", -1, "crtscts", "Y")\n')
            cmd_at_dbload = f'dbLoadRecords("db/asynRecord.db","P=xxx,R=:asyn,PORT=xxx,ADDR=xxx,IMAX=xxx,OMAX=xxx")\n'
            copy_str = f'src/protocol_file.proto:settings/protocol_file.proto:r'
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
    def get_src_file(self, src_dir=None, print_info=False):

        src_p = relative_and_absolute_path_to_abs(src_dir, self.src_path)
        if not os.path.exists(src_p):
            self.state_manager.set_state_info(state=STATE_ERROR, state_info='source directory lost.')
            print(f'IOC("{self.name}").get_src_file: Failed. Path provided "{src_p}" not exist.')
            return

        if self.verbose:
            print(f'IOC("{self.name}").get_src_file: get files from "{src_p}".')

        db_list = ''
        proto_list = ''
        other_list = ''
        # When add file from other directory, to get the files already in self.src_path first.
        if src_p != self.src_path:
            for item in os.listdir(self.src_path):
                if item.endswith(DB_SUFFIX):
                    db_list += f'{item}, '
                elif item.endswith(PROTO_SUFFIX):
                    proto_list += f'{item}, '
                elif item.endswith(OTHER_SUFFIX):
                    other_list += f'{item}, '

        # Copy files from given path and set db file option, duplicate files will result in a warning message.
        for item in os.listdir(src_p):
            if item.endswith(DB_SUFFIX):
                if item not in db_list:
                    db_list += f'{item}, '
                    if src_p != self.src_path:
                        file_copy(os.path.join(src_p, item), os.path.join(self.src_path, item), 'r', self.verbose)
                        if print_info:
                            print(f'IOC("{self.name}").get_src_file: add "{item}".')
                else:
                    if src_p != self.src_path:
                        file_copy(os.path.join(src_p, item), os.path.join(self.src_path, item), 'r', self.verbose)
                    if print_info:
                        print(f'IOC("{self.name}").get_src_file: overwrite "{item}".')
            elif item.endswith(PROTO_SUFFIX):
                if item not in proto_list:
                    proto_list += f'{item}, '
                    if src_p != self.src_path:
                        file_copy(os.path.join(src_p, item), os.path.join(self.src_path, item), 'r', self.verbose)
                        if print_info:
                            print(f'IOC("{self.name}").get_src_file: add "{item}".')
                else:
                    if src_p != self.src_path:
                        file_copy(os.path.join(src_p, item), os.path.join(self.src_path, item), 'r', self.verbose)
                    if print_info:
                        print(f'IOC("{self.name}").get_src_file: overwrite "{item}".')
            elif item.endswith(OTHER_SUFFIX):
                if item not in other_list:
                    other_list += f'{item}, '
                    if src_p != self.src_path:
                        file_copy(os.path.join(src_p, item), os.path.join(self.src_path, item), 'r', self.verbose)
                        if print_info:
                            print(f'IOC("{self.name}").get_src_file: add "{item}".')
                else:
                    if src_p != self.src_path:
                        file_copy(os.path.join(src_p, item), os.path.join(self.src_path, item), 'r', self.verbose)
                    if print_info:
                        print(f'IOC("{self.name}").get_src_file: overwrite "{item}".')

        # Update the settings.
        db_list = db_list.rstrip(', ')
        proto_list = proto_list.rstrip(', ')
        other_list = other_list.rstrip(', ')
        if db_list:
            self.set_config('db_file', db_list, 'SRC')
            if self.verbose:
                print(f'IOC("{self.name}").get_src_file: get db files "{db_list}".')
        if proto_list:
            self.set_config('protocol_file', proto_list, 'SRC')
            if self.verbose:
                print(f'IOC("{self.name}").get_src_file: get protocol files "{proto_list}".')
        if other_list:
            self.set_config('other_file', other_list, 'SRC')
            if self.verbose:
                print(f'IOC("{self.name}").get_src_file: get other files "{other_list}".')
        if any((db_list, proto_list, other_list)):
            self.write_config()

    # Generate .substitutions file for st.cmd to load.
    # This function should be called after getting source files and setting the load options.
    def generate_substitution_file(self):
        lines_to_add = []
        for load_line in multi_line_parse(self.get_config('load', 'DB')):
            db_file, *conditions = load_line.split(',')
            # print(conditions)
            db_file = db_file.strip()
            if db_file not in os.listdir(self.src_path):
                state_info = 'db file not found.'
                prompt = f'db file "{db_file}" not found.'
                self.state_manager.set_state_info(state=STATE_WARNING, state_info=state_info, prompt=prompt)
                print(f'IOC("{self.name}").generate_substitution_file: Failed. DB file "{db_file}" not found in '
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
                    state_info = 'bad load string definition.'
                    prompt = f'in "{load_line}".'
                    self.state_manager.set_state_info(state=STATE_WARNING, state_info=state_info, prompt=prompt)
                    print(f'IOC("{self.name}").generate_substitution_file: Failed. Bad load string '
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
                if self.verbose:
                    print(f'IOC("{self.name}").generate_substitution_file: File "{self.name}.substitutions" exists, '
                          f'firstly remove it before writing a new one.')
                file_remove(file_path, self.verbose)
            try:
                with open(file_path, 'w') as f:
                    f.writelines(lines_to_add)
            except Exception as e:
                state_info = 'substitutions file generating failed.'
                self.state_manager.set_state_info(state=STATE_WARNING, state_info=state_info)
                print(f'IOC("{self.name}").generate_substitution_file: Failed. '
                      f'Exception "{e}" occurs while trying to write "{self.name}.substitutions" file.')
                return False
            # set readonly permission.
            os.chmod(file_path, 0o444)
            print(f'IOC("{self.name}").generate_substitution_file: Success. "{self.name}.substitutions" created.')
            return True
        else:
            state_info = 'empty load string definition.'
            self.state_manager.set_state_info(state=STATE_WARNING, state_info=state_info)
            print(f'IOC("{self.name}").generate_substitution_file: Failed. '
                  f'At least one load string should be defined to generate "{self.name}.substitutions".')
            return False

    # Generate all startup files for running an IOC project.
    # This function should be called after that generate_check is passed.
    def generate_startup_files(self):
        if not self.generate_check():
            print(f'IOC("{self.name}").generate_st_cmd": Failed. Checks failed before generating startup files.')
            return
        else:
            if self.verbose:
                print(f'IOC("{self.name}").generate_st_cmd: Start generating startup files.')

        lines_before_dbload = []
        lines_at_dbload = [f'cd {self.startup_path_in_docker}\n',
                           f'dbLoadTemplate "db/{self.name}.substitutions"\n', ]
        lines_after_iocinit = ['\niocInit\n\n']

        if self.verbose:
            print(f'IOC("{self.name}").generate_st_cmd": Setting "module: {self.get_config("module")}" '
                  f'will be used to generate startup files.')

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
                f'epicsEnvSet SAVE_DIR {self.log_path_in_docker}/autosave\n',
                'set_requestfile_path("$(REQ_DIR)")\n',
                'set_savefile_path("$(SAVE_DIR)")\n',
                f'set_pass0_restoreFile("${self.name}-automake-pass0.sav")\n',
                f'set_pass1_restoreFile("${self.name}-automake.sav")\n',
                'save_restoreSet_DatedBackupFiles(1)\n',
                'save_restoreSet_NumSeqFiles(3)\n',
                'save_restoreSet_SeqPeriodInSeconds(600)\n',
                'save_restoreSet_RetrySeconds(60)\n',
                'save_restoreSet_CallbackTimeout(-1)\n',
                '\n',
            ]
            lines_before_dbload.extend(temp)
            # st.cmd
            # lines after iocinit
            temp = [
                '#autosave after iocInit\n',
                f'makeAutosaveFileFromDbInfo("$(REQ_DIR)/${self.name}-automake-pass0.req","autosaveFields_pass0")\n',
                f'makeAutosaveFileFromDbInfo("$(REQ_DIR)/${self.name}-automake.req","autosaveFields")\n',
                f'create_monitor_set("${self.name}-automake-pass0.req",10)\n',
                f'create_monitor_set("${self.name}-automake.req",10)\n',
                '\n',
            ]
            lines_after_iocinit.extend(temp)
            # create log dir and request file dir
            try_makedirs(os.path.join(self.log_path, 'autosave'), self.verbose)
            try_makedirs(os.path.join(self.settings_path, 'autosave'), self.verbose)

        # caputlog configurations.
        if self.check_config('module', 'caputlog'):
            # st.cmd
            # lines_before_dbload
            temp = [
                f'#caPutLog\n',
                f'asSetFilename("{self.settings_path_in_docker}/{self.name}.acf")\n',
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
            # try_makedirs(self.settings_path, self.verbose)  # shutil.copy不会递归创建不存在的文件夹
            file_path = os.path.join(self.settings_path, f'{self.name}.acf')
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

        # asyn configurations.
        if self.conf.has_section('ASYN'):
            sc = 'ASYN'
            # st.cmd
            # lines_before_dbload
            temp = [
                '#asyn\n',
                f'{self.get_config("port_config", sc)}\n',
                f'{self.get_config("asyn_option", sc)}\n',
                '\n',
            ]
            lines_before_dbload.extend(temp)
            # lines_at_dbload
            lines_at_dbload.append(f'{self.get_config("load", sc)}\n')
            # add asynRecord.db
            file_path = os.path.join(self.db_path, 'asynRecord.db')
            template_file_path = os.path.join(DB_TEMPLATE_PATH, 'asynRecord.db')
            file_copy(template_file_path, file_path, 'r', self.verbose)

        # StreamDevice configurations.
        if self.conf.has_section('STREAM'):
            sc = 'STREAM'
            # st.cmd
            # lines_before_dbload
            temp = [
                '#StreamDevice\n',
                f'epicsEnvSet("STREAM_PROTOCOL_PATH", {self.settings_path_in_docker})\n',
                f'{self.get_config("port_config", sc)}\n',
                f'{self.get_config("asyn_option", sc)}\n',
                '\n',
            ]
            lines_before_dbload.extend(temp)
            # protocol file
            ps = self.get_config('protocol_file', sc).split(',')
            for item in ps:
                item = item.strip()
                # add .proto file
                file_copy(os.path.join(self.src_path, item), os.path.join(self.settings_path, item), 'r', self.verbose)

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
                    src = os.path.join(self.src_path, src)
                else:  # src.startswith('template/') guaranteed by generate_check()
                    src = os.path.join(self.template_path, src)
                dest = os.path.join(self.project_path, dest)
                file_copy(src, dest, mode, self.verbose)

        # write report code at the end of st.cmd file if defined "report_info: true".
        if self.check_config('report_info', 'true', 'SETTING'):
            report_path = os.path.join(CONTAINER_IOC_RUN_PATH, LOG_FILE_DIR, f"{self.name}.info")
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
        if not self.generate_substitution_file():
            print(f'IOC("{self.name}").generate_st_cmd": Failed. Generate .substitutions file failed.')
            state_info = 'generate substitutions file failed.'
            self.state_manager.set_state_info(state=STATE_WARNING, state_info=state_info)
            return

        # write st.cmd file.
        file_path = os.path.join(self.boot_path, 'st.cmd')
        if os.path.exists(file_path):
            if self.verbose:
                print(f'IOC("{self.name}").generate_st_cmd: File "{self.name}.substitutions" exists, '
                      f'firstly remove it before writing a new one.')
            file_remove(file_path, self.verbose)
        try:
            with open(file_path, 'w') as f:
                f.writelines(lines_before_dbload)
                f.writelines(lines_at_dbload)
                f.writelines(lines_after_iocinit)
        except Exception as e:
            print(f'IOC("{self.name}").generate_st_cmd: Failed. '
                  f'Exception "{e}" occurs while trying to write st.cmd file.')
            state_info = 'write st.cmd file failed.'
            self.state_manager.set_state_info(state=STATE_WARNING, state_info=state_info)
            return
        # set readable and executable permission.
        os.chmod(file_path, 0o555)
        if self.verbose:
            print(f'IOC("{self.name}").generate_st_cmd: Successfully create "st.cmd" file.')

        # set status: generated and save self.conf to ioc.ini file
        self.state_manager.set_config('status', 'generated')
        self.state_manager.set_config('state', 'normal')
        self.state_manager.set_config('state_info', '')
        self.state_manager.write_config()
        # add snapshot files
        self.add_snapshot_files()
        print(f'IOC("{self.name}").generate_st_cmd": Success. Generating startup files finished.')

    # Copy IOC startup files to mount dir for running in container.
    # force_overwrite: "True" will overwrite all files, "False" only files that are not generated during running.
    def export_for_mount(self, force_overwrite=False):
        if not self.state_manager.check_config('state', 'normal'):
            print(f'IOC("{self.name}").export_for_mount: Failed for "{self.name}", '
                  f'exporting operation must under "normal" state.')
            return
        if not (self.state_manager.check_config('status', 'generated') or
                self.state_manager.check_config('status', 'exported')):
            print(f'IOC("{self.name}").export_for_mount: Failed for "{self.name}", '
                  f'startup files should be generated before exporting.')
            return

        container_name = self.name
        host_name = self.get_config('host')
        if not host_name:
            host_name = SWARM_DIR

        top_path = os.path.join(MOUNT_PATH, host_name, container_name)
        if not os.path.isdir(top_path):
            file_to_copy = (IOC_CONFIG_FILE,)
            dir_to_copy = ('settings', 'log', 'startup',)
            exec_type = 'created'
        elif os.path.isdir(top_path) and force_overwrite:
            file_to_copy = (IOC_CONFIG_FILE,)
            dir_to_copy = ('settings', 'log', 'startup',)
            exec_type = 'overwritten'
        else:
            file_to_copy = (IOC_CONFIG_FILE,)
            dir_to_copy = ('startup',)
            exec_type = 'updated'

        for item_file in file_to_copy:
            file_copy(os.path.join(self.dir_path, item_file), os.path.join(top_path, item_file),
                      verbose=self.verbose)
            os.chmod(os.path.join(top_path, item_file), mode=0o444)  # set readonly permission.
        for item_dir in dir_to_copy:
            if not dir_copy(os.path.join(self.project_path, item_dir), os.path.join(top_path, item_dir),
                            self.verbose):
                print(f'IOC("{self.name}").export_for_mount: Failed. '
                      f'You may run this command again with "-v" option to see '
                      f'what happened for IOC "{self.name}" in details.')
                return
        else:
            print(f'IOC("{self.name}").export_for_mount: Success. IOC "{self.name}" {exec_type} in {top_path}.')

        self.state_manager.set_config('status', 'exported')
        self.state_manager.set_config('is_exported', 'true')
        self.state_manager.write_config()

    # return whether the files are in consistent with snapshot files.
    def check_snapshot_files(self, print_info=False):
        if not self.state_manager.check_config('snapshot', 'tracked'):
            if self.verbose:
                print(f'IOC("{self.name}").check_snapshot_files: '
                      f'Failed, can\'t check snapshot files as project is not in "tracked" state.')
            return False, 'unchecked', 'unchecked'
        if self.verbose or print_info:
            print(f'IOC("{self.name}").check_snapshot_files: '
                  f'Start checking snapshot files.')

        consistent_flag = True
        config_file_check_res = ''
        source_file_check_res = ''
        # check config snapshot file.
        if os.path.isfile(self.config_snapshot_file):
            if os.path.isfile(self.config_file_path):
                compare_res = filecmp.cmp(self.config_snapshot_file, self.config_file_path)
                if not compare_res:
                    consistent_flag = False
                    config_file_check_res = 'config file changed.'
            else:
                consistent_flag = False
                config_file_check_res = 'config file lost.'
                state_info = config_file_check_res
                self.state_manager.set_state_info(state=STATE_ERROR, state_info=state_info)
        else:
            consistent_flag = False
            self.state_manager.set_config('snapshot', 'error')
            self.state_manager.write_config()
            config_file_check_res = 'config file snapshot lost.'
        # check source snapshot files.
        if os.path.isdir(self.src_snapshot_path):
            if not os.path.isdir(self.src_path):
                consistent_flag = False
                self.state_manager.set_config('state', 'error')
                self.state_manager.write_config()
                source_file_check_res = 'source directory lost.'
            else:
                src_compare_res = filecmp.dircmp(self.src_snapshot_path, self.src_path)
                if src_compare_res.diff_files:
                    consistent_flag = False
                    source_file_check_res += 'changed files: '
                    for item in src_compare_res.diff_files:
                        source_file_check_res += f'{item}, '
                    else:
                        source_file_check_res = source_file_check_res.rstrip(', ')
                        source_file_check_res += '.\n'
                if src_compare_res.left_only:
                    consistent_flag = False
                    source_file_check_res += 'missing files and directories: '
                    for item in src_compare_res.left_only:
                        source_file_check_res += f'{item}, '
                    else:
                        source_file_check_res = source_file_check_res.rstrip(', ')
                        source_file_check_res += '.\n'
                if src_compare_res.right_only:
                    consistent_flag = False
                    source_file_check_res += 'untracked files and directories: '
                    for item in src_compare_res.right_only:
                        source_file_check_res += f'{item}, '
                    else:
                        source_file_check_res = source_file_check_res.rstrip(', ')
                        source_file_check_res += '.\n'
                source_file_check_res = source_file_check_res.rstrip('\n')
        else:
            consistent_flag = False
            self.state_manager.set_config('snapshot', 'error')
            self.state_manager.write_config()
            config_file_check_res = 'source directory snapshot lost.'
        if not consistent_flag and print_info:
            prefix_str = ''
            if config_file_check_res and source_file_check_res:
                config_file_check_print = f'1: \n{config_file_check_res}\n'
                source_file_check_print = f'2: \n{source_file_check_res}'
            else:
                config_file_check_print = config_file_check_res
                source_file_check_print = source_file_check_res
            print(f'IOC("{self.name}").check_snapshot_files: Inconsistency with snapshot files found: \n'
                  f'{prefix_str}'
                  f'{config_file_check_print}'
                  f'{source_file_check_print}'
                  f'\n')
        return consistent_flag, config_file_check_res, source_file_check_res

    def add_snapshot_files(self):
        if self.verbose:
            print(f'IOC("{self.name}").add_snapshot_file: Starting to add snapshot files.')
        self.delete_snapshot_files()
        # snapshot for config file.
        if os.path.isfile(self.config_file_path):
            if file_copy(self.config_file_path, self.config_snapshot_file, 'r', self.verbose):
                if self.verbose:
                    print(f'IOC("{self.name}").add_snapshot_file: Snapshot file for config successfully created.')
            else:
                print(f'IOC("{self.name}").add_snapshot_file: Failed, snapshot file for config created failed.')
                self.state_manager.set_config('snapshot', 'error')
                self.state_manager.write_config()
                return False
        else:
            print(f'IOC("{self.name}").add_snapshot_file: Failed, source file "{self.config_file_path}" not exist.')
            self.state_manager.set_config('snapshot', 'error')
            self.state_manager.write_config()
            return False
        # snapshot for source files.
        for item in os.listdir(self.src_path):
            if file_copy(os.path.join(self.src_path, item), os.path.join(self.src_snapshot_path, item), 'r',
                         self.verbose):
                if self.verbose:
                    print(f'IOC("{self.name}").add_snapshot_file: Snapshot file '
                          f'"{os.path.join(self.src_snapshot_path, item)}" successfully created.')
            else:
                print(f'IOC("{self.name}").add_snapshot_file: Failed, snapshot file '
                      f'"{os.path.join(self.src_snapshot_path, item)}" created failed.')
                self.state_manager.set_config('snapshot', 'error')
                self.state_manager.write_config()
                return False

        if self.verbose:
            print(f'IOC("{self.name}").add_snapshot_file: Snapshot for source files successfully created.')
        self.state_manager.set_config('snapshot', 'tracked')
        self.state_manager.write_config()
        return True

    def delete_snapshot_files(self):
        if os.path.isdir(self.snapshot_path):
            dir_remove(self.snapshot_path, self.verbose)
            self.state_manager.set_config('snapshot', 'untracked')
            self.state_manager.write_config()
        else:
            if self.verbose:
                print(f'IOC("{self.name}").delete_snapshot_file: Failed, path "{self.snapshot_path}" not exist.')

    def restore_from_snapshot_files(self, restore_files: list, force_restore=False):
        if self.state_manager.check_config('snapshot', 'untracked'):
            print(f'IOC("{self.name}").restore_from_snapshot_file: '
                  f'Failed, can\'t restore snapshot files in "untracked" state.')
            return
        if not isinstance(restore_files, list) or not restore_files:
            print(f'IOC("{self.name}").restore_from_snapshot_file: '
                  f'Failed, input arg "restore_files" must be a non-empty list.')
            return
        files_to_restore = {'config': '', 'src': []}
        files_provided = {'config': '', 'src': []}
        unsupported_items = []
        if os.path.isfile(self.config_snapshot_file):
            files_provided['config'] = self.config_snapshot_file
        for item in os.listdir(self.src_snapshot_path):
            files_provided['src'].append(os.path.join(self.src_snapshot_path, item))
        if 'all' in restore_files:
            files_to_restore = files_provided
        else:
            if 'ioc.ini' in restore_files:
                restore_files.remove('ioc.ini')
                files_to_restore['config'] = files_provided['config']
                if not files_to_restore['config']:
                    unsupported_items.append('ioc.ini')
            for item in restore_files:
                item_path = os.path.join(self.src_snapshot_path, item)
                if item_path in files_provided:
                    files_to_restore['src'].append(item_path)
                else:
                    unsupported_items.append(item)

        file_string = ''
        if files_to_restore['config']:
            file_string += f"{files_to_restore['config']} "
        for item in files_to_restore['src']:
            file_string += f"{item} "
        file_string = file_string.rstrip()
        if not file_string:
            print(f'IOC("{self.name}").restore_from_snapshot_file: '
                  f'Failed to Restore any snapshot files from {restore_files}, as they are not exist.')
        else:
            if not force_restore:
                while not force_restore:
                    print(f'IOC("{self.name}").restore_from_snapshot_file: Restoring snapshot files.\n'
                          f'{file_string} will be restored.')
                    if unsupported_items:
                        print(f'{unsupported_items} can\'t be restored as they are not exist.')
                    ans = input(f'Confirm to continue?[y|n]:')
                    if ans.lower() == 'n' or ans.lower() == 'no':
                        print(f'IOC("{self.name}").restore_from_snapshot_file": Restoring canceled.')
                        return
                    if ans.lower() == 'y' or ans.lower() == 'yes':
                        print(f'IOC("{self.name}").restore_from_snapshot_file": Executing restoring.')
                        force_restore = True
                        break
                    print('Invalid input, please try again.')
            if force_restore:
                if files_to_restore['config']:
                    if not file_copy(files_to_restore['config'], self.dir_path, mode='rw', verbose=self.verbose):
                        print(f'IOC("{self.name}").restore_from_snapshot_file": '
                              f'Restoring {files_to_restore["config"]} failed.')
                    else:
                        if self.verbose:
                            print(f'IOC("{self.name}").restore_from_snapshot_file": '
                                  f'Restoring {files_to_restore["config"]} succeed.')
                for item in files_to_restore['src']:
                    if not file_copy(item, self.src_path, mode='rw', verbose=self.verbose):
                        print(f'IOC("{self.name}").restore_from_snapshot_file": '
                              f'Restoring {item} failed.')
                    else:
                        if self.verbose:
                            print(f'IOC("{self.name}").restore_from_snapshot_file": '
                                  f'Restoring {item} succeed.')

    # Checks before generating the IOC project startup files.
    def generate_check(self):
        check_flag = True

        # Check whether IOC executable binary is specified.
        sc = "IOC"
        if not self.get_config('bin'):
            print(f'IOC("{self.name}").generate_st_cmd": Failed. No executable IOC specified.')
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
                if not (src.startswith('src/') or src.startswith('template/')):
                    state_info = f'option "file_copy" in section "{sc}" invalid.'
                    prompt = f'in "{item}". only "src/" or "template/" directory is supported for file_copy.'
                    self.state_manager.set_state_info(state=STATE_WARNING, state_info=state_info, prompt=prompt)
                    check_flag = False

        return check_flag

    # Check differences between snapshot file and running settings file.
    # Check differences between project files and running files.
    def check_consistency(self, print_info=False):
        if not self.check_config('is_exported', 'true'):
            if self.verbose:
                print(f'IOC("{self.name}").check_consistency: '
                      f'Failed, can\'t check consistency as project is not in "exported" state.')
            return False, "Project not exported."
        if not os.path.isfile(self.config_snapshot_file):
            if self.verbose:
                print(f'IOC("{self.name}").check_consistency: '
                      f'Failed, can\'t check consistency as config snapshot file lost.')
            return False, "Config snapshot file lost."
        if not os.path.isfile(self.config_file_path_for_mount):
            if self.verbose:
                print(f'IOC("{self.name}").check_consistency: '
                      f'Failed, can\'t check consistency as config file in mount dir lost.')
            return False, "Differences detected."

        if self.verbose or print_info:
            print(f'IOC("{self.name}").check_consistency: '
                  f'Start checking consistency.')

        consistent_flag = True
        check_res = 'Consistency checked.'

        files_to_compare = (
            (self.config_snapshot_file, self.config_file_path_for_mount),
        )
        dirs_to_compare = (
            (self.settings_path, os.path.join(self.dir_path_for_mount, 'settings')),
            (self.startup_path, os.path.join(self.dir_path_for_mount, 'startup')),
        )
        for item in files_to_compare:
            if print_info:
                print(f'diff {item[0]} {item[1]}')
            compare_res = filecmp.cmp(item[0], item[1])
            if not compare_res:
                consistent_flag = False
                check_res = 'Differences detected.'
                if print_info:
                    print('changed files: "ioc.ini".\n')
            if print_info:
                print()
        for item in dirs_to_compare:
            if dir_compare(item[0], item[1], print_info=print_info):
                consistent_flag = False
                check_res = 'Differences detected.'
        return consistent_flag, check_res

    # Checks for IOC projects.
    def project_check(self, print_info=False):
        print(f'---------------------------------------------')
        consistent_flag, temp, _ = self.check_snapshot_files(print_info=print_info)
        if consistent_flag:
            print(f'IOC("{self.name}").project_check: snapshot consistency OK.')
        else:
            if temp == 'unchecked':
                print(f'IOC("{self.name}").project_check: '
                      f'can\'t check snapshot consistency as project is not tracked by snapshot.')
            else:
                print(f'IOC("{self.name}").project_check: snapshot inconsistency found!')
        consistent_flag, _ = self.check_consistency(print_info=print_info)
        if consistent_flag:
            print(f'IOC("{self.name}").project_check: running file consistency OK.')
        else:
            print(f'IOC("{self.name}").project_check: running file inconsistency found!')

    def try_repair(self):
        self.make_directory_structure()
