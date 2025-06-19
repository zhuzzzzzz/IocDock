import os
from tabulate import tabulate
from collections.abc import Iterable

import imutils.IMConfig as IMConfig
from imutils.IMError import IMValueError
from imutils.IocClass import IOC, gen_swarm_files, get_all_ioc, repository_backup, restore_backup
from imutils.SwarmClass import SwarmManager, SwarmService
from imutils.IMFunc import try_makedirs, condition_parse


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
                    print(f'create_ioc: add asyn template to IOC "{name}".')
            if hasattr(args, 'add_stream') and args.add_stream:
                ioc_temp.add_module_template('stream')
                if verbose:
                    print(f'create_ioc: add stream template to IOC "{name}".')
            if hasattr(args, 'add_raw') and args.add_raw:
                ioc_temp.add_raw_cmd_template()
                if verbose:
                    print(f'create_ioc: add raw command template to IOC "{name}".')
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
                        value = config.get(section, option)
                        ioc_temp.set_config(option, value, section)
                else:
                    ioc_temp.write_config()
            print(f'create_ioc: Success. IOC "{name}" created.')
    elif isinstance(name, Iterable):
        for n in name:
            create_ioc(n, args, config=config, verbose=verbose)
    else:
        raise IMValueError(f'Invalid parameter name="{name}".')


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
                        print(f'set_ioc: add asyn template to IOC "{name}".')
            if args.add_stream:
                if ioc_temp.add_module_template('stream'):
                    modify_flag = True
                    if verbose:
                        print(f'set_ioc: add stream template to IOC "{name}".')
            if args.add_raw:
                if ioc_temp.add_raw_cmd_template():
                    modify_flag = True
                    if verbose:
                        print(f'set_ioc: add raw command template to IOC "{name}".')
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
                    print(f'set_ioc: No applicable setting given to IOC "{name}".')
    elif isinstance(name, Iterable):
        for n in name:
            set_ioc(n, args, config=config, verbose=verbose)
    else:
        raise IMValueError(f'Invalid parameter name="{name}".')


# do not accept iterable for input
# Remove IOC projects. just remove generated files or remove all files.
def remove_ioc(name, remove_all=False, force_removal=False, verbose=False):
    dir_path = os.path.join(IMConfig.REPOSITORY_PATH, name)
    if os.path.exists(os.path.join(dir_path, IMConfig.IOC_CONFIG_FILE)):
        if not force_removal:
            if remove_all:
                print(f'remove_ioc: IOC "{name}" will be removed completely, '
                      f'project files in running dir(if exist) will also be removed. Be careful!', end='')
            else:
                print(f'remove_ioc: IOC "{name}" will be removed, the files in repository will be removed.',
                      end='')
            ans = input(f'Continue?[y|n]:')
            if ans.lower() == 'y' or ans.lower() == 'yes':
                force_removal = True
            elif ans.lower() == 'n' or ans.lower() == 'no':
                print(f'remove_ioc: Remove canceled.')
            else:
                print(f'remove_ioc: Failed. Invalid input, remove canceled.')
        if force_removal:
            ioc_temp = IOC(dir_path=dir_path, verbose=verbose)
            ioc_temp.remove(all_remove=remove_all)
    else:
        print(f'remove_ioc: Failed. IOC "{name}" not found.')


# do not accept iterable for input
def rename_ioc(old_name, new_name, verbose):
    dir_path = os.path.join(IMConfig.REPOSITORY_PATH, old_name)
    if os.path.exists(os.path.join(dir_path, IMConfig.IOC_CONFIG_FILE)):
        ioc_temp = IOC(dir_path=dir_path, verbose=verbose)
        ioc_temp.set_config('name', new_name)
        ioc_temp.write_config()
        try:
            os.rename(dir_path, os.path.join(IMConfig.REPOSITORY_PATH, new_name))
        except Exception as e:
            print(f'rename_ioc: Failed. Changing directory name failed, "{e}".')
        else:
            print(f'rename_ioc: Success. IOC name changed from "{old_name}" to "{new_name}".')
    else:
        print(f'rename_ioc: Failed. IOC "{old_name}" not found.')


