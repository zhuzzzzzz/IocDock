import os
import configparser

from .IMFuncsAndConst import try_makedirs, file_remove, dir_remove, file_copy, condition_parse, log_time, \
    delete_time_log, check_time_log
from .IMFuncsAndConst import CONFIG_FILE, REPOSITORY_TOP, CONTAINER_IOC_PATH, CONTAINER_IOC_RUN_PATH, \
    DEFAULT_IOC, MODULES_PROVIDED, DEFAULT_MODULES


class IOC:
    def __init__(self, dir_path=None, verbose=False):

        # self.dir_path
        # self.config_file_path
        # self.settings_path
        # self.log_path
        # self.db_path
        # self.boot_path
        # self.template_path
        # self.settings_path_in_docker
        # self.log_path_in_docker
        # self.startup_path_in_docker

        self.verbose = verbose

        if not dir_path or not os.path.isdir(dir_path):
            self.dir_path = os.path.join(os.getcwd(), REPOSITORY_TOP, 'default')
            print(f'IOC.__init__: no path or wrong path given, IOC init at default path: "{self.dir_path}".')
        else:
            self.dir_path = dir_path
        try_makedirs(self.dir_path, self.verbose)
        self.config_file_path = os.path.join(self.dir_path, CONFIG_FILE)

        self.conf = None
        if not self.read_config():
            if self.verbose:
                print(f'IOC.__init__: initialize a new ioc.ini file "{self.config_file_path}" with default settings.')
            self.set_config('name', os.path.basename(self.dir_path))
            self.set_config('bin', '')
            self.set_config('module', '')
            self.set_config('container', '')
            self.set_config('host', '')
            self.set_config('status', 'created')
            self.set_config('description', '')
            self.set_config('file', '', section='DB')
        else:
            if self.verbose:
                print(f'IOC.__init__: initialize IOC by ioc.ini file "{self.config_file_path}".')

        self.name = self.get_config('name')
        if self.name != os.path.basename(self.dir_path):
            old_name = self.name
            self.name = os.path.basename(self.dir_path)
            self.set_config('name', self.name)
            print(f'IOC.__init__: get wrong name \"{old_name}\" from \"{self.config_file_path}\", there may be '
                  f'something wrong, name has been set to directory name: \"{self.name}\" automatically.')

        self.settings_path = os.path.normpath(os.path.join(self.dir_path, 'settings'))
        try_makedirs(self.settings_path, self.verbose)
        self.log_path = os.path.normpath(os.path.join(self.dir_path, 'log'))
        try_makedirs(self.log_path, self.verbose)
        self.db_path = os.path.normpath(os.path.join(self.dir_path, 'startup', 'db'))
        try_makedirs(self.db_path, self.verbose)
        self.boot_path = os.path.normpath(os.path.join(self.dir_path, 'startup', 'iocBoot'))
        try_makedirs(self.boot_path, self.verbose)
        self.template_path = os.path.normpath(os.path.join(os.getcwd(), 'imtools', 'template'))
        if not os.path.exists(self.template_path):
            print("IOC.__init__: can't find template directory, you may run the scripts at a wrong path.")

        self.settings_path_in_docker = os.path.join(CONTAINER_IOC_RUN_PATH, self.name, 'settings')
        self.log_path_in_docker = os.path.join(CONTAINER_IOC_RUN_PATH, self.name, 'log')
        self.startup_path_in_docker = os.path.join(CONTAINER_IOC_RUN_PATH, self.name, 'startup')

    def read_config(self):
        if os.path.exists(self.config_file_path):
            conf = configparser.ConfigParser()
            if conf.read(self.config_file_path):
                self.conf = conf
                return True
            else:
                self.conf = None
                if self.verbose:
                    print(f'IOC.read_config: failed, path "{self.config_file_path}" exists, but not a valid configure '
                          f'file.')
                return False
        else:
            self.conf = None
            if self.verbose:
                print(f'IOC.read_config: failed, path "{self.config_file_path}" does not exists.')
            return False

    def write_config(self):
        with open(self.config_file_path, 'w') as f:
            self.conf.write(f)

    def set_config(self, option, value, section='IOC'):
        # a status indicator for status field. set "changed" if ioc.ini changed by this function after generated.
        if self.check_config('status', 'generated') and option != 'status':
            self.set_config('status', 'changed')
        if self.conf:
            if section not in self.conf:
                self.conf.add_section(section)
        else:
            self.conf = configparser.ConfigParser()
            self.conf.add_section(section)
        self.conf.set(section, option, value)
        self.write_config()
        if hasattr(self, 'name'):
            log_time(self.name)

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
        print(f' settings of "{self.name}" '.center(37, '='))
        if self.conf:
            for section in self.conf.sections():
                print(f'[{section}]')
                for key, value in self.conf.items(section):
                    print(f'{key}: {value}')

    def remove(self, all_remove=False):
        if all_remove:
            delete_time_log(self.name)
            dir_remove(self.dir_path, self.verbose)
        else:
            for item in (self.boot_path, self.settings_path, self.log_path):
                dir_remove(item, self.verbose)
            for item in os.listdir(self.db_path):
                if item in os.listdir(os.path.join(self.template_path, 'db')) and item.endswith('.db'):
                    file_remove(item, self.verbose)

    def generate_st_cmd(self, force_executing=False, default_executing=False):
        if not self.check_config('status', 'configured') and not self.check_config('status', 'generated'):
            print(f'IOC.generate_st_cmd: failed, IOC "{self.name}" should be configured firstly '
                  f'before executing this function.')
            return

        lines_before_dbload = []
        lines_at_dbload = [f'\ncd {self.startup_path_in_docker}\n',
                           f'dbLoadTemplate "db/{self.name}.substitutions"\n', ]
        lines_after_iocinit = ['\niocInit\n\n']

        # question whether to use default for unspecified IOC executable binary.
        if not self.get_config('bin'):
            if default_executing:
                self.set_config('bin', DEFAULT_IOC)
                print(f'IOC.generate_st_cmd: IOC executable binary was set to default "{DEFAULT_IOC}".')
            else:
                if force_executing:
                    print('IOC.generate_st_cmd: failed and exit, no IOC executable binary specified.')
                    return
                while not force_executing:
                    ans = input(f"IOC.generate_st_cmd: IOC executable binary not defined, use default '{DEFAULT_IOC}' "
                                f"to continue?[y|n]:")
                    if ans.lower() == 'n' or ans.lower() == 'no':
                        print('IOC.generate_st_cmd: failed and exit, no IOC executable binary specified.')
                        return
                    if ans.lower() == 'y' or ans.lower() == 'yes':
                        self.set_config('bin', DEFAULT_IOC)
                        print(f'IOC.generate_st_cmd: IOC executable binary was set default to "{DEFAULT_IOC}".')
                        break
                    print('invalid input, please try again.')

        # question whether to use default for unspecified install modules.
        if not self.get_config('module'):
            if default_executing:
                self.set_config('modules', DEFAULT_MODULES)
                print(f'IOC.generate_st_cmd: modules to be installed set to default "{DEFAULT_MODULES}".')
            else:
                while not force_executing:
                    ans = input(
                        f'IOC.generate_st_cmd: modules to be installed not defined, use default "{DEFAULT_MODULES}" '
                        f'to continue?[y|n]:')
                    if ans.lower() == 'n' or ans.lower() == 'no':
                        print('continue, no module will be installed.')
                        break
                    if ans.lower() == 'y' or ans.lower() == 'yes':
                        self.set_config('module', DEFAULT_MODULES)
                        print(f'IOC.generate_st_cmd: modules to be installed set to default "{DEFAULT_MODULES}".')
                        break
                    print('invalid input, please try again.')

        print(f'IOC.generate_st_cmd: setting "module: {self.get_config("module")}" '
              f'will be implied to generate st.cmd file for IOC "{self.name}".')

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

        # ioc-status
        if 'ioc-status' in self.get_config('module').lower():
            # st.cmd
            # lines_at_dbload
            lines_at_dbload.append(f'dbLoadRecords("db/status_ioc.db","IOC={self.name}")\n')
            # devIocStats .db
            file_path = os.path.join(self.db_path, 'status_ioc.db')
            template_file_path = os.path.join(self.template_path, 'db', 'status_ioc.db')
            file_copy(template_file_path, file_path, 'r', self.verbose)

        # os-status
        if 'os-status' in self.get_config('module').lower():
            # st.cmd
            # lines_at_dbload
            lines_at_dbload.append(f'dbLoadRecords("db/status_OS.db","HOST={self.name}:docker")\n')
            # devIocStats .db
            file_path = os.path.join(self.db_path, 'status_OS.db')
            template_file_path = os.path.join(self.template_path, 'db', 'status_OS.db')
            file_copy(template_file_path, file_path, 'r', self.verbose)

        # write st.cmd.
        file_path = os.path.join(self.boot_path, 'st.cmd')
        try:
            with open(file_path, 'w') as f:
                f.writelines(lines_before_dbload)
                f.writelines(lines_at_dbload)
                f.writelines(lines_after_iocinit)
        except PermissionError as e:
            if self.verbose:
                print(f'IOC.generate_st_cmd: st.cmd exists, first remove it before write a new one.')
            file_remove(file_path, self.verbose)
            with open(file_path, 'w') as f:
                f.writelines(lines_before_dbload)
                f.writelines(lines_at_dbload)
                f.writelines(lines_after_iocinit)
        # set readable and executable permission.
        os.chmod(file_path, 0o555)

        # set status: generated and save self.conf to ioc.ini file.
        self.set_config('status', 'generated')
        print(f'IOC.generate_st_cmd: success, finished generating st.cmd file for IOC "{self.name}".')

    # get db files from given path.
    def get_db_list(self, db_p=None):
        if not db_p or not os.path.exists(db_p):
            db_p = self.db_path
        db_list = ''
        for item in os.listdir(db_p):
            if item.endswith('.db') and (item not in os.listdir(os.path.join(self.template_path, 'db'))):
                db_list += f'{item}, '
                file_copy(os.path.join(db_p, item), os.path.join(self.db_path, item), 'r', self.verbose)
        db_list = db_list.rstrip(', ')
        if db_list:
            self.set_config('file', db_list, 'DB')
            print(f'IOC.get_db_list: success, set attribute "file: {db_list}" for IOC "{self.name}".')
            return True
        else:
            print(f'IOC.get_db_list: failed, no db files found in "{db_p}".')
            return False

    def generate_substitution_file(self):
        if not self.get_config('file', 'DB'):
            if not self.get_db_list():
                print(f'IOC.generate_substitution_file: failed, no db file are provided for IOC "{self.name}", you may '
                      f'add db files first, then set macro replacement settings, before executing this command.')
                return
        if self.get_config('file', 'DB'):
            lines_to_add = []
            for option in self.conf.options('DB'):
                if option.startswith('load'):
                    load_string = self.conf.get('DB', option)
                    dbf, *conditions = load_string.split(',')
                    # print(conditions)
                    dbf = dbf.strip()
                    ks = ''
                    vs = ''
                    for c in conditions:
                        k, v = condition_parse(c)
                        if k:
                            ks += f'{k}, '
                            vs += f'{v}, '
                        else:
                            print(f'IOC.generate_substitution_file: bad condition define "{c}" detected in ioc.ini for '
                                  f'IOC "{self.name}", "{option}: {load_string}", program exit, you may need to '
                                  f'check and set the attribute definition correctly.')
                            return
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
                        print(f'IOC.generate_substitution_file: {self.name}.substitutions exists, '
                              f'first remove it before write a new one.')
                    file_remove(file_path, self.verbose)
                    with open(file_path, 'w') as f:
                        f.writelines(lines_to_add)
                # set readable and executable permission.
                os.chmod(file_path, 0o555)
                self.set_config('status', 'configured')
                print(f'IOC.generate_substitution_file: success, '
                      f'{self.name}.substitutions generated for IOC "{self.name}".')
            else:
                print(f'IOC.generate_substitution_file: failed, "load" option not defined for IOC "{self.name}".')

    # get record list from .substitutions file.
    def get_record_list(self):
        pass

    # check consistency with st.cmd and running containers.
    def check_consistency(self, in_container=False):
        consistency_flag = True
        if in_container:
            pass
            # check bin IOC path
        else:
            # check name in ioc.ini equal to directory name.
            if self.get_config('name') != os.path.basename(self.dir_path):
                print(
                    f'check_consistency failed in "{self.name}": name defined ioc.ini "{self.get_config("name")}" is '
                    f'not equal to path name, this may be automatically changed to correct one when '
                    f'next initialize an IOC object.')
                consistency_flag = False
            # check whether modules to be installed was set correctly.
            module_list = self.get_config('module').strip().split(',')
            for s in module_list:
                if s == '':
                    continue
                else:
                    if s.strip().lower() not in MODULES_PROVIDED:
                        print(f'check_consistency failed in "{self.name}": invalid define detected in option '
                              f'"module", please check and reset correctly.')
                        consistency_flag = False
            # check whether st.cmd file is the latest.
            if self.check_config('status', 'changed'):
                print(f'check_consistency failed in "{self.name}": settings have been changed after generating st.cmd '
                      f'file, you may need to generate it again to get a latest one.')
                consistency_flag = False
            # check whether ioc.ini file be modified manually.
            if not check_time_log(self.name):
                print(f'check_consistency failed in "{self.name}": settings have been manually changed, you may need'
                      f' to generate it again to get a latest one that consistent with settings ioc.ini file.')
                consistency_flag = False
        return consistency_flag
