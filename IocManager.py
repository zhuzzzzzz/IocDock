#!/usr/bin/python3
import argparse
import os, shutil
import configparser
from collections.abc import Iterable

CONFIG_FILE = 'ioc.ini'
REPOSITORY_TOP = 'ioc-repository'
CONTAINER_TOP_PATH = os.path.join('/', 'opt', 'EPICS')
CONTAINER_IOC_PATH = os.path.join(CONTAINER_TOP_PATH, 'IOC')
CONTAINER_IOC_RUN_PATH = os.path.join(CONTAINER_TOP_PATH, 'RUN')

DEFAULT_IOC = 'ST-IOC'
# asyn, stream device needs to be set separately for different hosts.
MODULES_PROVIDED = ['autosave', 'caputlog', 'ioc-status', 'os-status']
DEFAULT_MODULES = 'caputlog, ioc-status'


class IOC:
    def __init__(self, dir_path=None, verbose=False):

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
            self.set_config('modules', '')
            self.set_config('container', '')
            self.set_config('host', '')
            self.set_config('status', 'created')
            self.set_config('description', '')
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
        self.template_path = os.path.normpath(os.path.join(self.dir_path, '..', '..', 'template'))
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

    def get_config(self, option, section="IOC"):
        value = ''  # undefined option will return ''.
        if self.conf.has_option(section, option):
            value = self.conf.get(section, option)
        return value

    def check_config(self, option, value, section='IOC'):
        if self.conf:
            if section in self.conf.sections():
                # check logic special to 'modules' option of section 'IOC'.
                if option == 'modules' and section == 'IOC':
                    if value == '':
                        if self.get_config('modules') == '':
                            return True
                        else:
                            return False
                    elif value.lower() in self.get_config('modules').lower():
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
            dir_remove(self.dir_path, self.verbose)
        else:
            for item in (self.boot_path, self.settings_path, self.log_path):
                dir_remove(item, self.verbose)
            for item in os.listdir(self.db_path):
                if item in os.listdir(os.path.join(self.template_path, 'db')) and item.endswith('.db'):
                    file_remove(item, self.verbose)

    def generate_st_cmd(self, force_executing=False, default_executing=False):
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
        if not self.get_config('modules'):
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
                        self.set_config('modules', DEFAULT_MODULES)
                        print(f'IOC.generate_st_cmd: modules to be installed set to default "{DEFAULT_MODULES}".')
                        break
                    print('invalid input, please try again.')

        print(f'IOC.generate_st_cmd: setting "modules: {self.get_config("modules")}" '
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

        # copy .substitutions from template
        file_path = os.path.join(self.db_path, f'{self.name}.substitutions')
        template_file_path = os.path.join(self.template_path, 'template.substitutions')
        shutil.copy(template_file_path, file_path)

        # autosave
        if self.check_config('modules', 'autosave'):
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
        if self.check_config('modules', 'caputlog'):
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
            shutil.copy(template_file_path, file_path)

        # ioc-status
        if 'ioc-status' in self.get_config('modules').lower():
            # st.cmd
            # lines_at_dbload
            lines_at_dbload.append(f'dbLoadRecords("db/status_ioc.db","IOC={self.name}")\n')
            # devIocStats .db
            file_path = os.path.join(self.db_path, 'status_ioc.db')
            template_file_path = os.path.join(self.template_path, 'db', 'status_ioc.db')
            shutil.copy(template_file_path, file_path)

        # os-status
        if 'os-status' in self.get_config('modules').lower():
            # st.cmd
            # lines_at_dbload
            lines_at_dbload.append(f'dbLoadRecords("db/status_OS.db","HOST={self.name}:docker")\n')
            # devIocStats .db
            file_path = os.path.join(self.db_path, 'status_OS.db')
            template_file_path = os.path.join(self.template_path, 'db', 'status_OS.db')
            shutil.copy(template_file_path, file_path)

        # write st.cmd and set execute permission.
        file_path = os.path.join(self.boot_path, 'st.cmd')
        with open(file_path, 'w') as f:
            f.writelines(lines_before_dbload)
            f.writelines(lines_at_dbload)
            f.writelines(lines_after_iocinit)
        os.chmod(file_path, 0o755)

        # set status: generated and save self.conf to ioc.ini file.
        self.set_config('status', 'generated')
        print(f'IOC.generate_st_cmd: success, finished generating st.cmd file for IOC "{self.name}".')

    # get record list from st.cmd file.
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
            module_list = self.get_config('modules').strip().split(',')
            for s in module_list:
                if s == '':
                    continue
                else:
                    if s.strip().lower() not in MODULES_PROVIDED:
                        print(f'check_consistency failed in "{self.name}": invalid define detected in option '
                              f'"modules", please check and reset correctly.')
                        consistency_flag = False
            # check whether st.cmd file is the latest.
            if self.check_config('status', 'changed'):
                print(f'check_consistency failed in "{self.name}": settings have been changed after generating st.cmd '
                      f'file, you may need to generate it again to get a latest one.')
                consistency_flag = False
        return consistency_flag


def try_makedirs(d, verbose=False):
    verbose = False
    try:
        os.makedirs(d)
    except OSError as e:
        if verbose:
            print(f'try_makedirs("{d}") failed, {e}.')
        return False
    else:
        if verbose:
            print(f'try_makedirs("{d}") Success.')
        return True


def file_remove(file_path, verbose=False):
    try:
        os.remove(file_path)
    except OSError as e:
        print(f'file_remove: "{file_path}" removed failed, {e}.')
    else:
        if verbose:
            print(f'file_remove: "{file_path}" removed.')


def dir_remove(dir_path, verbose=False):
    try:
        shutil.rmtree(dir_path)
    except shutil.Error as e:
        if verbose:
            print(f'dir_remove: "{dir_path}" removed failed, {e}.')
    except FileNotFoundError as e:
        if verbose:
            print(f'dir_remove: "{dir_path}" removed failed, {e}.')
    else:
        if verbose:
            print(f'dir_remove: "{dir_path}" removed.')


def dir_copy(source_folder, destination_folder, verbose=False):
    if os.path.exists(destination_folder):
        if verbose:
            print(f'dir_copy: destination folder "{destination_folder}" exists, first remove it.')
        dir_remove(destination_folder, verbose)
    try:
        shutil.copytree(source_folder, destination_folder)
    except shutil.Error as e:
        if verbose:
            print(f'dir_copy: failed, {e}')
        return False
    else:
        if verbose:
            print(f'dir_copy: success, copy files from "{source_folder}" to "{destination_folder}".')
        return True

# accepts iterable for input
def create_ioc(name, verbose=False, config=None):
    if isinstance(name, str):
        # may add a name string filter here.
        dir_path = os.path.join(os.getcwd(), REPOSITORY_TOP, name)
        if os.path.exists(os.path.join(dir_path, CONFIG_FILE)):
            print(f'create_ioc: failed, IOC "{name}" already exists.')
        else:
            # create an IOC and do initialization by given configparser.ConfigParser() object.
            try_makedirs(dir_path, verbose)
            ioc_temp = IOC(dir_path, verbose)
            if config:
                for section in config.sections():
                    for option in config.options(section):
                        value = config.get(section, option)
                        ioc_temp.set_config(option, value, section)
            print(f'create_ioc: success, IOC "{name}" created.')
            ioc_temp.check_consistency(in_container=False)
            if verbose:
                ioc_temp.show_config()
    elif isinstance(name, Iterable):
        for n in name:
            create_ioc(n, verbose, config)
    else:
        print(f'create_ioc: failed, invalid input args: "{name}".')


# do not accept iterable for input
def set_ioc(name, verbose=False, config=None):
    if isinstance(name, str):
        dir_path = os.path.join(os.getcwd(), REPOSITORY_TOP, name)
        if os.path.exists(os.path.join(dir_path, CONFIG_FILE)):
            # initialize an existing IOC, edit ioc.ini by given configparser.ConfigParser() object.
            ioc_temp = IOC(dir_path, verbose)
            if any(config.options(section) for section in config.sections()):
                for section in config.sections():
                    for option in config.options(section):
                        value = config.get(section, option)
                        ioc_temp.set_config(option, value, section)
                print(f'set_ioc: success, set attributes for IOC "{name}" by given settings.')
                ioc_temp.check_consistency(in_container=False)
                if verbose:
                    ioc_temp.show_config()
            else:
                if verbose:
                    print(f'set_ioc: not config given for setting IOC "{name}".')
        else:
            print(f'set_ioc: set attributes failed, IOC "{name}" not exists.')
    else:
        print(f'set_ioc: failed, invalid input args "{name}" for .')


def gen_st_cmd(name, verbose=False, force_executing=False, default_executing=False):
    dir_path = os.path.join(os.getcwd(), REPOSITORY_TOP, name)
    if os.path.exists(os.path.join(dir_path, CONFIG_FILE)):
        ioc_temp = IOC(dir_path, verbose)
        print(f'gen_st_cmd: start generating st.cmd file for IOC "{name}".')
        ioc_temp.generate_st_cmd(force_executing=force_executing, default_executing=default_executing)
    else:
        print(f'gen_st_cmd: failed, IOC "{name}" not found.')


# generate directory structure for running inside the container.
def repository_to_container(name, gen_path=None, verbose=False):
    dir_path = os.path.join(os.getcwd(), REPOSITORY_TOP, name)
    if os.path.exists(os.path.join(dir_path, CONFIG_FILE)):
        ioc_temp = IOC(dir_path, verbose)

        if not ioc_temp.check_config('status', 'generated'):
            print(f'repository_to_container: failed, attribute "status" get in IOC "{ioc_temp.name}" is not '
                  f'"generated" but "{ioc_temp.get_config("status")}", the directory files may not be prepared.')
            return

        container_name = ioc_temp.get_config('container')
        if not container_name:
            container_name = ioc_temp.name
            if verbose:
                print(f'repository_to_container: attribute "container" not defined in IOC "{ioc_temp.name}", '
                      f'automatically use IOC name as container name.')
        host_name = ioc_temp.get_config('host')
        if not host_name:
            host_name = 'localhost'
            if verbose:
                print(f'repository_to_container: attribute "host" not defined in IOC "{ioc_temp.name}", '
                      f'automatically use "localhost" as host name.')
        if not os.path.isdir(gen_path):
            gen_path = os.getcwd()
            if verbose:
                print(f'repository_to_container: arg "gen_path" invalid or not given, '
                      f'automatically use current work directory as generate path.')
        top_path = os.path.join(gen_path, 'ioc-for-docker', host_name, container_name)
        if dir_copy(ioc_temp.dir_path, top_path, verbose):
            print(f'repository_to_container: success, IOC "{name}" directory created in generate path for docker.')
        else:
            print(f'repository_to_container: failed, for IOC "{name}" you may run this again using "-v" option to see '
                  f'what happened in details.')
    else:
        print(f'repository_to_container: failed, IOC "{name}" not found.')


# Collect files from the container directory to central repository LOG directory.
def container_to_repository(container_path, repository_LOG_path):
    pass


# remove only generated files or remove all, do not accept iterable for input.
def remove_ioc(name, all_remove=False, force_removal=False, verbose=False):
    dir_path = os.path.join(os.getcwd(), REPOSITORY_TOP, name)
    if os.path.exists(os.path.join(dir_path, CONFIG_FILE)):
        if not force_removal:
            if all_remove:
                print(f'remove_ioc: IOC "{name}" will be removed completely.', end='')
            else:
                print(f'remove_ioc: IOC "{name}" will be removed, but ".ini" file and ".db" files are preserved.',
                      end='')
            ans = input(f'continue?[y|n]:')
            if ans.lower() == 'y' or ans.lower() == 'yes':
                force_removal = True
            else:
                print(f'remove_ioc: failed, remove IOC "{name}" canceled.')
        if force_removal:
            ioc_temp = IOC(dir_path, verbose)
            ioc_temp.remove(all_remove)
            if all_remove:
                print(f'remove_ioc: success, IOC "{name}" removed completely.')
            else:
                print(f'remove_ioc: success, IOC "{name}" removed, but ".ini" file and ".db" files are preserved.')
    else:
        print(f'remove_ioc: failed, IOC "{name}" not found.')


# do nothing, just create an IOC() object by given path to activate its self.__init__() for a name check scheme.
def refresh_ioc(name):
    if isinstance(name, str):
        # may add a name string filter here.
        dir_path = os.path.join(os.getcwd(), REPOSITORY_TOP, name)
        if os.path.exists(os.path.join(dir_path, CONFIG_FILE)):
            IOC(dir_path)
    elif isinstance(name, Iterable):
        for n in name:
            refresh_ioc(n)


# show all subdirectory IOCs for given path, return the list of all IOCs.
def get_all_ioc(dir_path=None):
    ioc_list = []
    if not dir_path:
        dir_path = os.path.join(os.getcwd(), REPOSITORY_TOP)
    for p in os.listdir(dir_path):
        subdir_path = os.path.join(dir_path, p)
        if os.path.isdir(subdir_path) and CONFIG_FILE in os.listdir(subdir_path):
            ioc_list.append(IOC(subdir_path))
    return ioc_list


# show IOC for specified conditions of specified section, AND logic was implied to each condition.
def get_filtered_ioc(condition: Iterable, section='IOC', show_info=False, verbose=False):
    ioc_list = get_all_ioc()

    index_to_remove = []
    if not condition:
        # default not filter any IOC by options, but filter by sections.
        for i in range(0, len(ioc_list)):
            if not ioc_list[i].conf.has_section(section=section):
                index_to_remove.append(i)
        if verbose:
            print(f'no condition specified, list all IOCs that have section "{section}":')
    elif isinstance(condition, str):
        key, value = condition_parse(condition)
        if key:
            for i in range(0, len(ioc_list)):
                if not ioc_list[i].check_config(key, value, section):
                    index_to_remove.append(i)
            if verbose:
                print(f'results for valid condition "{condition}":')
        else:
            # wrong condition parsed, not return any result.
            index_to_remove = [i for i in range(0, len(ioc_list))]
            if verbose:
                print(f'invalid condition "{condition}" specified.')
    elif isinstance(condition, Iterable):
        valid_flag = False  # flag to check whether any valid condition has been given.
        valid_condition = []
        for c in condition:
            key, value = condition_parse(c)
            # only valid condition was parsed to filter IOC.
            if key:
                valid_flag = True
                valid_condition.append(c)
                for i in range(0, len(ioc_list)):
                    if not ioc_list[i].check_config(key, value, section):
                        index_to_remove.append(i)
            else:
                if verbose:
                    print(f'invalid condition "{c}" specified, skipped.')
        if valid_flag:
            # if there is any valid condition given, not return any result.
            if verbose:
                print(f'results find for valid condition "{valid_condition}":')
        else:
            # if there is no valid condition given, show.
            index_to_remove = [i for i in range(0, len(ioc_list))]
            if verbose:
                print(f'no valid condition specified: "{condition}".')
    else:
        index_to_remove = [i for i in range(0, len(ioc_list))]
        if verbose:
            print(f'no valid condition specified: "{condition}".')

    index_to_preserve = []
    for i in range(0, len(ioc_list)):
        if i in index_to_remove:
            continue
        else:
            index_to_preserve.append(i)

    for i in index_to_preserve:
        if show_info:
            ioc_list[i].show_config()
        else:
            print(ioc_list[i].name, end=' ')
    else:
        print('')

    for i in index_to_preserve:
        ioc_list[i].check_consistency(in_container=False)


def condition_parse(condition: str):
    c_s = condition.strip().split(sep='=')
    # print(c_s)
    if len(c_s) == 2 and len(c_s[0]) > 0:
        key = c_s[0].strip()
        value = c_s[1].strip()
        # print(key, value)
        return key, value
    else:
        return None, None


if __name__ == '__main__':
    # argparse
    parser = argparse.ArgumentParser(description='IOC runtime file manager for docker. this script should '
                                                 'be run inside repository directory, where there is a template '
                                                 'folder.')

    subparsers = parser.add_subparsers(
        help='to get subparser help, you may run "./iocManager.py [create|set|exec|list|remove] -h".')

    parser_create = subparsers.add_parser('create', help='create IOC by given settings.')
    parser_create.add_argument('name', type=str, nargs='+', help='IOC name, name list is supported.')
    parser_create.add_argument('-f', '--from-ini-file', type=str,
                               help='settings from specified .ini files, settings created by this '
                                    'option may be override by other options.')
    parser_create.add_argument('-o', '--specify-options', type=str, nargs='+',
                               help='manually specify attribute, format: "key=value". This option may override all '
                                    'other options if conflicts.')
    parser_create.add_argument('-s', '--specify-section', type=str, default='IOC',
                               help='appointing a section for manually specified attribute, default: "IOC".')
    parser_create.add_argument('--putlog', action="store_true", help='add caPutLog.')
    parser_create.add_argument('--ioc-status', action="store_true",
                               help='add devIocStats for IOC monitor.')
    parser_create.add_argument('--os-status', action="store_true",
                               help='add devIocStats for OS monitor.')
    parser_create.add_argument('--autosave', action="store_true", help='add autosave.')
    parser_create.add_argument('-v', '--verbose', action="store_true", help='show details.')
    parser_create.set_defaults(func='parse_create')

    parser_set = subparsers.add_parser('set', help='set attributes for IOC.')
    parser_set.add_argument('name', type=str, nargs='+', help='IOC name, name list is supported.')
    parser_set.add_argument('-f', '--from-ini-file', type=str,
                            help='settings from specified .ini files, settings set by this '
                                 'option may be override by other options.')
    parser_set.add_argument('-o', '--specify-options', type=str, nargs='+',
                            help='manually specify attribute, format: "key=value". This option may override all '
                                 'other options if conflicts.')
    parser_set.add_argument('-s', '--specify-section', type=str, default='IOC',
                            help='appointing a section for manually specified attribute, default: "IOC".')
    parser_set.add_argument('--putlog', action="store_true", help='set caPutLog.')
    parser_set.add_argument('--ioc-status', action="store_true",
                            help='set devIocStats for IOC monitor.')
    parser_set.add_argument('--os-status', action="store_true",
                            help='set devIocStats for OS monitor.')
    parser_set.add_argument('--autosave', action="store_true", help='set autosave.')
    parser_set.add_argument('-v', '--verbose', action="store_true", help='show details.')
    parser_set.set_defaults(func='parse_set')

    parser_execute = subparsers.add_parser('exec', help='execute functions for IOC.')
    parser_execute.add_argument('name', type=str, nargs='+', help='IOC name, name list is supported.')
    parser_execute.add_argument('-g', '--generate-st-cmd', action="store_true", help='generate st.cmd startup file.')
    parser_execute.add_argument('-f', '--force-silent', action="store_true",
                                help='force generating st.cmd file and do not ask.')
    parser_execute.add_argument('-d', '--default-install', action="store_true",
                                help='force generating st.cmd file using default.')
    parser_execute.add_argument('-o', '--to-docker', action="store_true", help='copy generated IOC directory files '
                                                                               'out to a path for docker deployment.')
    parser_execute.add_argument('-p', '--generate-path', type=str, default='',
                                help='appointing a generate path where all files go into, default: current work path.')
    parser_execute.add_argument('-v', '--verbose', action="store_true", help='show details.')
    parser_execute.set_defaults(func='parser_execute')

    parser_list = subparsers.add_parser('list', help='get existing IOC by given conditions.')
    parser_list.add_argument('condition', type=str, nargs='*',
                             help='conditions to filter IOC, list all IOC if no input provided.')
    parser_list.add_argument('-s', '--specify-section', type=str, default='IOC',
                             help='appointing a section for filter, default: "IOC".')
    parser_list.add_argument('-v', '--verbose', action="store_true", help='show details.')
    parser_list.add_argument('-i', '--show-info', action="store_true", help='show details of IOC.')
    parser_list.set_defaults(func='parse_list')

    parser_remove = subparsers.add_parser('remove', help='remove IOC.')
    parser_remove.add_argument('name', type=str, nargs='+', help='IOC name, name list is supported.')
    parser_remove.add_argument('-r', '--remove-all', action="store_true",
                               help='remove entire IOC, this will remove all files of an IOC.')
    parser_remove.add_argument('-f', '--force', action="store_true", help='force removal, do not ask.')
    parser_remove.add_argument('-v', '--verbose', action="store_true", help='show details.')
    parser_remove.set_defaults(func='parse_remove')

    args = parser.parse_args()
    if not any(vars(args).values()):
        parser.print_help()
        exit()

    # print(f'{args}')
    if args.verbose:
        print(args)
    if args.func == 'parse_create' or args.func == 'parse_set':
        conf_temp = configparser.ConfigParser()
        #
        if args.from_ini_file:
            if conf_temp.read(args.from_ini_file):
                if args.verbose:
                    print(f'read .ini file "{args.from_ini_file}".')
            else:
                if args.verbose:
                    print('invalid .ini file "{args.from_ini_file}" specified, skipped.')
        #
        module_installed = ''
        if args.autosave:
            module_installed += 'autosave, '
        if args.putlog:
            module_installed += 'caputlog, '
        if args.ioc_status:
            module_installed += 'ioc-status, '
        if args.os_status:
            module_installed += 'os-status, '
        module_installed = module_installed.rstrip(', ')
        if module_installed:
            if not conf_temp.has_section('IOC'):
                conf_temp.add_section('IOC')
            conf_temp.set('IOC', 'modules', module_installed)
            if args.verbose:
                print(f'set "modules: {module_installed}" according to specified options for section "IOC".')
        #
        if args.specify_options:
            if not conf_temp.has_section(args.specify_section):
                conf_temp.add_section(args.specify_section)
            for item in args.specify_options:
                k, v = condition_parse(item)
                if k:
                    conf_temp.set(args.specify_section, k, v)
                    if args.verbose:
                        print(f'set "{k}: {v}" for section "{args.specify_section}".')
                else:
                    if args.verbose:
                        print(f'wrong option "{item}" for section "{args.specify_section}", skipped.')
        #
        if args.func == 'parse_create':
            # ./iocManager.py create
            create_ioc(args.name, args.verbose, conf_temp)
        else:
            # ./iocManager.py set
            for item in args.name:
                set_ioc(item, args.verbose, config=conf_temp)
    if args.func == 'parser_execute':
        for item in args.name:
            if args.generate_st_cmd:
                gen_st_cmd(item, verbose=args.verbose, force_executing=args.force_silent,
                           default_executing=args.default_install)
            if args.to_docker:
                repository_to_container(item, args.generate_path, args.verbose)
    if args.func == 'parse_list':
        get_filtered_ioc(args.condition, section=args.specify_section, show_info=args.show_info, verbose=args.verbose)
    if args.func == 'parse_remove':
        for item in args.name:
            remove_ioc(item, all_remove=args.remove_all, force_removal=args.force, verbose=args.verbose)
