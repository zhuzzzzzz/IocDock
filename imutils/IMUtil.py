import os
import sys
import yaml
import tarfile
import datetime
import configparser
from tabulate import tabulate
from collections.abc import Iterable

import imutils.IMConfig as IMConfig
from imutils.IMConfig import get_manager_path
from imutils.IMError import IMIOCError, IMValueError
from imutils.IocClass import IOC
from imutils.SwarmClass import SwarmManager, SwarmService
from imutils.IMFunc import (try_makedirs, dir_copy, file_copy, condition_parse, dir_remove,
                            relative_and_absolute_path_to_abs, file_remove, multi_line_parse, )


# accepts iterable for input
def create_ioc(name, args, config=None, verbose=False):
    if isinstance(name, str):
        #
        invalid_characters = (' ', ',', ';', '|', '\\', '~', '`')
        for cha in invalid_characters:
            if cha in name:
                print(f'create_ioc: Failed. IOC name "{name}" has invalid character "{cha}".')
                return
        #
        dir_path = os.path.join(IMConfig.REPOSITORY_PATH, name)
        if os.path.exists(os.path.join(dir_path, IMConfig.IOC_CONFIG_FILE)):
            print(f'create_ioc: Failed. IOC "{name}" already exists.')
        else:
            # Create an IOC and do initialization by given configparser.ConfigParser() object.
            try_makedirs(dir_path, verbose)
            ioc_temp = IOC(dir_path=dir_path, verbose=verbose, create=True)
            if hasattr(args, 'add_asyn') and args.add_asyn:
                ioc_temp.add_module_template('asyn')
                if verbose:
                    print(f'create_ioc: add asyn template for IOC "{name}".')
            if hasattr(args, 'add_stream') and args.add_stream:
                ioc_temp.add_module_template('stream')
                if verbose:
                    print(f'create_ioc: add stream template for IOC "{name}".')
            if hasattr(args, 'add_raw') and args.add_raw:
                ioc_temp.add_raw_cmd_template()
                if verbose:
                    print(f'create_ioc: add raw command template for IOC "{name}".')
            if config:
                for section in config.sections():
                    if section == 'SRC':  # src files are automatically detected.
                        continue
                    for option in config.options(section):
                        if section == 'IOC' and option == 'name':  # Name should not be directly copied.
                            continue
                        if section == 'IOC' and option == 'status':  # status should not be directly copied.
                            continue
                        if section == 'IOC' and option == 'snapshot':  # snapshot should not be directly copied.
                            continue
                        if section == 'DB' and option == 'file':  # deprecated option, for IOC updating.
                            continue
                        value = config.get(section, option)
                        ioc_temp.set_config(option, value, section)
                else:
                    ioc_temp.write_config()
            print(f'create_ioc: Success. IOC "{name}" created.')
    elif isinstance(name, Iterable):
        for n in name:
            create_ioc(n, args, config=config, verbose=verbose)
    else:
        print(f'create_ioc: Failed. Invalid input args: "{name}".')


