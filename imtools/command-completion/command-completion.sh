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
	sub_command_opts="create set exec list swarm service remove rename edit config"
	
	#
	create_prompt="--options --section --ini-file --caputlog --status-ioc --status-os --autosave --add-asyn --add-stream --add-raw"
	#
	exec_prompt="" # general prompt for all exec commands.
	exec_ioc_prompt="--generate-and-export --gen-startup-file --export-for-mount --add-src-file --restore-snapshot-file --gen-swarm-file --deploy" # exec commands for specified IOC projects.
	#
	list_prompt="--section --list-from --show-info --show-panel"
	_condition_type_prompt="name= host= state= status= snapshot= is_exported= "
	#
	remove_prompt="--remove-all --force"
	#
	rename_prompt=""
	#
	swarm_prompt="--gen-built-in-services --deploy-global-services --deploy-all-iocs --remove-global-services --remove-all-iocs --remove-all-services --show-digest --show-services --show-nodes --show-tokens --backup-swarm --restore-swarm --update-deployed-services"
	#
	service_prompt="--deploy --remove --show-config --show-info --show-logs --update"
	
	

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
	
	# get service list
	if [ -f "/usr/bin/IocManager" ]; then
		service_list=$(IocManager swarm --list-managed-services)
	else
		service_list=""
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
			"exec") # "exec" may specify an IOC project firstly or specify the commands that are applied to all IOC projects.
			prompt="--gen-backup-file --restore-backup-file --run-check"
			prompt="$ioc_list $prompt"
			;;
			"list")
			compopt -o nospace
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
			prompt="$service_list $prompt"
			;;
			"edit")
			prompt="" # "edit" should specify an IOC project firstly.
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

		# check whether any option was set(before the current word) and get the option at first.
		ioc_list_temp=$ioc_list
		service_list_temp=$service_list
		exec_ioc_prompt_temp=$exec_ioc_prompt
		_condition_type_prompt_temp=$_condition_type_prompt
		service_prompt_temp=$service_prompt
		for (( i=0; i<$((${#COMP_WORDS[@]}-1)); i++)); do
			case ${COMP_WORDS[$i]} in
				-*)
				option_set_first=${COMP_WORDS[$i]} # get that first option.
				ioc_list_temp="" # ioc projects will not be prompted when option has been set.
				service_list_temp=""
				exec_ioc_prompt_temp="" # commands for specified IOC projects will not be prompted, otherwise those should be prompt. for "exec". 
				_condition_type_prompt_temp="" # conditions will not be prompted. for "list".
				service_prompt_temp=""
				break
				;;
			esac
		done
		
		# get the option at last(before the current word).
		for (( i=0; i<$((${#COMP_WORDS[@]}-1)); i++)); do
			case ${COMP_WORDS[$i]} in
				-*)
				option_set_last=${COMP_WORDS[$i]}
				;;
			esac
		done
		
		# options completion for "create" and "set".
		if [ ${COMP_WORDS[1]} == "create" -o ${COMP_WORDS[1]} == "set" ]; then 
			case "$3" in 
				"-o"|"--options")
				;;
				"-s"|"--section")
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
				;;
				"--add-stream")
				;;
				"--add-raw")
				;;
				*)
				;;
			esac
			prompt="$create_prompt"
			prompt="$prompt $ioc_list_temp"
			COMPREPLY=( $(compgen -W "${prompt}" -- $2) )
			return 0
		fi
		# options completion for "exec".
		if [ ${COMP_WORDS[1]} == "exec" ]; then 
			case "$3" in 
				"--add-src-file")
				compopt -o nospace
				directory_list=$(compgen -d -- $2) # Variable Type!!!
				for dir in $directory_list; do
					COMPREPLY+=( "${dir}/" )
				done
				return 0
				;;
				"--gen-startup-file")
				return 0
				;;
				"--export-for-mount")
				COMPREPLY=( $(compgen -W "--force-overwrite" -- $2) )
				return 0
				;;
				"--force-overwrite")
				return 0
				;;
				"--generate-and-export")
				COMPREPLY=( $(compgen -W "--force-overwrite" -- $2) )
				return 0
				;;
				"--gen-swarm-file")
				return 0
				;;
				"--deploy")
				COMPREPLY=( $(compgen -W "--force-overwrite" -- $2) )
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
				COMPREPLY=( $(compgen -W "all src" -- $2) )
				return 0
				;;
				"-r"|"--restore-backup-file")
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
				"--restore-snapshot-file")
				COMPREPLY=( $(compgen -W "all ioc.ini" -- $2) )
				return 0
				;;
				"--run-check")
				return 0
				;;
				*)
				;;
			esac
			if [ "$option_set_first" == "--gen-backup-file" ]; then 
				prompt="--backup-path --backup-mode"
			elif [ "$option_set_first" == "--restore-backup-file" ]; then 
				prompt="--force-overwrite"
			elif [ "$option_set_first" == "--restore-snapshot-file" ]; then 
				prompt="--force-overwrite"
			fi
			prompt="$prompt $exec_ioc_prompt_temp"
			prompt="$prompt $exec_prompt"
			prompt="$prompt $ioc_list_temp"
			COMPREPLY=( $(compgen -W "${prompt}" -- $2) )
			return 0
		fi
		# options completion for "list".
		if [ ${COMP_WORDS[1]} == "list" ]; then 
			compopt -o nospace
			case "$3" in
				"-s"|"--section")
				COMPREPLY=( $(compgen -W "IOC SETTING DEPLOY" -- $2) )
				return 0
				;;
				"-l"|"--list-from")
				COMPREPLY=( $(compgen -W "${ioc_list}" -- $2) )
				return 0
				;;
				"-i"|"--show-info")
				;;
				"-p"|"--prompt-info")
				;;
				*)
				if [ "$option_set_last" == "--list-from" -o "$option_set_last" == "-l" ]; then 
					prompt="--section --show-info --show-panel $ioc_list"
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
				"--gen-built-in-services")
				;;
				"--deploy-global-services")
				;;
				"--deploy-all-iocs")
				;;
				"--remove-global-services")
				;;
				"--remove-all-iocs")
				;;
				"--remove-all-services")
				;;
				"--show-digest")
				;;
				"--show-services")
				prompt="--detail"
				;;
				"--detail")
				;;
				"--show-nodes")
				prompt="--detail"
				;;
				"--show-tokens")
				;;
				"-b"|"--backup-swarm")
				;;
				"-r"|"--restore-swarm")
				COMPREPLY=( $(compgen -W "--backup-file" -- $2) )
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
				"--update-deployed-services")
				;;
				*)
				;;
			esac
			prompt="$prompt"
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
			prompt="$prompt $service_list_temp"
			COMPREPLY=( $(compgen -W "${prompt}" -- $2) )
			
		fi		

	fi

}

complete -F _mycommand_completion "./IocManager.py"
complete -F _mycommand_completion "IocManager.py"
complete -F _mycommand_completion "IocManager"

