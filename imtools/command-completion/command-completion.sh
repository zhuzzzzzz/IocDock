#!/bin/bash

# pipe and xargs will not influence command completion.

_mycommand_completion() {

	# echo $1 $2 $3 
	# $1 : command
	# $2 : current word
	# $3 : previous word

	#
	prompt="" 
	option_set_first=""
	option_set_last=""
	
	# 
	sub_command_opts="create set exec list swarm service remove rename"
	#
	create_prompt="--options --section --ini-file --caputlog --status-ioc --status-os --autosave --add-asyn --add-stream --add-raw --print-ioc --verbose --help"
	_options_prompt="host= image= bin= description= load_=  epics_env_= report_info=true report_info=false caputlog_json=true caputlog_json=false "
	_section_prompt="DB SETTING ASYN STREAM RAW"
	_port_type_prompt="tcp/ip serial"
	#
	exec_prompt="--verbose --help" # general prompt for all exec commands.
	exec_ioc_prompt="--gen-startup-file --export-for-mount --add-src-file" # exec commands for specified IOC projects.
	_backup_mode_prompt="src all"
	#
	list_prompt="--section --ioc-list --show-info --raw-info --verbose --help"
	_condition_type_prompt="name= host= status=created status=generated status=exported snapshot=logged snapshot=changed"
	#
	remove_prompt="--remove-all --force --verbose --help"
	#
	rename_prompt="--verbose --help"
	#
	swarm_prompt="--gen-global-compose-file --deploy-global-services --deploy-all-iocs --remove-all-services --show-digest --show-services --show-nodes --show-tokens --backup-swarm --restore-swarm --update-deployed-services --verbose --help"
	#
	service_prompt="--deploy --remove --show-config --show-info --show-logs --update --verbose --help"
	
	#
	image_prefix="image.dals/"


	# sub-commands completion.( 2nd position )
	if [ $COMP_CWORD -eq 1 ]; then  
		COMPREPLY=( $(compgen -W "${sub_command_opts}" -- $2) )  
		return 0  
	fi

	# get ioc list.
	if [ -d "$REPOSITORY_PATH" ]; then 
		ioc_list=$(ls $REPOSITORY_PATH)   
	else
		ioc_list="" 
	fi	

	# sub-command options completion( 3rd position ).
	if [ $COMP_CWORD -eq 2 ]; then
		case "$3" in 
			"create")
			prompt="" # "create" should specify an IOC project firstly.
			prompt="$ioc_list $prompt"
			;;
			"set")
			prompt="" # "set" should specify an IOC project firstly.
			prompt="$ioc_list $prompt"
			;;
			"exec") # "exec" should specify an IOC project firstly or specify the commands that are to all IOC projects.
			prompt="--gen-compose-file --gen-backup-file --restore-backup-file --run-check --verbose --help"
			prompt="$ioc_list $prompt"
			;;
			"list")
			prompt="$list_prompt $_condition_type_prompt"
			;;
			"remove")
			prompt="" # "remove" should specify an IOC project firstly.
			prompt="$ioc_list $prompt"
			;;
			"rename")
			prompt="" # "rename" should specify an IOC project firstly.
			prompt="$ioc_list $prompt"
			;;
			"swarm")
			prompt="$swarm_prompt"
			;;
			"service")
			prompt="" # "service" should specify an IOC project firstly.
			prompt="$ioc_list $prompt"
			;;
			*)
			return 1
		esac
		COMPREPLY=( $(compgen -W "${prompt}" -- $2) )
		return 0  
	fi

	# options completion( 4th or later ).
	if [ $COMP_CWORD -gt 2 ]; then
		
		# echo "${COMP_WORDS[@]}"
		# echo  ${#COMP_WORDS[@]}

		# check whether any option was set(before the current word).
		ioc_list_temp=$ioc_list
		exec_ioc_prompt_temp=$exec_ioc_prompt
		_condition_type_prompt_temp=$_condition_type_prompt
		service_prompt_temp=$service_prompt
		for (( i=0; i<$((${#COMP_WORDS[@]}-1)); i++)); do
			case ${COMP_WORDS[$i]} in
				-*)
				option_set_first=${COMP_WORDS[$i]} # get that first option.
				ioc_list_temp="" # ioc projects will not be prompted. used for "create" "set" "exec" "remove", etc. 
				exec_ioc_prompt_temp="" # commands for specified IOC projects will not be prompted, otherwise those should be prompt. used for "exec". 
				_condition_type_prompt_temp="" # conditions will not be prompted. used for "list".
				service_prompt_temp="--verbose --help"
				break
				;;
			esac
		done
		
		# get the option at last(right before the current word).
		for (( i=0; i<$((${#COMP_WORDS[@]}-1)); i++)); do
			case ${COMP_WORDS[$i]} in
				-*)
				option_set_last=${COMP_WORDS[$i]}
				;;
			esac
		done
		
		# if "--hosts" was set at last, get hosts list.
		if [ "$option_set_last" == "--hosts" ]; then
			# get hosts list.
			if [ -d "$MOUNT_PATH" ]; then 
				hosts_list=$(ls $MOUNT_PATH)   
			else
				hosts_list="" 
			fi	
		fi
		
		# options completion for "create" and "set".
		if [ ${COMP_WORDS[1]} == "create" -o ${COMP_WORDS[1]} == "set" ]; then 
			case "$3" in 
				"-o"|"--options")
				compopt -o nospace
				COMPREPLY=( $(compgen -W "${_options_prompt}" $2) )
				return 0
				;;
				"-s"|"--section")
				COMPREPLY=( $(compgen -W "${_section_prompt}" -- $2) )
				return 0
				;;
				"-f"|"--ini-file")
				compopt -o nospace
				file_list=$(compgen -f -- $2) # Variable Type!!!
				for file in $file_list; do
					if [ -d $(readlink -f "$file") ]; then
						COMPREPLY+=( "${file}/" )
					else
						COMPREPLY+=( "${file}" )
					fi
				done
				return 0
				;;
				"--caputlog")
				;;
				"--status-ioc")
				;;
				"--status-os")
				;;
				"--autosave")
				;;
				"--add-asyn")
				prompt="--port-type"
				;;
				"--add-stream")
				prompt="--port-type"
				;;
				"--port-type")
				COMPREPLY=( $(compgen -W "${_port_type_prompt}" -- $2) )
				return 0
				;;
				"--add-raw")
				;;
				"-p"|"--print-ioc")
				;;
				"-v"|"--verbose")
				;;
				"-h"|"--help")
				;;
				*)
				if [ "$option_set_last" == "--options" -o "$option_set_last" == "-o" ]; then 
					compopt -o nospace
					prompt=$_options_prompt
				fi
				;;
			esac
			prompt="$prompt $create_prompt"
			prompt="$prompt $ioc_list_temp"
			COMPREPLY=( $(compgen -W "${prompt}" -- $2) )
			return 0
		fi
		# options completion for "exec".
		if [ ${COMP_WORDS[1]} == "exec" ]; then 
			case "$3" in 
				"--add-src-file")
				prompt="--src-path"
				;;
				"--src-path")
				compopt -o nospace
				directory_list=$(compgen -d -- $2) # Variable Type!!!
				for dir in $directory_list; do
					COMPREPLY+=( "${dir}/" )
				done
				return 0
				;;
				"--gen-startup-file")
				prompt="--force-silent --force-default"
				;;
				"--force-silent")
				prompt="--force-default"
				;;
				"--force-default")
				prompt="--force-silent"
				;;
				"-e"|"--export-for-mount")
				prompt="--mount-path --force-overwrite"
				;;
				"--mount-path")
				compopt -o nospace
				directory_list=$(compgen -d -- $2) # Variable Type!!!
				for dir in $directory_list; do
					COMPREPLY+=( "${dir}/" )
				done
				return 0
				;;
				"--force-overwrite")
				if [ "$option_set_first" == "--export-for-mount" ]; then
					prompt="--mount-path"
				elif [ "$option_set_first" == "--restore-backup-file" ]; then
					prompt="--backup-path"
				else
					return 0
				fi
				;;
				"--gen-compose-file")
				prompt="--base-image --hosts"
				;;
				"--hosts")
				COMPREPLY=( $(compgen -W "${hosts_list}" -- $2) )
				return 0
				;;
				"--base-image")
				compopt -o nospace
				COMPREPLY=( $(compgen -W $image_prefix -- $2) )
				return 0
				;;
				"-b"|"--gen-backup-file")
				COMPREPLY=( $(compgen -W "--backup-path --backup-mode" -- $2) )
				return 0
				;;
				"--backup-path")
				compopt -o nospace
				directory_list=$(compgen -d -- $2) # Variable Type!!!
				for dir in $directory_list; do
					COMPREPLY+=( "${dir}/" )
				done
				return 0
				;;
				"--backup-mode")
				COMPREPLY=( $(compgen -W "${_backup_mode_prompt}" -- $2) )
				return 0
				;;
				"-r"|"--restore-backup-file")
				COMPREPLY=( $(compgen -W "--backup-file " -- $2) )
				return 0
				;;
				"--backup-file")
				compopt -o nospace
				file_list=$(compgen -f -- $2) # Variable Type!!!
				for file in $file_list; do
					if [ -d $(readlink -f "$file") ]; then
						COMPREPLY+=( "${file}/" )
					else
						COMPREPLY+=( "${file}" )
					fi
				done
				return 0
				;;
				"--run-check")
				;;
				"-v"|"--verbose")
				;;
				"-h"|"--help")
				;;
				*)
				if [ "$option_set_last" == "--mount-path" ]; then 
					prompt="--force-overwrite"
				elif [ "$option_set_last" == "--hosts" ]; then 
					prompt="--base-image ${hosts_list}"
				elif [ "$option_set_last" == "--base-image" ]; then 
					prompt="--hosts"
				elif [ "$option_set_last" == "--backup-path" ]; then 
					prompt="--backup-mode"
				elif [ "$option_set_last" == "--backup-mode" ]; then 
					prompt="--backup-path"
				elif [ "$option_set_last" == "--backup-file" ]; then 
					prompt="--force-overwrite"
				fi
				;;
			esac
			prompt="$prompt $exec_ioc_prompt_temp"
			prompt="$prompt $exec_prompt"
			prompt="$prompt $ioc_list_temp"
			COMPREPLY=( $(compgen -W "${prompt}" -- $2) )
			return 0
		fi
		# options completion for "list".
		if [ ${COMP_WORDS[1]} == "list" ]; then 
			case "$3" in
				"-s"|"--section")
				COMPREPLY=( $(compgen -W "${_section_prompt}" -- $2) )
				return 0
				;;
				"-l"|"--ioc-list")
				COMPREPLY=( $(compgen -W "${ioc_list}" -- $2) )
				return 0
				;;
				"-i"|"--show-info")
				;;
				"-r"|"--raw-info")
				;;
				"-v"|"--verbose")
				;;
				"-h"|"--help")
				;;
				*)
				if [ "$option_set_last" == "--ioc-list" -o "$option_set_last" == "-l" ]; then 
					prompt="--section --show-info --raw-info --verbose $ioc_list"
					COMPREPLY=( $(compgen -W "${prompt}" -- $2) )
					return 0
				fi
				;;
			esac
			prompt="$prompt $list_prompt"
			prompt="$prompt $_condition_type_prompt_temp"
			COMPREPLY=( $(compgen -W "${prompt}" -- $2) )
			return 0
		fi
		# options completion for "remove".
		if [ ${COMP_WORDS[1]} == "remove" ]; then 
			case "$3" in
				"-r"|"--remove-all")
				;;
				"-f"|"--force")
				;;				
				"-v"|"--verbose")
				;;
				"-h"|"--help")
				;;
				*)
				;;
			esac
			prompt=$remove_prompt
			prompt="$prompt $ioc_list_temp"
			COMPREPLY=( $(compgen -W "${prompt}" -- $2) )
			return 0
		fi	
		# options completion for "rename".
		if [ ${COMP_WORDS[1]} == "rename" ]; then 
			if [ $COMP_CWORD -eq 3 ]; then 
				compopt -o nospace
				COMPREPLY=( $(compgen -W "${ioc_list}" -- $2) )
				return 0
			else
				COMPREPLY=( $(compgen -W "${rename_prompt}" -- $2) )
				return 0
			fi
		fi	
		# options completion for "swarm".
		if [ ${COMP_WORDS[1]} == "swarm" ]; then 
			case "$3" in
				"--gen-global-compose-file")
				prompt="--base-image"
				;;
				"--base-image")
				compopt -o nospace
				COMPREPLY=( $(compgen -W $image_prefix -- $2) )
				return 0
				;;				
				"--show-digest")
				;;
				"--show-services")
				prompt="--detail"
				;;
				"--detail")
				;;
				"--show-nodes")
				;;
				"--show-tokens")
				;;
				"--deploy-global-services")
				;;
				"--deploy-all-iocs")
				;;
				"--remove-all-services")
				;;
				"-b"|"--backup-swarm")
				;;
				"-r"|"--restore-swarm")
				prompt="--backup-file"
				;;
				"--backup-file")
				compopt -o nospace
				file_list=$(compgen -f -- $2) # Variable Type!!!
				for file in $file_list; do
					if [ -d $(readlink -f "$file") ]; then
						COMPREPLY+=( "${file}/" )
					else
						COMPREPLY+=( "${file}" )
					fi
				done
				return 0
				;;
				"--update-deployed-services")
				;;
				*)
				;;
			esac
			prompt="$prompt --verbose --help"
			COMPREPLY=( $(compgen -W "${prompt}" -- $2) )
			return 0
		fi	
		# options completion for "service".
		if [ ${COMP_WORDS[1]} == "service" ]; then 
			case "$3" in
				"--deploy")
				;;
				"--remove")
				;;				
				"--show-config")
				;;
				"--show-info")
				;;
				"--show-logs")
				;;
				"--update")
				;;
				*)
				;;
			esac
			prompt=$service_prompt_temp
			prompt="$prompt $ioc_list_temp"
			COMPREPLY=( $(compgen -W "${prompt}" -- $2) )
			
		fi		

	fi

}

complete -F _mycommand_completion "./IocManager.py"
complete -F _mycommand_completion "IocManager.py"

# export $REPOSITORY_PATH here.