# accept iterable for input
def set_ioc(name, args, config=None, verbose=False):
    if isinstance(name, str):
        dir_path = os.path.join(IMConfig.REPOSITORY_PATH, name)
        if not os.path.exists(os.path.join(dir_path, IMConfig.IOC_CONFIG_FILE)):
            print(f'set_ioc: Failed. IOC "{name}" is not exist.')
        else:
            # Initialize an existing IOC, edit ioc.ini by given configparser.ConfigParser() object.
            ioc_temp = IOC(dir_path=dir_path, verbose=verbose)
            modify_flag = False
            if args.add_asyn:
                if ioc_temp.add_module_template('asyn'):
                    modify_flag = True
                    if verbose:
                        print(f'set_ioc: add asyn template for IOC "{name}".')
            if args.add_stream:
                if ioc_temp.add_module_template('stream'):
                    modify_flag = True
                    if verbose:
                        print(f'set_ioc: add stream template for IOC "{name}".')
            if args.add_raw:
                if ioc_temp.add_raw_cmd_template():
                    modify_flag = True
                    if verbose:
                        print(f'set_ioc: add raw command template for IOC "{name}".')
            if any(config.options(section) for section in config.sections()):
                for section in config.sections():
                    if section == 'SRC':  # src files are automatically detected.
                        continue
                    for option in config.options(section):
                        if section == 'IOC' and option == 'name':
                            continue
                        if section == 'IOC' and option == 'status':
                            continue
                        if section == 'IOC' and option == 'snapshot':
                            continue
                        value = config.get(section, option)
                        ioc_temp.set_config(option, value, section)
                modify_flag = True
            if modify_flag:
                ioc_temp.write_config()
                print(f'set_ioc: Success. IOC "{name}" modified by given settings.')
            else:
                if verbose:
                    print(f'set_ioc: No setting was given for IOC "{name}".')
    elif isinstance(name, Iterable):
        for n in name:
            set_ioc(n, args, config=config, verbose=verbose)
    else:
        print(f'set_ioc: Failed. Invalid input args "{name}".')


# do not accept iterable for input
# Remove IOC projects. just remove generated files or remove all files.
def remove_ioc(name, remove_all=False, force_removal=False, verbose=False):
    dir_path = os.path.join(IMConfig.REPOSITORY_PATH, name)
    if os.path.exists(os.path.join(dir_path, IMConfig.IOC_CONFIG_FILE)):
        if not force_removal:
            if remove_all:
                print(f'remove_ioc: IOC "{name}" will be removed completely.', end='')
            else:
                print(f'remove_ioc: Remove IOC "{name}" partially. only the generated files will be removed,'
                      f' "src/" directory and settings file will be preserved.', end='')
            ans = input(f'Continue?[y|n]:')
            if ans.lower() == 'y' or ans.lower() == 'yes':
                force_removal = True
            elif ans.lower() == 'n' or ans.lower() == 'no':
                print(f'remove_ioc: Remove canceled.')
            else:
                print(f'remove_ioc: Failed. Invalid input, remove canceled.')
        if force_removal:
            ioc_temp = IOC(dir_path=dir_path, verbose=verbose)
            ioc_temp.remove(remove_all)
            if remove_all:
                print(f'remove_ioc: Success. IOC "{name}" removed completely.')
            else:
                print(f'remove_ioc: Success. IOC "{name}" removed, '
                      f'but directory "src/" and file "{IMConfig.IOC_CONFIG_FILE}" are preserved.')
    else:
        print(f'remove_ioc: Failed. IOC "{name}" not found.')


# do not accept iterable for input
def rename_ioc(old_name, new_name, verbose):
    dir_path = os.path.join(IMConfig.REPOSITORY_PATH, old_name)
    if os.path.exists(os.path.join(dir_path, IMConfig.IOC_CONFIG_FILE)):
        try:
            os.rename(dir_path, os.path.join(IMConfig.REPOSITORY_PATH, new_name))
        except Exception as e:
            print(f'rename_ioc: Failed. Changing directory name failed, "{e}".')
        else:
            if verbose:
                IOC(dir_path=os.path.join(IMConfig.REPOSITORY_PATH, new_name), verbose=verbose)
            else:
                with open(os.devnull, 'w') as devnull:
                    original_stdout = sys.stdout
                    original_stderr = sys.stderr
                    sys.stdout = devnull
                    sys.stderr = devnull
                    IOC(dir_path=os.path.join(IMConfig.REPOSITORY_PATH, new_name), verbose=verbose)
                    sys.stdout = original_stdout
                    sys.stderr = original_stderr
            print(f'rename_ioc: Success. IOC project name changed from "{old_name}" to "{new_name}".')
    else:
        print(f'rename_ioc: Failed. IOC "{old_name}" not found.')


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
        dir_path = IMConfig.REPOSITORY_PATH
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


