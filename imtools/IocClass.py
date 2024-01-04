import os
import configparser

from .IMFuncsAndConst import try_makedirs, file_remove, dir_remove, file_copy, condition_parse, format_normalize, \
    add_log_file, delete_log_file, check_log_file
from .IMFuncsAndConst import CONFIG_FILE_NAME, REPOSITORY_DIR, CONTAINER_IOC_PATH, CONTAINER_IOC_RUN_PATH, \
    DEFAULT_IOC, MODULES_PROVIDED, DEFAULT_MODULES, PORT_SUPPORT, DB_SUFFIX, PROTO_SUFFIX, OTHER_SUFFIX


class IOC:
    def __init__(self, dir_path=None, verbose=False, **kwargs):

        # self.dir_path
        # self.config_file_path
        # self.settings_path
        # self.log_path
        # self.db_path
        # self.boot_path
        # self.src_path
        # self.template_path
        # self.settings_path_in_docker
        # self.log_path_in_docker
        # self.startup_path_in_docker

        self.verbose = verbose

        if not dir_path or not os.path.isdir(dir_path):
            self.dir_path = os.path.join(os.getcwd(), REPOSITORY_DIR, 'default')
            print(f'IOC.__init__: No path given or wrong path given, init at default path: "{self.dir_path}".')
        else:
            self.dir_path = os.path.normpath(dir_path)
        try_makedirs(self.dir_path, self.verbose)
        self.config_file_path = os.path.join(self.dir_path, CONFIG_FILE_NAME)

        self.conf = None
        if not self.read_config():
            if self.verbose:
                print(f'IOC.__init__": Initialize a new file "{self.config_file_path}" with default settings.')
            self.set_config('name', os.path.basename(self.dir_path))
            self.set_config('bin', '')
            self.set_config('module', '')
            self.set_config('container', '')
            self.set_config('host', '')
            self.set_config('status', 'unready')
            self.set_config('description', '')
            self.set_config('file', '', section='DB')
        else:
            if self.verbose:
                print(f'IOC.__init__: Initialize IOC from file "{self.config_file_path}".')

        self.name = self.get_config('name')
        if self.name != os.path.basename(self.dir_path):
            old_name = self.name
            self.name = os.path.basename(self.dir_path)
            self.set_config('name', self.name)
            print(f'IOC.__init__: Get wrong name "{old_name}" from "{self.config_file_path}", there may be '
                  f'something wrong. IOC name has been automatically set same as directory name: "{self.name}".')

        self.settings_path = os.path.join(self.dir_path, 'settings')
        try_makedirs(self.settings_path, self.verbose)
        self.log_path = os.path.join(self.dir_path, 'log')
        try_makedirs(self.log_path, self.verbose)
        self.db_path = os.path.join(self.dir_path, 'startup', 'db')
        try_makedirs(self.db_path, self.verbose)
        self.boot_path = os.path.join(self.dir_path, 'startup', 'iocBoot')
        try_makedirs(self.boot_path, self.verbose)
        self.src_path = os.path.join(self.dir_path, 'src')
        try_makedirs(self.src_path, self.verbose)
        self.template_path = os.path.join(os.getcwd(), 'imtools', 'template')
        if not os.path.exists(self.template_path):
            print("IOC.__init__: Can't find template directory. You may run the scripts at a wrong path.")

        self.settings_path_in_docker = os.path.join(CONTAINER_IOC_RUN_PATH, self.name, 'settings')
        self.log_path_in_docker = os.path.join(CONTAINER_IOC_RUN_PATH, self.name, 'log')
        self.startup_path_in_docker = os.path.join(CONTAINER_IOC_RUN_PATH, self.name, 'startup')

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
        print(f' settings of "{self.name}" '.center(73, '='))
        if self.conf:
            for section in self.conf.sections():
                print(f'[{section}]')
                for key, value in self.conf.items(section):
                    print(f'{key}: {value}')
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
            delete_log_file(self.name, self.verbose)
            dir_remove(self.dir_path, self.verbose)
        else:
            for item in (os.path.join(self.dir_path, 'startup'), self.settings_path, self.log_path):
                dir_remove(item, self.verbose)
            self.set_config('status', 'unready')

    def add_asyn_template(self, port_type):
        sc = 'ASYN'
        if port_type in PORT_SUPPORT:
            self.set_config('port_type', port_type, section=sc)
            if port_type == 'tcp/ip':
                self.set_config('port_config', 'drvAsynIPPortConfigure("L0","192.168.0.23:4001",0,0,0)', section=sc)
            elif port_type == 'serial':
                self.set_config('port_config', 'drvAsynSerialPortConfigure("L0","/dev/tty.PL2303-000013FA",0,0,0)',
                                section=sc)
                self.set_config('asyn_option_a', 'asynSetOption("L0", -1, "baud", "9600")', section=sc)
                self.set_config('asyn_option_b', 'asynSetOption("L0", -1, "bits", "8")', section=sc)
                self.set_config('asyn_option_c', 'asynSetOption("L0", -1, "parity", "none")', section=sc)
                self.set_config('asyn_option_d', 'asynSetOption("L0", -1, "stop", "1")', section=sc)
                self.set_config('asyn_option_e', 'asynSetOption("L0", -1, "clocal", "Y")', section=sc)
                self.set_config('asyn_option_f', 'asynSetOption("L0", -1, "crtscts", "Y")', section=sc)
            self.set_config('load_a',
                            'dbLoadRecords("db/asynRecord.db","P=xxx,R=:asyn,PORT=xxx,ADDR=xxx,IMAX=xxx,OMAX=xxx")',
                            section=sc)
        else:
            print(f'IOC("{self.name}").add_asyn_template: Failed. Invalid port type "{port_type}".')

    def add_stream_template(self, port_type):
        sc = 'STREAM'
        if port_type in PORT_SUPPORT:
            self.set_config('port_type', port_type, section=sc)
            if port_type == 'tcp/ip':
                self.set_config('port_config', 'drvAsynIPPortConfigure("L0","192.168.0.23:4001",0,0,0)', section=sc)
            elif port_type == 'serial':
                self.set_config('port_config', 'drvAsynSerialPortConfigure("L0","/dev/tty.PL2303-000013FA",0,0,0)',
                                section=sc)
                self.set_config('asyn_option_a', 'asynSetOption("L0", -1, "baud", "9600")', section=sc)
                self.set_config('asyn_option_b', 'asynSetOption("L0", -1, "bits", "8")', section=sc)
                self.set_config('asyn_option_c', 'asynSetOption("L0", -1, "parity", "none")', section=sc)
                self.set_config('asyn_option_d', 'asynSetOption("L0", -1, "stop", "1")', section=sc)
                self.set_config('asyn_option_e', 'asynSetOption("L0", -1, "clocal", "Y")', section=sc)
                self.set_config('asyn_option_f', 'asynSetOption("L0", -1, "crtscts", "Y")', section=sc)
            self.set_config('protocol_file', 'xxx.proto', section=sc)
        else:
            print(f'IOC("{self.name}").add_stream_template: Failed. Invalid port type "{port_type}".')

    def add_raw_cmd_template(self):
        sc = 'RAW'
        self.set_config('cmd_before_dbload_a', '', sc)
        self.set_config('cmd_at_dbload_a', '', sc)
        self.set_config('cmd_after_iocinit_a', '', sc)
        self.set_config('file_copy_a', '', sc)

    def add_module_settings_template(self):
        pass

    def add_env_template(self):
        pass

    # from given path get all source files, and update ioc.ini file.
    def get_src_file(self, src_p=None):
        db_suffix = DB_SUFFIX
        proto_suffix = PROTO_SUFFIX
        other_suffix = OTHER_SUFFIX
        if not src_p:
            src_p = self.src_path
        else:
            if not os.path.isabs(src_p):
                src_p = os.path.abspath(src_p)
        if not os.path.exists(src_p):
            print(f'IOC("{self.name}").get_db_list: Failed. Provided path "{src_p}" not exists.')
            return

        db_list = ''
        proto_list = ''
        other_list = ''
        for item in os.listdir(src_p):
            if item.endswith(db_suffix):
                if item not in db_list:
                    db_list += f'{item}, '
                    if src_p != self.src_path:
                        file_copy(os.path.join(src_p, item), os.path.join(self.src_path, item), 'r', self.verbose)
                else:
                    print(f'IOC("{self.name}").get_db_list: Warning. File "{item}" was already added, skipped. '
                          f'You\'d better to check whether the db files are conflicting.')
            elif item.endswith(proto_suffix):
                if item not in proto_list:
                    proto_list += f'{item}, '
                    if src_p != self.src_path:
                        file_copy(os.path.join(src_p, item), os.path.join(self.src_path, item), 'r', self.verbose)
                else:
                    print(f'IOC("{self.name}").get_db_list: Warning. File "{item}" was already added, skipped. '
                          f'You\'d better to check whether the .proto files are conflicting.')
            elif item.endswith(other_suffix):
                if item not in other_list:
                    other_list += f'{item}, '
                    if src_p != self.src_path:
                        file_copy(os.path.join(src_p, item), os.path.join(self.src_path, item), 'r', self.verbose)
                else:
                    print(f'IOC("{self.name}").get_db_list: Warning. File "{item}" was already added, skipped. '
                          f'You\'d better to check whether the files are conflicting.')

        db_list = db_list.rstrip(', ')
        proto_list = proto_list.rstrip(', ')
        other_list = other_list.rstrip(', ')
        if db_list:
            self.set_config('file', db_list, 'DB')
            print(f'IOC("{self.name}").get_db_list: Add db files. Set attribute "file: {db_list}".')
        else:
            print(f'IOC("{self.name}").get_db_list: No db files found in "{src_p}".')
        if proto_list:
            print(f'IOC("{self.name}").get_db_list: Add protocol files "{proto_list}".')
        else:
            print(f'IOC("{self.name}").get_db_list: No protocol files found in "{src_p}".')
        if other_list:
            print(f'IOC("{self.name}").get_db_list: Add files "{other_list}".')
        else:
            print(f'IOC("{self.name}").get_db_list: No files with suffix {other_suffix} found in "{src_p}".')

    def generate_substitution_file(self):
        lines_to_add = []
        for option in self.conf.options('DB'):
            if option.startswith('load_'):
                load_string = self.conf.get('DB', option)
                dbf, *conditions = load_string.split(',')
                # print(conditions)
                dbf = dbf.strip()
                if dbf not in os.listdir(self.src_path):
                    print(f'IOC("{self.name}").generate_substitution_file: Failed. File "{dbf}" not found in '
                          f'"src/" directory. You need to add it before executing this command.')
                    return False
                else:
                    file_copy(os.path.join(self.src_path, dbf), os.path.join(self.db_path, dbf), 'r', self.verbose)
                ks = ''
                vs = ''
                for c in conditions:
                    k, v = condition_parse(c)
                    if k:
                        ks += f'{k}, '
                        vs += f'{v}, '
                    else:
                        print(f'IOC("{self.name}").generate_substitution_file: Failed. Bad condition '
                              f'"{option}: {load_string}" defined in ioc.ini. You may need to '
                              f'check and set the attributes correctly.')
                        return False
                else:
                    ks = ks.strip(', ')
                    vs = vs.strip(', ')
                lines_to_add.append(f'\nfile db/{dbf} {{\n')
                lines_to_add.append(f'    pattern {{ {ks} }}\n')
                lines_to_add.append(f'        {{ {vs} }}\n')
                lines_to_add.append(f'}}\n')
        if lines_to_add:
            # write .substitutions file.
            file_path = os.path.join(self.db_path, f'{self.name}.substitutions')
            try:
                with open(file_path, 'w') as f:
                    f.writelines(lines_to_add)
            except PermissionError as e:
                if self.verbose:
                    print(f'IOC("{self.name}").generate_substitution_file: File "{self.name}.substitutions" exists, '
                          f'firstly remove it before write a new one.')
                file_remove(file_path, self.verbose)
                with open(file_path, 'w') as f:
                    f.writelines(lines_to_add)
            # set readable and executable permission.
            os.chmod(file_path, 0o555)
            print(f'IOC("{self.name}").generate_substitution_file: Success. "{self.name}.substitutions" created.')
            return True
        else:
            print(f'IOC("{self.name}").generate_substitution_file: Failed. '
                  f'At least one "load_" option should be defined.')
            return False

    def generate_st_cmd(self, force_executing=False, force_default=False):
        if not self.generate_check():
            print(f'IOC("{self.name}").generate_st_cmd": Failed. Checks failed before generating startup files.')
            return
        else:
            print(f'IOC("{self.name}").generate_st_cmd: Start generating startup files.')

        lines_before_dbload = []
        lines_at_dbload = [f'cd {self.startup_path_in_docker}\n',
                           f'dbLoadTemplate "db/{self.name}.substitutions"\n', ]
        lines_after_iocinit = ['\niocInit\n\n']

        # question whether to use default for unspecified IOC executable binary.
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

        # question whether to use default for unspecified install modules.
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
                  f'will be implied to generate startup files.')

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

        # autosave
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
                f'makeAutosaveFileFromDbInfo("$(REQ_DIR)/${self.name}-automake-pass0.req", "autosaveFields_pass0")\n',
                f'makeAutosaveFileFromDbInfo("$(REQ_DIR)/${self.name}-automake.req", "autosaveFields")\n',
                f'create_monitor_set("${self.name}-automake-pass0.req",10)\n',
                f'create_monitor_set("${self.name}-automake.req",10)\n',
                '\n',
            ]
            lines_after_iocinit.extend(temp)
            # create log dir and request file dir
            try_makedirs(os.path.join(self.log_path, 'autosave'), self.verbose)
            try_makedirs(os.path.join(self.settings_path, 'autosave'), self.verbose)

        # caputlog
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

        # status-ioc
        if self.check_config('module', 'status-ioc'):
            # st.cmd
            # lines_at_dbload
            lines_at_dbload.append(f'dbLoadRecords("db/status_ioc.db","IOC={self.name}")\n')
            # devIocStats .db
            file_path = os.path.join(self.db_path, 'status_ioc.db')
            template_file_path = os.path.join(self.template_path, 'db', 'status_ioc.db')
            file_copy(template_file_path, file_path, 'r', self.verbose)

        # status-os
        if self.check_config('module', 'status-os'):
            # st.cmd
            # lines_at_dbload
            lines_at_dbload.append(f'dbLoadRecords("db/status_OS.db","HOST={self.name}:docker")\n')
            # devIocStats .db
            file_path = os.path.join(self.db_path, 'status_OS.db')
            template_file_path = os.path.join(self.template_path, 'db', 'status_OS.db')
            file_copy(template_file_path, file_path, 'r', self.verbose)

        # asyn
        if self.conf.has_section('ASYN'):
            sc = 'ASYN'
            # st.cmd
            # lines_before_dbload
            temp = [
                '#asyn\n',
                f'{self.get_config("port_config", sc)}\n',
            ]
            for option in self.conf.options(sc):
                if option.startswith('asyn_option_'):
                    temp.append(f'{self.get_config(option, sc)}\n')
            else:
                temp.append('\n')
            lines_before_dbload.extend(temp)
            # lines_at_dbload
            for option in self.conf.options(sc):
                if option.startswith('load_'):
                    lines_at_dbload.append(f'{self.get_config(option, sc)}\n')
            # add asynRecord.db
            file_path = os.path.join(self.db_path, 'asynRecord.db')
            template_file_path = os.path.join(self.template_path, 'db', 'asynRecord.db')
            file_copy(template_file_path, file_path, 'r', self.verbose)

        # StreamDevice
        if self.conf.has_section('STREAM'):
            sc = 'STREAM'
            # st.cmd
            # lines_before_dbload
            temp = [
                '#StreamDevice\n',
                f'epicsEnvSet("STREAM_PROTOCOL_PATH", {self.settings_path_in_docker})\n',
                f'{self.get_config("port_config", sc)}\n',
            ]
            for option in self.conf.options(sc):
                if option.startswith('asyn_option_'):
                    temp.append(f'{self.get_config(option, sc)}\n')
            else:
                temp.append('\n')
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

        # handle raw commands
        if self.conf.has_section('RAW'):
            sc = 'RAW'
            # st.cmd
            # lines_before_dbload
            for option in self.conf.options(sc):
                if option.startswith('cmd_before_dbload_'):
                    lines_before_dbload.append(f'{self.get_config(option, sc)}\n')
            else:
                lines_before_dbload.append('\n')
            # lines_at_dbload
            for option in self.conf.options(sc):
                if option.startswith('cmd_at_dbload_'):
                    lines_at_dbload.append(f'{self.get_config(option, sc)}\n')
            # lines after iocinit
            for option in self.conf.options(sc):
                if option.startswith('cmd_after_iocinit_'):
                    lines_after_iocinit.append(f'{self.get_config(option, sc)}\n')
            else:
                lines_after_iocinit.append('\n')
            # file copy
            for option in self.conf.options(sc):
                if option.startswith('file_copy_'):
                    fs = self.get_config(option, sc).split(sep=':')
                    if len(fs) == 2:
                        src = fs[0]
                        dest = fs[1]
                        mode = 'r'
                    elif len(fs) == 3:
                        src = fs[0]
                        dest = fs[1]
                        mode = fs[2]
                    else:
                        print(f'IOC("{self.name}").generate_st_cmd: Warning. Invalid option "{option}": '
                              f'"{self.get_config(option, sc)}" for file copy, skipped.')
                        continue
                    file_copy(src, dest, mode, self.verbose)

        # generate substitutions file
        if not self.generate_substitution_file():
            print(f'IOC("{self.name}").generate_st_cmd": Failed. Run function IOC.generate_substitution_file failed.')
            return

        # write st.cmd
        file_path = os.path.join(self.boot_path, 'st.cmd')
        try:
            with open(file_path, 'w') as f:
                f.writelines(lines_before_dbload)
                f.writelines(lines_at_dbload)
                f.writelines(lines_after_iocinit)
        except PermissionError as e:
            if self.verbose:
                print(f'IOC("{self.name}").generate_st_cmd": File st.cmd exists, remove it before writing a new one.')
            file_remove(file_path, self.verbose)
            with open(file_path, 'w') as f:
                f.writelines(lines_before_dbload)
                f.writelines(lines_at_dbload)
                f.writelines(lines_after_iocinit)
                if self.verbose:
                    print(f'IOC("{self.name}").generate_st_cmd: Successfully create "st.cmd" file.')
        # set readable and executable permission
        os.chmod(file_path, 0o555)

        # set status: ready and save self.conf to ioc.ini file
        self.set_config('status', 'ready')
        # log ioc.ini
        add_log_file(self.name, self.verbose)
        print(f'IOC("{self.name}").generate_st_cmd": Success. Generating startup files finished.')

    # check configuration before generating startup files.
    def generate_check(self):
        check_flag = True
        # execute normal check in self.check_consistency firstly.
        if not self.check_consistency():
            print(f'IOC("{self.name}").generate_check": Failed. Run self.check_consistency() failed.')
            check_flag = False

        # check whether section ASYN was set correctly.
        if self.conf.has_section('ASYN'):
            sc = 'ASYN'
            if self.get_config('port_type', sc) not in PORT_SUPPORT:
                print(f'IOC("{self.name}").generate_check": Failed. Invalid option '
                      f'"port_type" in section "{sc}", please check and reset the settings correctly.')
                check_flag = False
            if self.get_config('port_config', sc) == '':
                print(f'IOC("{self.name}").generate_check: Failed. Empty option '
                      f'"port_config" detected in section "{sc}", please check and reset the settings correctly.')
                check_flag = False
            for option in self.conf.options(sc):
                if option.startswith('asyn_option_'):
                    if self.get_config(option, sc) == '':
                        print(f'IOC("{self.name}").generate_check: Failed. Empty option "{option}" detected in '
                              f'section "{sc}", please check and reset the settings correctly.')
                        check_flag = False
                if option.startswith('load_'):
                    if self.get_config(option, sc) == '':
                        print(f'IOC("{self.name}").generate_check: Failed. Empty option detected in '
                              f'"{option}" for section "{sc}", please check and reset correctly.')
                        check_flag = False

        # check whether section STREAM was set correctly.
        if self.conf.has_section('STREAM'):
            sc = 'STREAM'
            if self.get_config('port_type', sc) not in PORT_SUPPORT:
                print(f'IOC("{self.name}").generate_check: Failed. Invalid option '
                      f'"port_type" in section "{sc}", please check and reset the settings correctly.')
                check_flag = False
            if self.get_config('port_config', sc) == '':
                print(f'IOC("{self.name}").generate_check: Failed. Empty option "port_config" detected in'
                      f' section "{sc}", please check and reset the settings correctly.')
                check_flag = False
            if self.get_config('protocol_file', sc) == '':
                print(f'IOC("{self.name}").generate_check: Failed. Empty option "protocol_file" detected in '
                      f'section "{sc}", please check and reset the settings correctly.')
                check_flag = False
            for option in self.conf.options(sc):
                if option.startswith('asyn_option_'):
                    if self.get_config(option, sc) == '':
                        print(f'IOC("{self.name}").generate_check: Failed. Empty option "{option}" detected in '
                              f' section "{sc}", please check and reset the settings correctly.')
                        check_flag = False
        return check_flag

    # check consistency with ioc.ini and st.cmd and running containers.
    def check_consistency(self, run_check=False):
        consistency_flag = True
        if run_check:
            # checks before running the IOC project.
            # only generated projects can do run-check.
            if not self.check_config('status', 'ready'):
                print(f'IOC("{self.name}").check_consistency: Failed for run-check. IOC startup files not generated.')
                return False

            # check whether ioc.ini file be modified after generating startup files.
            if not check_log_file(self.name, self.verbose):
                print(f'IOC("{self.name}").check_consistency: Failed for run-check. Settings has been changed after '
                      f'generating startup files.')
                self.set_config('status', 'unready')
                return False

            # check whether .substitutions file is created.
            if not os.path.isfile(os.path.join(self.db_path, f'{self.name}.substitutions')):
                print(
                    f'IOC("{self.name}").check_consistency: Failed for run-check. '
                    f'"{self.name}.substitutions" not found.')
                consistency_flag = False

            # if StreamDevice defined, check protocol file
            if self.conf.has_section('STREAM'):
                ps = self.get_config('protocol_file', 'STREAM').split(',')
                for item in ps:
                    if item not in os.listdir(self.settings_path):
                        print(f'IOC("{self.name}").check_consistency: Failed for run-check. Protocol file "{item}" for '
                              f'StreamDevice not found in "{self.name}/settings/".')
                        consistency_flag = False
        else:
            # normal checks for IOC project.
            # check name in ioc.ini equal to directory name.
            if self.get_config('name') != os.path.basename(self.dir_path):
                print(f'IOC("{self.name}").check_consistency: Failed for normal-check. Name defined in ioc.ini '
                      f'"{self.get_config("name")}" is not as same as the directory name. This will be automatically '
                      f'set to directory name when next IOC object initialization, '
                      f'but you\'d better to check the settings again.')
                consistency_flag = False

            # check status 'ready' for file change, if changed set status 'unready'.
            if self.check_config('status', 'ready') and not check_log_file(self.name, self.verbose):
                print(f'IOC("{self.name}").check_consistency: Failed for normal-check. Settings has been changed after'
                      f' generating startup files.')
                self.set_config('status', 'unready')
                consistency_flag = False

            # check whether modules to be installed was set correctly.
            module_list = self.get_config('module').strip().split(',')
            for s in module_list:
                if s == '':
                    continue
                else:
                    if s.strip().lower() not in MODULES_PROVIDED:
                        print(f'IOC("{self.name}").check_consistency: Failed for normal-check. Invalid option '
                              f'"module: {s}", please check and reset the settings correctly.')
                        consistency_flag = False

            # asyn and stream should not exist at the same time.
            if self.conf.has_section('ASYN') and self.conf.has_section('STREAM'):
                print(f'IOC("{self.name}").check_consistency: Failed for normal-check. ASYN and StreamDevice'
                      f'should not be set simultaneously, please check and reset the settings correctly.')
                consistency_flag = False
        return consistency_flag
