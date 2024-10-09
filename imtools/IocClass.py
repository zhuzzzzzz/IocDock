import os
import configparser
import sys

from .IMFuncsAndConst import try_makedirs, file_remove, dir_remove, file_copy, condition_parse, multi_line_parse, \
    format_normalize, relative_and_absolute_path_to_abs, get_manager_path, MOUNT_DIR
from .IMFuncsAndConst import CONFIG_FILE_NAME, REPOSITORY_DIR, CONTAINER_IOC_PATH, CONTAINER_IOC_RUN_PATH, \
    DEFAULT_IOC, MODULES_PROVIDED, DEFAULT_MODULES, PORT_SUPPORT, DB_SUFFIX, PROTO_SUFFIX, OTHER_SUFFIX, LOG_FILE_DIR, \
    TOOLS_DIR, SNAPSHOT_PATH


class IOC:
    def __init__(self, dir_path=None, verbose=False, **kwargs):

        # self.dir_path
        # self.config_file_path
        # self.settings_path
        # self.log_path
        # self.startup_path
        # self.db_path
        # self.boot_path
        # self.src_path
        # self.template_path
        # self.settings_path_in_docker
        # self.log_path_in_docker
        # self.startup_path_in_docker

        self.verbose = verbose

        if not dir_path or not os.path.isdir(dir_path):
            self.dir_path = os.path.join(get_manager_path(), REPOSITORY_DIR, 'default')
            print(f'IOC.__init__: No path given or wrong path given, use default path: "{self.dir_path}".')
        self.dir_path = os.path.normpath(dir_path)
        try_makedirs(self.dir_path, self.verbose)
        self.config_file_path = os.path.join(self.dir_path, CONFIG_FILE_NAME)

        self.conf = None
        if not self.read_config():
            if self.verbose:
                print(f'IOC.__init__": Initialize a new file "{self.config_file_path}" with default settings.')
            self.set_config('name', os.path.basename(self.dir_path))
            self.set_config('host', '')
            self.set_config('image', '')
            self.set_config('bin', '')
            self.set_config('module', 'autosave, caputlog')
            self.set_config('description', '')
            self.set_config('status', 'created')
            self.set_config('snapshot', '')
            self.set_config('is_exported', 'false')
            self.set_config('db_file', '', section='SRC')
            self.set_config('protocol_file', '', section='SRC')
            self.set_config('others_file', '', section='SRC')
            self.set_config('load', '', section='DB')
            self.add_settings_template()
        else:
            if self.verbose:
                print(f'IOC.__init__: Initialize IOC from configuration file "{self.config_file_path}".')

        self.name = self.get_config('name')
        if self.name != os.path.basename(self.dir_path):
            old_name = self.name
            self.name = os.path.basename(self.dir_path)
            self.set_config('name', self.name)
            print(f'IOC.__init__: Get wrong name "{old_name}" from configuration file "{self.config_file_path}", '
                  f'name of IOC project directory may be manually changed to "{self.name}". '
                  f'IOC name has been automatically set in configuration file to follow that change.')

        self.settings_path = os.path.join(self.dir_path, 'settings')
        try_makedirs(self.settings_path, self.verbose)
        self.log_path = os.path.join(self.dir_path, 'log')
        try_makedirs(self.log_path, self.verbose)
        self.startup_path = os.path.join(self.dir_path, 'startup')
        self.db_path = os.path.join(self.startup_path, 'db')
        try_makedirs(self.db_path, self.verbose)
        self.boot_path = os.path.join(self.startup_path, 'iocBoot')
        try_makedirs(self.boot_path, self.verbose)
        self.src_path = os.path.join(self.dir_path, 'src')
        try_makedirs(self.src_path, self.verbose)
        self.template_path = os.path.join(get_manager_path(), TOOLS_DIR, 'template')
        if not os.path.exists(self.template_path):
            print("IOC.__init__: Can't find \"template\" directory.")
        self.snapshot_file = os.path.join(SNAPSHOT_PATH, self.name)

        self.settings_path_in_docker = os.path.join(CONTAINER_IOC_RUN_PATH, self.name, 'settings')
        self.log_path_in_docker = os.path.join(CONTAINER_IOC_RUN_PATH, self.name, 'log')
        self.startup_path_in_docker = os.path.join(CONTAINER_IOC_RUN_PATH, self.name, 'startup')

        mount_dir_in_sys = os.getenv('MOUNT_PATH', os.path.join(get_manager_path(), '..', MOUNT_DIR))
        self.dir_path_for_mount = os.path.normpath(
            os.path.join(mount_dir_in_sys, self.get_config('host'), self.get_config('name')))
        self.config_file_path_for_mount = os.path.join(self.dir_path_for_mount, CONFIG_FILE_NAME)
        if not os.path.isfile(self.config_file_path_for_mount) and self.verbose:
            print(f"IOC.__init__: Can't find settings file \"{self.config_file_path_for_mount}\" in mount dir.")

        #
        #
        self.get_src_file()
        #
        self.check_snapshot_status()
        # set attributes in configure file a normalized format.
        self.normalize_config()

    def read_config(self):
        if os.path.exists(self.config_file_path):
            conf = configparser.ConfigParser()
            if conf.read(self.config_file_path):
                self.conf = conf
                return True
            else:
                self.conf = None
                if self.verbose:
                    print(f'IOC.read_config: Failed. Path "{self.config_file_path}" exists but not a valid '
                          f'configuration file.')
                return False
        else:
            self.conf = None
            if self.verbose:
                print(f'IOC.read_config: Failed. Path "{self.config_file_path}" does not exists.')
            return False

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
        self.write_config()

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
        print(f' settings of IOC "{self.name}" '.center(73, '='))
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
            self.delete_snapshot_file()
            # remove entire project
            dir_remove(self.dir_path, self.verbose)
        else:
            for item in (os.path.join(self.dir_path, 'startup'), self.settings_path, self.log_path):
                dir_remove(item, self.verbose)
            self.set_config('snapshot', 'changed')

    def add_asyn_template(self, port_type):
        sc = 'ASYN'
        if self.conf.has_section(sc) and self.check_config('port_type', port_type, sc):
            print(f'IOC("{self.name}").add_asyn_template: Failed. Section "{sc}" already exists.')
            return False
        if port_type in PORT_SUPPORT:
            if self.conf.has_section(sc):
                self.conf.remove_section(sc)
            self.set_config('port_type', port_type, section=sc)
            if port_type == 'tcp/ip':
                self.set_config('port_config', 'drvAsynIPPortConfigure("L0","192.168.0.23:4001",0,0,0)\n', section=sc)
            elif port_type == 'serial':
                self.set_config('port_config', 'drvAsynSerialPortConfigure("L0","/dev/tty.PL2303-000013FA",0,0,0)\n',
                                section=sc)
                asyn_option_str = ''
                asyn_option_str = f'{asyn_option_str}asynSetOption("L0", -1, "baud", "9600")\n'
                asyn_option_str = f'{asyn_option_str}asynSetOption("L0", -1, "bits", "8")\n'
                asyn_option_str = f'{asyn_option_str}asynSetOption("L0", -1, "parity", "none")\n'
                asyn_option_str = f'{asyn_option_str}asynSetOption("L0", -1, "stop", "1")\n'
                asyn_option_str = f'{asyn_option_str}asynSetOption("L0", -1, "clocal", "Y")\n'
                asyn_option_str = f'{asyn_option_str}asynSetOption("L0", -1, "crtscts", "Y")\n'
                self.set_config('asyn_option', asyn_option_str, section=sc)
            self.set_config('load',
                            'dbLoadRecords("db/asynRecord.db","P=xxx,R=:asyn,PORT=xxx,ADDR=xxx,IMAX=xxx,OMAX=xxx")\n',
                            section=sc)
            return True
        else:
            print(f'IOC("{self.name}").add_asyn_template: Failed. Invalid port type "{port_type}".')
            return False

    def add_stream_template(self, port_type):
        sc = 'STREAM'
        if self.conf.has_section(sc) and self.check_config('port_type', port_type, sc):
            print(f'IOC("{self.name}").add_stream_template: Failed. Section "{sc}" already exists.')
            return False
        if port_type in PORT_SUPPORT:
            if self.conf.has_section(sc):
                self.conf.remove_section(sc)
            self.set_config('port_type', port_type, section=sc)
            if port_type == 'tcp/ip':
                self.set_config('port_config', 'drvAsynIPPortConfigure("L0","192.168.0.23:4001",0,0,0)\n', section=sc)
            elif port_type == 'serial':
                self.set_config('port_config', 'drvAsynSerialPortConfigure("L0","/dev/tty.PL2303-000013FA",0,0,0)\n',
                                section=sc)
                asyn_option_str = ''
                asyn_option_str = f'{asyn_option_str}asynSetOption("L0", -1, "baud", "9600")\n'
                asyn_option_str = f'{asyn_option_str}asynSetOption("L0", -1, "bits", "8")\n'
                asyn_option_str = f'{asyn_option_str}asynSetOption("L0", -1, "parity", "none")\n'
                asyn_option_str = f'{asyn_option_str}asynSetOption("L0", -1, "stop", "1")\n'
                asyn_option_str = f'{asyn_option_str}asynSetOption("L0", -1, "clocal", "Y")\n'
                asyn_option_str = f'{asyn_option_str}asynSetOption("L0", -1, "crtscts", "Y")\n'
                self.set_config('asyn_option', asyn_option_str, section=sc)
            self.set_config('protocol_file', 'xxx.proto', section=sc)
            return True
        else:
            print(f'IOC("{self.name}").add_stream_template: Failed. Invalid port type "{port_type}".')
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

    def add_settings_template(self):
        sc = 'SETTING'
        if self.conf.has_section(sc):
            print(f'IOC("{self.name}").add_settings_template: Failed. Section "{sc}" already exists.')
            return False
        self.set_config('report_info', 'true', sc)
        self.set_config('caputlog_json', 'false', sc)
        self.set_config('epics_env', '', sc)

    # From given path copy source files and update ioc.ini settings according to file suffix specified.
    # src_p: existed path from where to get source files, absolute path or relative path, None to use IOC src path.
    def get_src_file(self, src_dir=None):
        db_suffix = DB_SUFFIX
        proto_suffix = PROTO_SUFFIX
        other_suffix = OTHER_SUFFIX
        src_p = relative_and_absolute_path_to_abs(src_dir, self.src_path)
        if not os.path.exists(src_p):
            print(f'IOC("{self.name}").get_src_file: Failed. Path provided "{src_p}" not exist.')
            return

        db_list = ''
        proto_list = ''
        other_list = ''
        # When add file from other directory, to get the files already in self.src_path first.
        if src_p != self.src_path:
            for item in os.listdir(self.src_path):
                if item.endswith(db_suffix):
                    db_list += f'{item}, '
                elif item.endswith(proto_suffix):
                    proto_list += f'{item}, '
                elif item.endswith(other_suffix):
                    other_list += f'{item}, '

        # Copy files from given path and set db file option, duplicate files will result in a warning message.
        for item in os.listdir(src_p):
            if item.endswith(db_suffix):
                if item not in db_list:
                    db_list += f'{item}, '
                    if src_p != self.src_path:
                        file_copy(os.path.join(src_p, item), os.path.join(self.src_path, item), 'r', self.verbose)
                else:
                    print(f'IOC("{self.name}").get_src_file: Warning. File "{item}" was already added, skipped. '
                          f'You\'d better to check whether the db files are conflicting.')
            elif item.endswith(proto_suffix):
                if item not in proto_list:
                    proto_list += f'{item}, '
                    if src_p != self.src_path:
                        file_copy(os.path.join(src_p, item), os.path.join(self.src_path, item), 'r', self.verbose)
                else:
                    print(f'IOC("{self.name}").get_src_file: Warning. File "{item}" was already added, skipped. '
                          f'You\'d better to check whether the .proto files are conflicting.')
            elif item.endswith(other_suffix):
                if item not in other_list:
                    other_list += f'{item}, '
                    if src_p != self.src_path:
                        file_copy(os.path.join(src_p, item), os.path.join(self.src_path, item), 'r', self.verbose)
                else:
                    print(f'IOC("{self.name}").get_src_file: Warning. File "{item}" was already added, skipped. '
                          f'You\'d better to check whether files are conflicting.')

        # Update the settings.
        db_list = db_list.rstrip(', ')
        proto_list = proto_list.rstrip(', ')
        other_list = other_list.rstrip(', ')
        if db_list:
            self.set_config('db_file', db_list, 'SRC')
            if self.verbose:
                print(f'IOC("{self.name}").get_src_file: Add db files. Set attribute "file: {db_list}".')
        else:
            if self.verbose:
                print(f'IOC("{self.name}").get_src_file: No db files found in "{src_p}".')
        if proto_list:
            self.set_config('protocol_file', proto_list, 'SRC')
            if self.verbose:
                print(f'IOC("{self.name}").get_src_file: Add protocol files "{proto_list}".')
        else:
            if self.verbose:
                print(f'IOC("{self.name}").get_src_file: No protocol files found in "{src_p}".')
        if other_list:
            self.set_config('other_file', other_list, 'SRC')
            if self.verbose:
                print(f'IOC("{self.name}").get_src_file: Add files "{other_list}".')
        else:
            if self.verbose:
                print(f'IOC("{self.name}").get_src_file: No file for given suffix {other_suffix} found in "{src_p}".')

    # Generate .substitutions file for st.cmd to load.
    # This function should be called after getting source files and setting the load options.
    def generate_substitution_file(self):
        lines_to_add = []
        for load_line in multi_line_parse(self.get_config('load', 'DB')):
            db_file, *conditions = load_line.split(',')
            # print(conditions)
            db_file = db_file.strip()
            if db_file not in os.listdir(self.src_path):
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
                    print(f'IOC("{self.name}").generate_substitution_file: Failed. Bad load string '
                          f'"{load_line}" defined in {CONFIG_FILE_NAME}. You may need to check and set the attributes correctly.')
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
                print(f'IOC("{self.name}").generate_substitution_file: Failed. '
                      f'Exception "{e}" occurs while trying to write "{self.name}.substitutions" file.')
                return False
            # set readonly permission.
            os.chmod(file_path, 0o444)
            print(f'IOC("{self.name}").generate_substitution_file: Success. "{self.name}.substitutions" created.')
            return True
        else:
            print(f'IOC("{self.name}").generate_substitution_file: Failed. '
                  f'At least one load string should be defined to generate "{self.name}.substitutions".')
            return False

    # Generate all startup files for running an IOC project.
    # This function should be called after that generate_check is passed.
    def generate_startup_files(self, force_executing=False, force_default=False):
        if not self.generate_check():
            print(f'IOC("{self.name}").generate_st_cmd": Failed. Checks failed before generating startup files.')
            return
        else:
            print(f'IOC("{self.name}").generate_st_cmd: Start generating startup files.')

        lines_before_dbload = []
        lines_at_dbload = [f'cd {self.startup_path_in_docker}\n',
                           f'dbLoadTemplate "db/{self.name}.substitutions"\n', ]
        lines_after_iocinit = ['\niocInit\n\n']

        # Question whether to use default if unspecified IOC executable binary.
        if not self.get_config('bin'):
            if force_default:
                self.set_config('bin', DEFAULT_IOC)
                if self.verbose:
                    print(f'IOC("{self.name}").generate_st_cmd": Executable IOC was set to default "{DEFAULT_IOC}".')
            else:
                if force_executing:
                    print(f'IOC("{self.name}").generate_st_cmd: Failed. No executable IOC specified.')
                    return
                while not force_executing:
                    ans = input(f'IOC("{self.name}").generate_st_cmd: Executable IOC not defined. '
                                f'Use default "{DEFAULT_IOC}" to continue?[y|n]:')
                    if ans.lower() == 'n' or ans.lower() == 'no':
                        print(f'IOC("{self.name}").generate_st_cmd": Failed. No executable IOC specified.')
                        return
                    if ans.lower() == 'y' or ans.lower() == 'yes':
                        self.set_config('bin', DEFAULT_IOC)
                        print(f'IOC("{self.name}").generate_st_cmd": Executable IOC set default to "{DEFAULT_IOC}".')
                        break
                    print('Invalid input, please try again.')

        # Question whether to use default if unspecified install modules.
        if not self.get_config('module'):
            if force_default:
                self.set_config('module', DEFAULT_MODULES)
                if self.verbose:
                    print(f'IOC("{self.name}").generate_st_cmd": Modules to be installed was set to default'
                          f' "{DEFAULT_MODULES}".')
            else:
                while not force_executing:
                    ans = input(
                        f'IOC("{self.name}").generate_st_cmd": Modules to be installed not defined. '
                        f'Use default "{DEFAULT_MODULES}" to continue?[y|n]:')
                    if ans.lower() == 'n' or ans.lower() == 'no':
                        print('Continue, no module will be installed.')
                        break
                    if ans.lower() == 'y' or ans.lower() == 'yes':
                        self.set_config('module', DEFAULT_MODULES)
                        print(f'IOC("{self.name}").generate_st_cmd": Modules to be installed was set to default'
                              f' "{DEFAULT_MODULES}".')
                        break
                    print('Invalid input, please try again.')

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
        sc = 'SETTING'
        # st.cmd
        # lines_before_dbload
        temp = ['#settings\n', ]
        for env_def in multi_line_parse(self.get_config("epics_env", sc)):
            env_name, env_val = condition_parse(env_def)
            if env_name:
                temp.append(f'epicsEnvSet("{env_name}","{env_val}")\n')
            else:
                print(env_name, env_val)
                print(f'IOC("{self.name}").generate_st_cmd: Failed. Bad environment "{env_def}" defined in SETTING '
                      f'section. You may need to check and set the attributes correctly.')
                return
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
            template_file_path = os.path.join(self.template_path, 'template.acf')
            file_copy(template_file_path, file_path, 'r', self.verbose)

        # status-ioc configurations.
        if self.check_config('module', 'status-ioc'):
            # st.cmd
            # lines_at_dbload
            lines_at_dbload.append(f'dbLoadRecords("db/status_ioc.db","IOC={self.name}")\n')
            # devIocStats .db
            file_path = os.path.join(self.db_path, 'status_ioc.db')
            template_file_path = os.path.join(self.template_path, 'db', 'status_ioc.db')
            file_copy(template_file_path, file_path, 'r', self.verbose)

        # status-os configurations.
        if self.check_config('module', 'status-os'):
            # st.cmd
            # lines_at_dbload
            lines_at_dbload.append(f'dbLoadRecords("db/status_OS.db","HOST={self.name}:docker")\n')
            # devIocStats .db
            file_path = os.path.join(self.db_path, 'status_OS.db')
            template_file_path = os.path.join(self.template_path, 'db', 'status_OS.db')
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
            template_file_path = os.path.join(self.template_path, 'db', 'asynRecord.db')
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
                if item not in os.listdir(self.src_path):
                    print(f'IOC("{self.name}").generate_st_cmd: Failed. StreamDevice protocol file "{item}" '
                          f'not found in "{self.src_path}", you need to add it then run this command again.')
                    return
                else:
                    # add .proto file
                    file_copy(os.path.join(self.src_path, item), os.path.join(self.settings_path, item), 'r',
                              self.verbose)

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
                elif len(fs) == 3:
                    src = fs[0]
                    dest = fs[1]
                    mode = fs[2]
                else:
                    print(f'IOC("{self.name}").generate_st_cmd: Warning. Invalid string "{item}" specified for '
                          f'file copy, skipped.')
                    continue
                file_copy(src, dest, mode, self.verbose)

        # write report code at the end of st.cmd file if defined "report_info: true".
        if self.check_config('report_info', 'true', 'SETTING'):
            report_path = os.path.join(CONTAINER_IOC_RUN_PATH, LOG_FILE_DIR, f"{self.name}.info")
            temp = [
                '#report info\n',
                f'system "touch {report_path}"\n',

                f'system "echo \#date > {report_path}"\n',
                f'date >> {report_path}\n',
                f'system "echo >> {report_path}"\n',

                f'system "echo \#ip >> {report_path}"\n',
                f'system "hostname -I >> {report_path}"\n',
                f'system "echo >> {report_path}"\n',

                f'system "echo \#pv list >> {report_path}"\n',
                f'dbl >> {report_path}\n',
                f'system "echo >> {report_path}"\n',

                '\n'
            ]
            lines_after_iocinit.extend(temp)

        # generate .substitutions file.
        if not self.generate_substitution_file():
            print(f'IOC("{self.name}").generate_st_cmd": Failed. Generate .substitutions file failed.')
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
            return
        # set readable and executable permission.
        os.chmod(file_path, 0o555)
        if self.verbose:
            print(f'IOC("{self.name}").generate_st_cmd: Successfully create "st.cmd" file.')

        # set status: generated and save self.conf to ioc.ini file
        self.set_config('status', 'generated')
        # add ioc.ini snapshot file
        self.add_snapshot_file()
        print(f'IOC("{self.name}").generate_st_cmd": Success. Generating startup files finished.')

    def check_snapshot_status(self):
        if not self.check_snapshot_file():
            if os.path.isfile(self.snapshot_file):
                self.set_config('snapshot', 'changed')
            else:
                self.set_config('snapshot', '')

    def add_snapshot_file(self):
        if os.path.isfile(self.config_file_path):
            if self.verbose:
                print(f'IOC("{self.name}").add_snapshot_file: Starting to add snapshot file.')
            temp_config = self.get_config('snapshot')
            self.set_config('snapshot', 'logged')
            if file_copy(self.config_file_path, self.snapshot_file, 'r', self.verbose):
                if self.verbose:
                    print(f'IOC("{self.name}").add_snapshot_file: Snapshot file successfully created.')
            else:
                self.set_config('snapshot', temp_config)
                if self.verbose:
                    print(f'IOC("{self.name}").add_snapshot_file: Failed, snapshot file created failed.')
        else:
            if self.verbose:
                print(f'IOC("{self.name}").add_snapshot_file: failed, source file "{self.config_file_path}" not exist.')

    def delete_snapshot_file(self):
        if os.path.isfile(self.snapshot_file):
            file_remove(self.snapshot_file, self.verbose)
        else:
            if self.verbose:
                print(f'IOC("{self.name}").delete_snapshot_file: Failed, file "{self.snapshot_file}" not exist.')

    def check_snapshot_file(self):
        if not os.path.isfile(self.snapshot_file):
            return False
        else:
            with open(self.config_file_path, 'r') as f1, open(self.snapshot_file, 'r') as f2:
                lines1 = f1.readlines()
                lines2 = f2.readlines()
                return lines1 == lines2

    def restore_snapshot_file(self, force_restore=False):
        if not os.path.isfile(self.snapshot_file):
            print(f'IOC("{self.name}").restore_snapshot_file: Failed, snapshot file not found. ')
            return
        conf_snap = configparser.ConfigParser()
        if not conf_snap.read(self.snapshot_file):
            print(f'IOC("{self.name}").restore_snapshot_file: Failed, invalid snapshot file. ')
            return
        if not force_restore:
            ans = input(f'IOC("{self.name}").restore_snapshot_file: Confirm to restore snapshot settings file?[y|n]:')
            if ans.lower() == 'yes' or ans.lower() == 'y':
                force_restore = True
                print(f'IOC("{self.name}").restore_snapshot_file: Restoring.')
            elif ans.lower() == 'no' or ans.lower() == 'n':
                print(f'IOC("{self.name}").restore_snapshot_file: Choose to give up restoring.')
            else:
                print(f'IOC("{self.name}").restore_snapshot_file: Wong input, restoring exit.')
        if force_restore:
            self.conf = conf_snap
            self.write_config()
            self.check_snapshot_status()
            print(f'IOC("{self.name}").restore_snapshot_file: Restoring finished.')


    # Checks before generating the IOC project startup file.
    def generate_check(self):
        check_flag = True

        # Check whether modules to be installed was set correctly.
        module_list = self.get_config('module').strip().split(',')
        for s in module_list:
            if s == '':
                continue
            else:
                if s.strip().lower() not in MODULES_PROVIDED:
                    print(f'IOC("{self.name}").generate_check: Failed. Invalid module "{s}" '
                          f'set in option "module", please check and reset the settings correctly.')
                    check_flag = False

        # Check that asyn and stream not exist at the same time.
        if self.conf.has_section('ASYN') and self.conf.has_section('STREAM'):
            print(f'IOC("{self.name}").generate_check: Failed. ASYN and StreamDevice '
                  f'should set in one IOC project simultaneously, please check and reset the settings correctly.')
            check_flag = False

        # Check whether section ASYN was set correctly.(now only check port type and other settings are not empty.)
        if self.conf.has_section('ASYN'):
            sc = 'ASYN'
            if self.get_config('port_type', sc) not in PORT_SUPPORT:
                print(f'IOC("{self.name}").generate_check": Failed. Invalid option '
                      f'"port_type" in section "{sc}", please check and reset the settings correctly.')
                check_flag = False
            if self.get_config('port_config', sc) == '':
                print(f'IOC("{self.name}").generate_check: Failed. Empty option "port_config" detected in section '
                      f'"{sc}", please check and reset the settings correctly.')
                check_flag = False
            if self.check_config('port_type', 'serial', sc) and self.get_config('asyn_option', sc) == '':
                print(f'IOC("{self.name}").generate_check: Failed. Empty option "asyn_option" detected in section '
                      f'"{sc}", please check and reset the settings correctly.')
                check_flag = False
            if self.get_config('load', sc) == '':
                print(f'IOC("{self.name}").generate_check: Failed. Empty option "load" detected in section '
                      f'"{sc}", please check and reset the settings correctly.')
                check_flag = False

        # check whether section STREAM was set correctly.(now only check port type and other settings are not empty.)
        if self.conf.has_section('STREAM'):
            sc = 'STREAM'
            if self.get_config('port_type', sc) not in PORT_SUPPORT:
                print(f'IOC("{self.name}").generate_check: Failed. Invalid option '
                      f'"port_type" in section "{sc}", please check and reset the settings correctly.')
                check_flag = False
            if self.get_config('protocol_file', sc) == '':
                print(f'IOC("{self.name}").generate_check: Failed. Empty option "protocol_file" detected in '
                      f'section "{sc}", please check and reset the settings correctly.')
                check_flag = False
            if self.get_config('port_config', sc) == '':
                print(f'IOC("{self.name}").generate_check: Failed. Empty option "port_config" detected in section '
                      f'"{sc}", please check and reset the settings correctly.')
                check_flag = False
            if self.check_config('port_type', 'serial', sc) and self.get_config('asyn_option', sc) == '':
                print(f'IOC("{self.name}").generate_check: Failed. Empty option "asyn_option" detected in '
                      f' section "{sc}", please check and reset the settings correctly.')
                check_flag = False

        return check_flag

    # Checks differences between snapshot file and running settings file.
    def check_consistency(self, print_info=False):
        if not self.check_config('is_exported', 'true'):
            return False, "Project not exported. "
        if not os.path.isfile(self.snapshot_file):
            return False, "Snapshot file not found. "
        conf_snap = configparser.ConfigParser()
        if not conf_snap.read(self.snapshot_file):
            return False, "Invalid snapshot file. "
        # Check whether settings file in mount dir is consistent with the one in repository.
        if os.path.isfile(self.config_file_path_for_mount):
            conf_run = configparser.ConfigParser()
            if not conf_run.read(self.config_file_path_for_mount):
                return False, "Invalid running settings file. "
            else:
                # sections comparing
                if set(conf_run.sections()).issubset(set(conf_snap.sections())):
                    if not set(conf_snap.sections()).issubset(set(conf_run.sections())):
                        return False, "New settings available. "
                else:
                    return False, "Deprecated settings detected. "
                # options comparing
                fine_flag = True
                for section in conf_run.sections():
                    if section == 'SRC':
                        continue
                    if set(conf_run[section].keys()).issubset(set(conf_snap[section].keys())):
                        for key in conf_run[section]:
                            if conf_run[section][key] != conf_snap[section][key]:
                                fine_flag = False
                                if print_info:
                                    print(f'Inconsistent settings detected for "{self.name}". '
                                          f'"{key}[{section}]": "{conf_run[section][key]}" in running settings while '
                                          f'"{key}[{section}]": "{conf_snap[section][key]}" in snapshot settings.')
                        else:
                            if not set(conf_snap[section].keys()).issubset(set(conf_run[section].keys())):
                                fine_flag = False
                                if print_info:
                                    print(f'New options to apply for "{self.name}" in section [{section}]: '
                                          f'{set(conf_run[section].keys()).difference(set(conf_snap[section].keys()))}. ')
                    else:
                        fine_flag = False
                        if print_info:
                            print(f'Inconsistent options detected for "{self.name}" in section [{section}]: '
                                  f'{set(conf_run[section].keys()).difference(set(conf_snap[section].keys()))}')
                else:
                    if fine_flag:
                        return True, "Fine."
                    else:
                        return False, "Inconsistent settings detected. "
        else:
            return False, "Running settings file not found. "

    # Checks for IOC projects.
    def run_check(self, print_info=True, print_prompt=False):

        # output redirect.
        with open(os.devnull, 'w') as devnull:
            original_stdout = sys.stdout
            original_stderr = sys.stderr
            sys.stdout = devnull
            sys.stderr = devnull
            if print_info:
                sys.stdout = original_stdout
                sys.stderr = original_stderr
            #####
            # checks that give prompt for further operation.
            res_prompt = ''
            if not self.check_config('is_exported', 'true'):
                if self.check_config('status', 'created'):
                    res_prompt = (f'Project just created, '
                                  f'make settings then generate startup files and export them into running dir.')
                elif self.check_config('status', 'generated'):
                    if self.check_config('snapshot', 'logged'):
                        res_prompt = f'Project just generated, now you can export them into running dir.'
                    elif self.check_config('snapshot', 'changed'):
                        res_prompt = (f'Settings has been changed but not generated. Generate startup files again to '
                                      f'apply new settings or just restore old settings from snapshot file.')
                elif self.check_config('status', 'restored'):
                    res_prompt = (f'Project just restored, make settings then generate startup files and '
                                  f'export them into running dir.')
                if print_prompt:
                    print(f'IOC("{self.name}").run_check: {res_prompt}')
            else:
                if self.check_config('snapshot', ''):
                    res_prompt = (f'Snapshot file not found, project may be just restored, '
                                  f'please generate startup file to make snapshot files.')
                    print(f'IOC("{self.name}").run_check: Warning. {res_prompt}')
                elif self.check_config('snapshot', 'changed'):
                    res_prompt = (f'Settings has been changed, generate startup files again to make snapshot file for '
                                  f'new settings or just restore old settings from snapshot file.')
                    print(f'IOC("{self.name}").run_check: Warning. {res_prompt}')
                elif self.check_config('snapshot', 'logged'):
                    if print_prompt:
                        res, prompt_info = self.check_consistency(print_info=True)
                    else:
                        res, prompt_info = self.check_consistency()
                    if not res:
                        res_prompt = (f'Settings are not consistent between running settings file and snapshot file, '
                                      f'you should export startup files again.')
                        print(f'IOC("{self.name}").run_check: Warning. {res_prompt}')
                    else:
                        res_prompt = prompt_info
                        if print_prompt:
                            print(f'IOC("{self.name}").run_check: {prompt_info}')
            #####
            sys.stdout = original_stdout
            sys.stderr = original_stderr

            return res_prompt