def get_filtered_ioc(condition: list, section='IOC', from_list=None, show_info=False, show_panel=False,
                     verbose=False):
    """
    Filter and List IOC projects by specified conditions and section. Logic "AND" is used between each condition.

    :param condition: filter conditions such as ["a=b", "c=d"]
    :param section: filter on given section in config file
    :param from_list: filter from given IOC list
    :param show_info: show IOC configurations
    :param show_panel: show IOC management pannel
    :param verbose:
    :return:
    """
    section = section.upper()  # to support case-insensitive filter for section.
    ioc_list = get_all_ioc(read_mode=True, from_list=from_list, verbose=verbose)

    if verbose and from_list is not None:
        print(f'List IOC projects from "{from_list}".')

    index_to_remove = []
    if not condition:
        # Return all IOC projects when no condition specified.
        if verbose:
            print(f'No condition specified, list all IOC projects.')
    elif isinstance(condition, list):
        valid_flag = False  # flag to check whether any valid condition has been given.
        valid_condition = []
        for c in condition:
            key, value = condition_parse(c)
            # only valid condition was parsed to filter IOC.
            if key:
                valid_flag = True
                valid_condition.append(c)
                if key.lower() == 'name':
                    for i in range(0, len(ioc_list)):
                        if value not in ioc_list[i].name:
                            index_to_remove.append(i)
                else:
                    for i in range(0, len(ioc_list)):
                        if not ioc_list[i].check_config(key, value, section):
                            index_to_remove.append(i)
            else:
                if verbose:
                    print(f'Skip invalid condition "{c}".')
        if valid_flag:
            if verbose:
                print(f'Results for filter with parameter: section="{section}", condition="{valid_condition}".')
        else:
            # Do not return any result if no valid condition given.
            index_to_remove = [i for i in range(0, len(ioc_list))]
            if verbose:
                print(f'No result. No valid condition given.')
    else:
        raise IMValueError(f'Invalid filter parameter: condition="{condition}".')

    # get index to print.
    index_reserved = []
    for i in range(0, len(ioc_list)):
        if i in index_to_remove:
            continue
        else:
            index_reserved.append(i)
    # print results.
    ioc_print = []
    panel_print = [["IOC", "Host", "State", "Status", "DeployStatus", "ExportConsistency"], ]
    for i in index_reserved:
        if show_info:
            ioc_list[i].show_config()
        elif show_panel:
            temp_service = SwarmService(name=ioc_list[i].name, service_type='ioc')
            panel_print.append([ioc_list[i].name, ioc_list[i].get_config("host"), ioc_list[i].get_config("state"),
                                ioc_list[i].get_config("status"), temp_service.current_state,
                                ioc_list[i].check_consistency(print_info=False)[1]])
        else:
            ioc_print.append(ioc_list[i].name)
    else:
        if show_info:
            pass
        elif show_panel:
            print(tabulate(panel_print, headers="firstrow", tablefmt='plain'))
        else:
            print(' '.join(ioc_print))