def get_filtered_ioc(condition: list, section='IOC', from_list=None, show_info=False, show_description=False,
                     show_panel=False, verbose=False):
    """
    Filter and List IOC projects by specified conditions and section. Logic "AND" is used between each condition.

    :param condition: filter conditions such as ["a=b", "c=d"]
    :param section: filter on given section in config file
    :param from_list: filter from given IOC list
    :param show_info: show IOC configurations
    :param show_description: show IOC description
    :param show_panel: show IOC management panel
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
                elif key.lower() in ('state', 'status', 'snapshot', 'is_exported'):
                    for i in range(0, len(ioc_list)):
                        if not ioc_list[i].state_manager.check_config(key, value):
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
    description_print = [["IOC", "Description"], ]
    panel_print = [["IOC", "Host", "Description", "State", "Status",
                    "DeployStatus", "SnapshotConsistency", "RuningConsistency"], ]
    for i in index_reserved:
        if show_info:
            ioc_list[i].show_config()
        elif show_panel:
            desc = ioc_list[i].get_config("description")
            if len(desc) > 37:
                desc = desc[:37] + '...'
            temp_service = SwarmService(name=ioc_list[i].name, service_type='ioc')
            panel_print.append([ioc_list[i].name, ioc_list[i].get_config("host"),
                                desc,
                                ioc_list[i].state_manager.get_config("state"),
                                ioc_list[i].state_manager.get_config("status"),
                                temp_service.current_state,
                                ioc_list[i].check_snapshot_consistency(print_info=False)[1],
                                ioc_list[i].check_running_consistency(print_info=False)[1],
                                ])
        elif show_description:
            desc = ioc_list[i].get_config("description")
            if len(desc) > 100:
                desc = desc[:80] + '...'
            description_print.append([ioc_list[i].name, desc])
        else:
            ioc_print.append(ioc_list[i].name)
    else:
        if show_info:
            pass
        elif show_description:
            print(tabulate(description_print, headers="firstrow", tablefmt='plain'))
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
    else:
        # operation inside IOC projects.
        if not args.name:
            print(f'execute_ioc: No IOC project specified.')
        else:
            for name in args.name:
                dir_path = os.path.join(IMConfig.REPOSITORY_PATH, name)
                if os.path.isdir(dir_path):
                    ioc_temp = IOC(dir_path=dir_path, verbose=args.verbose)
                    if isinstance(args.add_src_file, str):
                        ioc_temp.get_src_file(src_dir=args.add_src_file, print_info=True)
                    elif args.generate_and_export:
                        ioc_temp.generate_startup_files()
                        ioc_temp.export_for_mount(force_overwrite=args.force_overwrite)
                    elif args.gen_startup_file:
                        ioc_temp.generate_startup_files()
                    elif args.export_for_mount:
                        ioc_temp.export_for_mount(force_overwrite=args.force_overwrite)
                    elif args.add_snapshot_file:
                        ioc_temp.add_snapshot_files()
                    elif args.check_snapshot:
                        ioc_temp.check_snapshot_consistency(print_info=True)
                    elif args.restore_snapshot_file:
                        ioc_temp.restore_from_snapshot_files(restore_files=args.restore_snapshot_file,
                                                             force_restore=args.force_overwrite)
                    elif args.deploy:
                        ioc_temp.generate_startup_files()
                        ioc_temp.export_for_mount(force_overwrite=args.force_overwrite)
                        gen_swarm_files(iocs=list([ioc_temp.name, ]), verbose=args.verbose)
                    elif args.check_running:
                        ioc_temp.check_running_consistency(print_info=True)
                    else:
                        print(f'execute_ioc: No execution operation specified.')
                        break  # break to avoid repeat print of no exec operation.
                else:
                    print(f'execute_ioc: Failed. IOC "{name}" not found.')


def execute_swarm(args):
    if args.gen_built_in_services:
        SwarmManager.gen_global_services(verbose=args.verbose)
        SwarmManager.gen_local_services(verbose=args.verbose)
    elif args.deploy_global_services:
        SwarmManager(verbose=args.verbose).deploy_global_services()
    elif args.deploy_all_iocs:
        SwarmManager(verbose=args.verbose).deploy_all_iocs()
    elif args.remove_global_services:
        SwarmManager(verbose=args.verbose).remove_global_services()
    elif args.remove_all_iocs:
        SwarmManager(verbose=args.verbose).remove_all_iocs()
    elif args.remove_all_services:
        SwarmManager(verbose=args.verbose).remove_all_services()
    elif args.show_digest:
        SwarmManager(verbose=args.verbose).show_info()
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
        print(SwarmManager.list_managed_services())
    elif args.backup_swarm:
        SwarmManager.backup_swarm()
    elif args.restore_swarm:
        SwarmManager.restore_swarm(args.backup_file)
    elif args.update_deployed_services:
        SwarmManager(verbose=args.verbose).update_deployed_services()


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


# Edit configuration file of an IOC project using vi.
def edit_ioc(args):
    file_path = os.path.join(IMConfig.REPOSITORY_PATH, args.name, IMConfig.IOC_CONFIG_FILE)
    if args.verbose:
        print(f'edit_ioc: Edit file "{file_path}".')
    if os.path.exists(file_path):
        try:
            os.system(f'vi {file_path}')
        except Exception as e:
            print(f'edit_ioc: Failed, "{e}".')
    else:
        print(f'edit_ioc: Failed, IOC "{args.name}" not found.')


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
