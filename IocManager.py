#!/usr/bin/python3

import random
import os.path
import argparse
import subprocess
import configparser

from imutils.IMConfig import get_manager_path, IOC_CONFIG_FILE, IOC_BACKUP_DIR, PREFIX_STACK_NAME
from imutils.IMFunc import operation_log, condition_parse
from imutils.IMUtil import create_ioc, set_ioc, get_filtered_ioc, remove_ioc, execute_ioc, rename_ioc, update_ioc, \
    execute_swarm, execute_service, edit_ioc, execute_config

if __name__ == '__main__':
    # argparse
    parser = argparse.ArgumentParser(description='Manager of IOC projects for docker deploying.',
                                     formatter_class=argparse.RawTextHelpFormatter)

    subparsers = parser.add_subparsers(
        help='For subparser command help, run "IocManager [create|set|exec|list|swarm|service|remove] -h".')

    #
    parser_create = subparsers.add_parser('create', help='Create IOC projects by given settings.',
                                          formatter_class=argparse.RawTextHelpFormatter)
    parser_create.add_argument('name', type=str, nargs='+', help='name for IOC project, a list of name is supported.')
    parser_create.add_argument('-o', '--options', type=str, nargs='+',
                               help=f'manually specify attributes in {IOC_CONFIG_FILE} file, format: "key=value".\n'
                                    f'attributes set by this option will override other options if conflicts.')
    parser_create.add_argument('-s', '--section', type=str, default='IOC',
                               help='specify section used for manually specified attributes.'
                                    '\ndefault: "IOC" ')
    parser_create.add_argument('-f', '--ini-file', type=str,
                               help=f'copy settings from specified {IOC_CONFIG_FILE} files.\n'
                                    f'attributes set by this option may be override by other options.')
    parser_create.add_argument('--caputlog', action="store_true", help='add caPutLog module.')
    parser_create.add_argument('--status-ioc', action="store_true",
                               help='add devIocStats module for IOC monitor.')
    parser_create.add_argument('--status-os', action="store_true",
                               help='add devIocStats module for OS monitor.')
    parser_create.add_argument('--autosave', action="store_true", help='add autosave module.')
    parser_create.add_argument('--add-asyn', action="store_true", help='add asyn template.\n')
    parser_create.add_argument('--add-stream', action="store_true", help='add StreamDevice template.\n')
    parser_create.add_argument('--add-raw', action="store_true",
                               help=f'add raw command template, so to add customized commands.')
    parser_create.add_argument('-v', '--verbose', action="store_true", help='show processing details.')
    parser_create.set_defaults(func='parse_create')

    #
    parser_set = subparsers.add_parser('set', help='Set attributes for IOC projects.',
                                       formatter_class=argparse.RawTextHelpFormatter)
    parser_set.add_argument('name', type=str, nargs='+', help='name for IOC project, a list of name is supported.')
    parser_set.add_argument('-o', '--options', type=str, nargs='+',
                            help=f'manually specify attributes in {IOC_CONFIG_FILE} file, format: "key=value".\n'
                                 f'attributes set by this option will override other options if conflicts.')
    parser_set.add_argument('-s', '--section', type=str, default='IOC',
                            help='specify section used for manually specified attributes.'
                                 '\ndefault: "IOC" ')
    parser_set.add_argument('-f', '--ini-file', type=str,
                            help=f'copy settings from specified {IOC_CONFIG_FILE} files.\n'
                                 f'attributes set by this option may be override by other options.')
    parser_set.add_argument('--caputlog', action="store_true", help='add caPutLog module.')
    parser_set.add_argument('--status-ioc', action="store_true",
                            help='add devIocStats module for IOC monitor.')
    parser_set.add_argument('--status-os', action="store_true",
                            help='add devIocStats module for OS monitor.')
    parser_set.add_argument('--autosave', action="store_true", help='add autosave module.')
    parser_set.add_argument('--add-asyn', action="store_true", help='add asyn template.\n')
    parser_set.add_argument('--add-stream', action="store_true", help='add StreamDevice template.\n')
    parser_set.add_argument('--add-raw', action="store_true",
                            help=f'add raw command template, so to add customized commands.')
    parser_set.add_argument('-v', '--verbose', action="store_true", help='show processing details.')
    parser_set.set_defaults(func='parse_set')

    #
    parser_execute = subparsers.add_parser('exec', help='Execute functions for IOC projects.',
                                           formatter_class=argparse.RawTextHelpFormatter)
    parser_execute.add_argument('name', type=str, nargs='*', help='name for IOC project, a list of name is supported.')
    # Sort by operation procedure.
    parser_execute.add_argument('--add-src-file', metavar="DIR_PATH", type=str, nargs='?', const='', default=None,
                                help='add source files from given path and update settings automatically.'
                                     '\ndefault: "src" directory in the project')
    parser_execute.add_argument('--gen-startup-file', action="store_true",
                                help='generate startup files for IOC project.')
    parser_execute.add_argument('--export-for-mount', action="store_true",
                                help='export generated startup files into running dir.'
                                     '\nset "--force-overwrite" to enable overwrite when project files in running dir '
                                     'conflicts with those in repository.')
    parser_execute.add_argument('--force-overwrite', action="store_true",
                                help='force overwrite when file conflicts or already exists.')
    parser_execute.add_argument('--generate-and-export', action="store_true",
                                help='generate startup files and then export them into running dir.'
                                     '\nset "--force-overwrite" to enable exporting overwrite when IOC in running dir '
                                     'conflicts with the one in repository.')
    parser_execute.add_argument('--gen-swarm-file', action="store_true",
                                help='generate docker service compose file of IOC projects for swarm deploying.')
    parser_execute.add_argument('--deploy', action="store_true",
                                help='generate and export startup files, then generate swarm file for deploying.'
                                     '\nset "--force-overwrite" to enable exporting overwrite when IOC in running dir '
                                     'conflicts with the one in repository.')
    parser_execute.add_argument('-b', '--gen-backup-file', action="store_true",
                                help='generate backup file, all IOC projects currently '
                                     'in the repository will be packed and compressed into a tgz file.'
                                     '\nset "--backup-path" to choose a directory to store backup file.'
                                     '\nset "--backup-mode" to choose a backup mode.')
    parser_execute.add_argument('--backup-path', type=str,
                                default=f'{os.path.join(get_manager_path(), "..", IOC_BACKUP_DIR)}',
                                help=f'path of directory used for storing backup files of IOC projects.'
                                     f'\ndefault: "$MANAGER_PATH/../{IOC_BACKUP_DIR}/" ')
    parser_execute.add_argument('--backup-mode', type=str, default='src',
                                help='backup mode for IOC projects.'
                                     '\n"all": back up all files including running files'
                                     '(files generated by autosave, etc.).'
                                     '\n"src": back up only config file and source files.'
                                     '\ndefault: "src" ')
    parser_execute.add_argument('-r', '--restore-backup-file', metavar="BACKUP_FILE", type=str,
                                help='restore IOC projects from tgz backup file into repository.'
                                     '\nset "--force-overwrite" to enable overwrite when IOC in backup file '
                                     'conflicts with the one in repository.')
    parser_execute.add_argument('--add-snapshot-file', action="store_true",
                                help='add snapshot file for current project files.')
    parser_execute.add_argument('--check-snapshot', action="store_true",
                                help='check differences between files in snapshot and repository.')
    parser_execute.add_argument('--restore-snapshot-file', metavar="SNAPSHOT_FILE", type=str, nargs='+',
                                help='restore IOC project files from snapshot.'
                                     '\nset "--force-overwrite" to enable overwrite when file in snapshot'
                                     'conflicts with the one in repository.')
    parser_execute.add_argument('--check-running', action="store_true",
                                help='check differences between files in running dir and repository.')
    parser_execute.add_argument('-v', '--verbose', action="store_true", help='show processing details.')
    parser_execute.set_defaults(func='parse_execute')

    #
    parser_list = subparsers.add_parser('list', help='List existing IOC projects filtered by given conditions.',
                                        formatter_class=argparse.RawTextHelpFormatter)
    parser_list.add_argument('condition', type=str, nargs='*',
                             help='conditions to filter IOC projects in specified section. format: "xxx=xxx".'
                                  '\nlist all IOC projects if no condition provided.')
    parser_list.add_argument('-s', '--section', type=str, default='IOC',
                             help='specify a section applied for condition filtering. default section: "IOC".')
    parser_list.add_argument('-l', '--list-from', type=str, nargs='*',
                             help='filter IOC projects by given conditions from given IOC list.')
    parser_list.add_argument('-i', '--show-info', action="store_true", help='show details of IOC.')
    parser_list.add_argument('-d', '--show-description', action="store_true", help='show description of IOC.')
    parser_list.add_argument('-p', '--show-panel', action="store_true", help='show panel of all managed IOC.')
    parser_list.add_argument('-v', '--verbose', action="store_true", help='show processing details.')
    parser_list.set_defaults(func='parse_list')

    #
    parser_swarm = subparsers.add_parser('swarm', help='Functions for managing swarm system.',
                                         formatter_class=argparse.RawTextHelpFormatter)
    parser_swarm.add_argument('--gen-built-in-services', action="store_true",
                              help='generate swarm deployment files of global and local services.')
    parser_swarm.add_argument('--deploy-global-services', action="store_true",
                              help='deploy all global services into running.')
    parser_swarm.add_argument('--deploy-all-iocs', action="store_true",
                              help='deploy all IOC projects that are available but not deployed into running.')
    parser_swarm.add_argument('--remove-global-services', action="store_true",
                              help='remove all deployed global services.')
    parser_swarm.add_argument('--remove-all-iocs', action="store_true",
                              help='remove all deployed ioc projects services.')
    parser_swarm.add_argument('--remove-all-services', action="store_true",
                              help='remove all deployed services including global services.')
    parser_swarm.add_argument('--show-digest', action="store_true",
                              help='show digest information of current swarm deploying.')
    parser_swarm.add_argument('--show-services', action="store_true",
                              help='show all service deployed in swarm.'
                                   '\nset "--detail" to show details.')
    parser_swarm.add_argument('--detail', action="store_true")
    parser_swarm.add_argument('--show-nodes', action="store_true",
                              help='show all nodes joined in swarm.'
                                   '\nset "--detail" to show details, such as node labels.')
    parser_swarm.add_argument('--show-tokens', action="store_true", help='show how to join into swarm for other nodes.')
    parser_swarm.add_argument('--list-managed-services', action="store_true",
                              help='list all managed swarm services.')
    parser_swarm.add_argument('-b', '--backup-swarm', action="store_true",
                              help='generate backup file of current swarm.'
                                   '\ndocker daemon of current manager will be paused for backup operation.')
    parser_swarm.add_argument('-r', '--restore-swarm', action="store_true",
                              help='restore swarm backup file into current machine.'
                                   '\nset "--backup-file" to choose the backup file to restore from.')
    parser_swarm.add_argument('--backup-file', type=str, default='', help='tgz backup file for swarm.')
    parser_swarm.add_argument('--update-deployed-services', action="store_true",
                              help='update all services deployed in swarm to force load balance.')
    parser_swarm.add_argument('-v', '--verbose', action="store_true", help='show processing details.')
    parser_swarm.set_defaults(func='parse_swarm')

    #
    parser_service = subparsers.add_parser('service', help='Functions for managing IOC service in swarm system.',
                                           formatter_class=argparse.RawTextHelpFormatter)
    parser_service.add_argument('name', type=str, nargs='+', help='name for IOC project, name list is supported.')
    parser_service.add_argument('--deploy', action="store_true", help='deploy service into running.')
    parser_service.add_argument('--type', type=str, default='',
                                help='service type, one of "ioc", "global", "local", "custom".'
                                     '\ndefault: "", let tool decide the type.')
    parser_service.add_argument('--remove', action="store_true", help='remove running service.')
    parser_service.add_argument('--show-config', action="store_true", help='show configuration of running service.')
    parser_service.add_argument('--show-info', action="store_true", help='show information of running service.')
    parser_service.add_argument('--show-logs', action="store_true", help='show logs of running service.')
    parser_service.add_argument('--update', action="store_true", help='restart running service.')
    parser_service.add_argument('-v', '--verbose', action="store_true", help='show processing details.')
    parser_service.set_defaults(func='parse_service')

    #
    parser_remove = subparsers.add_parser('remove', help='Remove IOC projects.',
                                          formatter_class=argparse.RawTextHelpFormatter)
    parser_remove.add_argument('name', type=str, nargs='+', help='name for IOC project, name list is supported.')
    parser_remove.add_argument('-r', '--remove-all', action="store_true",
                               help='enable this option will delete the entire IOC project!')
    parser_remove.add_argument('-f', '--force', action="store_true", help='force removal, do not ask.')
    parser_remove.add_argument('-v', '--verbose', action="store_true", help='show processing details.')
    parser_remove.set_defaults(func='parse_remove')

    #
    parser_rename = subparsers.add_parser('rename', help='Rename IOC project.',
                                          formatter_class=argparse.RawTextHelpFormatter)
    parser_rename.add_argument('name', type=str, nargs=2,
                               help='only accept 2 arguments, old name and new name of the IOC project.')
    parser_rename.add_argument('-v', '--verbose', action="store_true", help='show processing details.')
    parser_rename.set_defaults(func='parse_rename')

    #
    parser_update = subparsers.add_parser('update', help='Update IOC project to the form of newer version.',
                                          formatter_class=argparse.RawTextHelpFormatter)
    parser_update.add_argument('-v', '--verbose', action="store_true", help='show processing details.')
    parser_update.set_defaults(func='parse_update')

    #
    parser_edit = subparsers.add_parser('edit', help='Edit configuration file of an IOC project using vi.',
                                        formatter_class=argparse.RawTextHelpFormatter)
    parser_edit.add_argument('name', type=str, help='name of the IOC project.')
    parser_edit.add_argument('-v', '--verbose', action="store_true", help='show processing details.')
    parser_edit.set_defaults(func='parse_edit')

    #
    parser_config = subparsers.add_parser('config', help='Functions for managing configurations in swarm system.',
                                          formatter_class=argparse.RawTextHelpFormatter)
    parser_config.add_argument('name', type=str, help='name of configurations.')
    parser_config.add_argument('-s', '--set-value', type=str,
                               help='values to set for given configuration.'
                                    '\nget operation implied when not specifying this option.')
    parser_config.add_argument('-v', '--verbose', action="store_true", help='show processing details.')
    parser_config.set_defaults(func='parse_config')

    #
    parser_config = subparsers.add_parser('client', help='Call EPICS client library to connect PV in swarm.',
                                          formatter_class=argparse.RawTextHelpFormatter)
    parser_config.add_argument('cmd', type=str, help='command.')
    parser_config.add_argument('arguments', type=str, nargs='*', help='arguments.')
    parser_config.set_defaults(func='parse_client')

    args = parser.parse_args()
    if not any(vars(args).values()):
        parser.print_help()
        exit()

    # log current operation.
    try:
        operation_log()
    except Exception as e:
        print(f'IocManager: Failed to execute operation_log(), {e}')

    # print(f'{args}')
    if not hasattr(args, 'verbose'):
        args.verbose = False
    if args.verbose:
        print(args)
    if args.func == 'parse_create' or args.func == 'parse_set':
        # ./iocManager.py create or ./iocManager.py set
        conf_temp = configparser.ConfigParser()
        #
        if args.ini_file:
            if args.verbose:
                print(f'ArgumentParser: Read configuration from file "{args.ini_file}".')
            if not conf_temp.read(args.ini_file):
                print(f'ArgumentParser: skip invalid file "{args.ini_file}".')
        #
        module_installed = ''
        if args.autosave:
            module_installed += 'autosave, '
        if args.caputlog:
            module_installed += 'caputlog, '
        if args.status_ioc:
            module_installed += 'status-ioc, '
        if args.status_os:
            module_installed += 'status-os, '
        module_installed = module_installed.rstrip(', ')
        if module_installed:
            if not conf_temp.has_section('IOC'):
                conf_temp.add_section('IOC')
            conf_temp.set('IOC', 'module', module_installed)
        #
        if args.options:
            if args.verbose:
                print(f'ArgumentParser: Read configuration from specified options.')
            args.section = args.section.upper()
            if not conf_temp.has_section(args.section):
                conf_temp.add_section(args.section)
            for item in args.options:
                k, v = condition_parse(item, split_once=True)
                if k:
                    conf_temp.set(args.section, k, v)
                else:
                    if args.verbose:
                        print(f'skip invalid option "{item}".')
        #
        if args.verbose:
            if conf_temp.sections():
                print(f'ArgumentParser: Configurations parsed.')
                print('//-----------------------------')
            for sec in conf_temp.sections():
                print(f"[{sec}]")
                for key, value in conf_temp.items(sec):
                    print(f"{key} = {value}")
            else:
                print('-----------------------------//')
        #
        if args.func == 'parse_create':
            # ./iocManager.py create
            create_ioc(args.name, args, config=conf_temp, verbose=args.verbose)
        else:
            # ./iocManager.py set
            set_ioc(args.name, args, config=conf_temp, verbose=args.verbose)
    if args.func == 'parse_list':
        # ./iocManager.py list
        get_filtered_ioc(args.condition, section=args.section, from_list=args.list_from, show_info=args.show_info,
                         show_description=args.show_description, show_panel=args.show_panel, verbose=args.verbose)
    if args.func == 'parse_remove':
        # ./iocManager.py remove
        for item in args.name:
            remove_ioc(item, remove_all=args.remove_all, force_removal=args.force, verbose=args.verbose)
    if args.func == 'parse_execute':
        # ./iocManager.py exec
        execute_ioc(args)
    if args.func == 'parse_rename':
        # ./iocManager.py rename
        rename_ioc(args.name[0], args.name[1], args.verbose)
    if args.func == 'parse_update':
        # ./iocManager.py update
        update_ioc(args)
    if args.func == 'parse_swarm':
        # ./iocManager.py swarm
        execute_swarm(args)
    if args.func == 'parse_service':
        # ./iocManager.py service
        execute_service(args)
    if args.func == 'parse_edit':
        # ./iocManager.py edit
        edit_ioc(args)
    if args.func == 'parse_config':
        # ./iocManager.py config
        execute_config(args)
    if args.func == 'parse_client':
        # ./iocManager.py client
        result = subprocess.run(
            ['docker', 'ps', '--format', '{{.ID}}',
             '--filter', f'label=com.docker.swarm.service.name={PREFIX_STACK_NAME}_srv-client', ],
            capture_output=True,
            text=True
        )
        if result.stderr:
            print(f'Failed. Exit code "{result.returncode}". {result.stderr}.')
            exit(1)
        if not result.stdout:
            print(f'Failed. Container that matches '
                  f'label="com.docker.swarm.service.name={PREFIX_STACK_NAME}_srv-client" was not running.')
            exit(1)
        container_list = list(filter(None, result.stdout.split('\n')))
        arguments = ' '.join(args.arguments)
        cmd_str = f'docker exec {random.choice(container_list)} ./{args.cmd} {arguments}'
        print(f'executing "{cmd_str}".')
        os.system(cmd_str)
    if args.verbose:
        print()