def execute_ioc(args):
    # operation outside IOC projects.
    if args.gen_swarm_file:
        gen_swarm_files(iocs=args.name, verbose=args.verbose)
    elif args.gen_backup_file:
        repository_backup(backup_mode=args.backup_mode, backup_dir=args.backup_path, verbose=args.verbose)
    elif args.restore_backup_file:
        restore_backup(backup_path=args.restore_backup_file, force_overwrite=args.force_overwrite,
                       verbose=args.verbose)
    elif args.run_check:
        if args.name:
            for name in args.name:
                dir_path = os.path.join(IMConfig.REPOSITORY_PATH, name)
                if os.path.exists(os.path.join(dir_path, IMConfig.IOC_CONFIG_FILE)):
                    ioc_temp = IOC(dir_path=dir_path, verbose=args.verbose)
                    ioc_temp.project_check(print_info=True)
                else:
                    print(f'execute_ioc: Failed. IOC "{name}" not found.')
        else:
            for ioc_temp in get_all_ioc():
                ioc_temp.project_check()
    else:
        # operation inside IOC projects.
        if not args.name:
            print(f'execute_ioc: No IOC project specified.')
        else:
            for name in args.name:
                dir_path = os.path.join(IMConfig.REPOSITORY_PATH, name)
                if os.path.exists(os.path.join(dir_path, IMConfig.IOC_CONFIG_FILE)):
                    if args.verbose:
                        print(f'execute_ioc: dealing with IOC "{name}".')
                    ioc_temp = IOC(dir_path=dir_path, verbose=args.verbose)
                    if isinstance(args.add_src_file, str):
                        if args.verbose:
                            print(f'execute_ioc: adding source file.')
                        ioc_temp.get_src_file(src_dir=args.add_src_file, print_info=True)
                    elif args.generate_and_export:
                        if args.verbose:
                            print(f'execute_ioc: generating startup files.')
                        ioc_temp.generate_startup_files()
                        if args.verbose:
                            print(f'execute_ioc: exporting startup files.')
                        ioc_temp.export_for_mount(force_overwrite=args.force_overwrite)
                    elif args.gen_startup_file:
                        if args.verbose:
                            print(f'execute_ioc: generating startup files.')
                        ioc_temp.generate_startup_files()
                    elif args.export_for_mount:
                        if args.verbose:
                            print(f'execute_ioc: exporting startup files.')
                        ioc_temp.export_for_mount(force_overwrite=args.force_overwrite)
                    elif args.restore_snapshot_file:
                        if args.verbose:
                            print(f'execute_ioc: restoring snapshot file.')
                        ioc_temp.restore_from_snapshot_files(restore_files=args.restore_snapshot_file,
                                                             force_restore=args.force_overwrite)
                    elif args.deploy:
                        if args.verbose:
                            print(f'execute_ioc: generating startup files.')
                        ioc_temp.generate_startup_files()
                        if args.verbose:
                            print(f'execute_ioc: exporting startup files.')
                        ioc_temp.export_for_mount(force_overwrite=args.force_overwrite)
                        if ioc_temp.check_config('host', 'swarm'):
                            if args.verbose:
                                print(f'execute_ioc: generating swarm file.')
                            gen_swarm_files(iocs=list([ioc_temp.name, ]), verbose=args.verbose)
                        else:
                            if args.verbose:
                                print(f'execute_ioc: generating compose file.')
                    else:
                        if args.verbose:
                            print(f'execute_ioc: No "exec" operation specified.')
                        break  # break to avoid repeat print of "no exec" operation.
                else:
                    print(f'execute_ioc: Failed. IOC "{name}" not found.')
            else:
                if args.verbose:
                    print('')


def execute_swarm(args):
    if args.gen_built_in_services:
        SwarmManager.gen_global_services(mount_dir=f'{os.path.join(get_manager_path(), "..")}')
        SwarmManager.gen_local_services(mount_dir=f'{os.path.join(get_manager_path(), "..")}')
    elif args.deploy_global_services:
        SwarmManager().deploy_global_services()
    elif args.deploy_all_iocs:
        SwarmManager().deploy_all_iocs()
    elif args.remove_global_services:
        SwarmManager().remove_global_services()
    elif args.remove_all_iocs:
        SwarmManager().remove_all_iocs()
    elif args.remove_all_services:
        SwarmManager().remove_all_services()
    elif args.show_digest:
        SwarmManager().show_info()
    elif args.show_services:
        if args.detail:
            SwarmManager.show_deployed_services_detail()
        else:
            SwarmManager.show_deployed_services()
    elif args.show_nodes:
        SwarmManager.show_deployed_machines(show_detail=args.detail)
    elif args.show_tokens:
        SwarmManager.show_join_tokens()
    elif args.list_managed_services:
        print(SwarmManager().list_managed_services())
    elif args.backup_swarm:
        SwarmManager.backup_swarm()
    elif args.restore_swarm:
        SwarmManager.restore_swarm(args.backup_file)
    elif args.update_deployed_services:
        SwarmManager().update_deployed_services()


def execute_service(args):
    # operation for specified IOC projects.
    if not args.name:
        print(f'execute_service: No IOC project specified.')
    else:
        services_dict = SwarmManager().services
        for name in args.name:
            # set service_type automatically
            if not args.type:
                if name in services_dict.keys():
                    temp_service = SwarmService(name, service_type=services_dict[name].service_type)
                else:
                    temp_service = SwarmService(name, service_type='custom')
            else:
                temp_service = SwarmService(name, service_type=args.type)
            #
            if args.deploy:
                temp_service.deploy()
            elif args.remove:
                temp_service.remove()
            elif args.show_config:
                temp_service.show_info()
            elif args.show_info:
                temp_service.show_ps()
            elif args.show_logs:
                temp_service.show_logs()
            elif args.update:
                temp_service.update()


def gen_swarm_files(iocs, verbose):
    """
    Generate Docker Compose file for swarm deploying at swarm data dir for specified IOC projects.

    :param iocs: IOC projects specified to generate compose file.
    :param verbose:
    """
    if verbose:
        print(f'gen_swarm_files: Processing with iocs="{iocs}", verbosity="{verbose}".')

    if not iocs:
        print(f'gen_swarm_files: Failed. No IOC project specified.')
        return

    top_path = os.path.join(IMConfig.MOUNT_PATH, IMConfig.SWARM_DIR)
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
        ioc_ini_path = os.path.join(service_path, IMConfig.IOC_CONFIG_FILE)
        if not os.path.exists(ioc_ini_path):
            if verbose:
                print(f'gen_swarm_files: Skip directory "{service_dir}" as there is no valid IOC config file.')
            continue
        try:
            temp_ioc = IOC(dir_path=service_path, read_mode=True, verbose=verbose)
            if not temp_ioc.get_config(section='IOC', option='image'):
                print(f'gen_swarm_files: Warning. No image defined in settings of IOC "{service_dir}", skipped.')
                continue
            else:
                ioc_settings['image'] = temp_ioc.get_config(section='IOC', option='image')
            if not temp_ioc.get_config(section='DEPLOY', option='cpu-reserve'):
                ioc_settings['cpu-reserve'] = ''
            else:
                ioc_settings['cpu-reserve'] = temp_ioc.get_config(section='DEPLOY', option='cpu-reserve')
            if not temp_ioc.get_config(section='DEPLOY', option='memory-reserve'):
                ioc_settings['memory-reserve'] = ''
            else:
                ioc_settings['memory-reserve'] = temp_ioc.get_config(section='DEPLOY', option='memory-reserve')
            if not temp_ioc.get_config(section='DEPLOY', option='cpu-limit'):
                ioc_settings['cpu-limit'] = IMConfig.RESOURCE_IOC_CPU_LIMIT
            else:
                ioc_settings['cpu-limit'] = temp_ioc.get_config(section='DEPLOY', option='cpu-limit')
            if not temp_ioc.get_config(section='DEPLOY', option='memory-limit'):
                ioc_settings['memory-limit'] = IMConfig.RESOURCE_IOC_MEMORY_LIMIT
            else:
                ioc_settings['memory-limit'] = temp_ioc.get_config(section='DEPLOY', option='memory-limit')
            # resources reservations
            reservations_dict = {}
            if ioc_settings['cpu-reserve']:
                reservations_dict['cpus'] = ioc_settings['cpu-reserve']
            if ioc_settings['memory-reserve']:
                reservations_dict['memory'] = ioc_settings['memory-reserve']
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
            'networks': ['hostnet'],
            'volumes': [
                {
                    'type': 'bind',
                    'source': f'../{ioc_settings["service_dir"]}',
                    'target': f'{os.path.join(IMConfig.CONTAINER_IOC_RUN_PATH, ioc_settings["service_dir"])}',
                },
                {
                    'type': 'bind',
                    'source': f'.',
                    'target': f'{os.path.join(IMConfig.CONTAINER_IOC_RUN_PATH, IMConfig.LOG_FILE_DIR)}',
                },
                {
                    'type': 'bind',
                    'source': '/etc/localtime',
                    'target': '/etc/localtime',
                    'read_only': True
                },  # set correct timezone for linux kernel
            ],
            'deploy': {
                'labels':
                    {
                        'service-type': 'ioc',
                    },
                'replicas': 1,
                'update_config':
                    {
                        'parallelism': 1,
                        'delay': '10s',
                        'failure_action': 'rollback',
                    },
                'resources':
                    {
                        'limits': {
                            'cpus': ioc_settings['cpu-limit'],
                            'memory': ioc_settings['memory-limit'],
                        },
                    }
            }
        }
        # reservations dict.
        if reservations_dict:
            temp_yaml['deploy']['resources']['reservations'] = reservations_dict
        # labels dict
        if labels_to_add:
            temp_yaml['deploy']['labels'].update(labels_to_add)
        #
        yaml_data['services'].update({f'srv-{ioc_settings["service_dir"]}': temp_yaml})
        # add network for each stack.
        temp_yaml = {
            'external': True,
            'name': 'host',
        }
        yaml_data['networks'].update({f'hostnet': temp_yaml})
        # write yaml file
        file_path = os.path.join(top_path, service_dir, IMConfig.IOC_SERVICE_FILE)
        if os.path.exists(file_path):
            if verbose:
                print(f'gen_swarm_files: File "{file_path}" exists, firstly remove it before writing a new one.')
            file_remove(file_path, verbose)
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
            else:
                if not iocs:
                    print(f'gen_swarm_files: No IOC project was specified to generate compose file!')


# Generate backup file of IOC project settings.
# backup_mode: "src" will only copy .ini file and source files; "all" backup all files.
# backup_dir: top dir for IOC_BACKUP_DIR.
def repository_backup(backup_mode, backup_dir, verbose):
    ioc_list = get_all_ioc()
    backup_path = relative_and_absolute_path_to_abs(backup_dir, IMConfig.IOC_BACKUP_DIR)  # default path ./ioc-backup/
    # collect ioc.ini files and source files into tar.gz file.
    if not os.path.exists(backup_path):
        try_makedirs(backup_path, verbose)
    now_time = datetime.datetime.now().strftime("%Y%m%d%H%M%S")
    tar_dir = os.path.join(backup_path, now_time)
    if ioc_list:
        for ioc_item in ioc_list:
            # make temporary directory.
            ioc_tar_dir = os.path.join(tar_dir, ioc_item.name)
            try_makedirs(ioc_tar_dir, verbose)
            # copy entire repository file into tar directory.
            file_copy(ioc_item.config_file_path, os.path.join(ioc_tar_dir, IMConfig.IOC_CONFIG_FILE), mode='rw',
                      verbose=verbose)
            dir_copy(ioc_item.src_path, os.path.join(ioc_tar_dir, 'src'), verbose=verbose)
            if backup_mode == 'all':
                dir_copy(ioc_item.startup_path, os.path.join(ioc_tar_dir, 'startup'), verbose=verbose)
                ######
                ioc_run_path = os.path.join(get_manager_path(), '..', IMConfig.MOUNT_DIR, ioc_item.get_config('host'),
                                            ioc_item.name)
                dir_copy(os.path.join(ioc_run_path, 'log'), os.path.join(ioc_tar_dir, 'log'), verbose=verbose)
                dir_copy(os.path.join(ioc_run_path, 'settings'), os.path.join(ioc_tar_dir, 'settings'),
                         verbose=verbose)
        else:
            with tarfile.open(os.path.join(backup_path, f'{now_time}.ioc.tar.gz'), "w:gz") as tar:
                tar.add(tar_dir, arcname=os.path.basename(tar_dir))
            dir_remove(tar_dir, verbose=verbose)
            print(f'repository_backup: Finished. Backup file created at {backup_path} in "{backup_mode}" mode.')
    else:
        print(f'repository_backup: No IOC project to backup.')


# Restore IOC projects from tgz backup file.
# backup_path: path of the tgz backup file.
# force_overwrite: "True" force overwrite when existing IOC project if conflicts with the backup file.
def restore_backup(backup_path, force_overwrite, verbose):
    extract_path = relative_and_absolute_path_to_abs(backup_path)
    if not os.path.isfile(extract_path):
        print(f'restore_backup: Failed. File to extract "{extract_path}" is not exists.')
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
        print(f'restore_backup: Restoring from backup file "{os.path.basename(temp_in_dir)}".')

    try:
        # copy IOC projects. if IOC conflicts, just skip or overwrite.
        ioc_existed = [ioc_item.name for ioc_item in get_all_ioc()]
        for ioc_item in os.listdir(temp_in_dir):
            ioc_dir = os.path.join(temp_in_dir, ioc_item)
            current_path = os.path.join(IMConfig.REPOSITORY_PATH, ioc_item)
            restore_flag = False
            if os.path.isdir(ioc_dir) and os.path.exists(os.path.join(ioc_dir, IMConfig.IOC_CONFIG_FILE)):
                if ioc_item not in ioc_existed:
                    print(f'restore_backup: Restoring IOC project "{ioc_item}".')
                    dir_copy(ioc_dir, current_path, verbose=verbose)
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
                        dir_copy(ioc_dir, current_path, verbose=verbose)
                        restore_flag = True
                else:
                    print(f'restore_backup: Restoring IOC project "{ioc_item}", local project will be overwrite.')
                    dir_copy(ioc_dir, current_path, verbose=verbose)
                    restore_flag = True
            else:
                if verbose:
                    print(f'restore_backup: Skip invalid directory "{ioc_item}".')
            if restore_flag:
                print(f'restore_backup: Restoring IOC project "{ioc_item}" finished.')
                temp_ioc = IOC(dir_path=current_path, verbose=verbose)
                # set status for restored IOC.
                temp_ioc.set_config('status', 'restored')
                temp_ioc.write_config()
    except Exception as e:
        # remove temporary directory finally.
        print(f'\nrestore_backup: {e}.')
        dir_remove(temp_dir, verbose=verbose)
    else:
        # remove temporary directory finally.
        print(f'restore_backup: Restoring Finished.')
        dir_remove(temp_dir, verbose=verbose)


# Update IOC project to the form of newer version.
def update_ioc(args):
    print(f'Starting to update IOC projects.')
    ioc_list = get_all_ioc()
    for ioc_item in ioc_list:
        create_ioc(f'{ioc_item.name}_temp', args, ioc_item.conf, args.verbose)
    for ioc_item in ioc_list:
        name = ioc_item.name
        ioc_item.remove(all_remove=True)
        rename_ioc(f'{name}_temp', name, verbose=args.verbose)
    print(f'Finished updating IOC projects.')


# Edit settings file for an IOC project using vi command.
def edit_ioc(args):
    name = args.name
    dir_path = os.path.join(IMConfig.REPOSITORY_PATH, name)
    file_path = os.path.join(dir_path, IMConfig.IOC_CONFIG_FILE)
    if args.verbose:
        print(f'edit_ioc: Edit file path: "{file_path}".')
    if os.path.exists(file_path):
        try:
            os.system(f'vi {file_path}')
        except Exception as e:
            if args.verbose:
                print(f'edit_ioc: Failed to edit, "{e}".')
    else:
        print(f'edit_ioc: Failed. IOC "{name}" not found.')


def execute_config(args):
    if args.set_value:
        print(f'execute_config: Failed, not implemented yet.')
    else:
        if hasattr(IMConfig, args.name):
            print(getattr(IMConfig, args.name))
        else:
            exit(10)


if __name__ == '__main__':
    class TESTV: pass


    argtest = TESTV()
    argtest.set_value = None
    argtest.name = 'REPOSITORY_PATH'
    execute_config(argtest)
    argtest.name = 'REPOSITORY_PATH1'
    execute_config(argtest)
