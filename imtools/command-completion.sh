
# pipe and xargs will not influence command completion.

_mycommand_completion() {

	# echo $1 $2 $3 
	# $1 : command
	# $2 : current word
	# $3 : previous word

	# 
	sub_command_opts="create set exec list remove --help"
	#
	create_prompt="--options --section --ini-file --caputlog --status-ioc --status-os --autosave --add-asyn --add-stream --port-type --add-raw --print-ioc --verbose --help"
	_options_prompt="host= image= bin= description= load_=  epics_env_= report_info=true report_info=false caputlog_json=true caputlog_json=false "
	_section_prompt="DB SETTING ASYN STREAM RAW"
	_port_type_prompt="tcp/ip serial"
	#
	exec_prompt="--add-src-file --src-path --gen-startup-file --force-silent --force-default --export-for-mount --mount-path --force-overwrite --gen-compose-file --base-image --gen-backup-file --backup-path --backup-mode --restore-backup-file --backup-file --run-check --verbose --help"
	_backup_mode_prompt="src all"
	#
	list_prompt="--section --ioc-list --show-info --raw-info --verbose --help"
	_condition_type_prompt="name= host= status=created status=generated status=exported snapshot=logged snapshot=changed"
	#
	remove_prompt="--remove-all --force --verbose --help"


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
			*)
			return 1
		esac
		COMPREPLY=( $(compgen -W "${prompt}" -- $2) )
		return 0  
	fi

	# options completion( 4th or later ).
	if [ $COMP_CWORD -gt 2 ]; then
		
		# echo "${COMP_WORDS[@]}"
		
		# check whether any option was set.
		ioc_list_temp=$ioc_list
		_condition_type_prompt_temp=$_condition_type_prompt
		for word in ${COMP_WORDS[@]}; do
			case $word in
				-*)
				ioc_list_temp="" # once any option was set, ioc projects will not be prompted. used for "create" "set" "exec" "remove".
				_condition_type_prompt_temp="" # once any option was set, conditions will not be prompted. used for "list".
				break
				;;
			esac
		done
		# options completion for "create" and "set".
		if [ ${COMP_WORDS[1]} == "create" -o ${COMP_WORDS[1]} == "set" ]; then 
			# if only "--options" specified,  _options_prompt should be prompted.
			for word in ${COMP_WORDS[@]}; do
				case $word in
					"--options")
					prompt=$_options_prompt
					;;
					-*)
					prompt=""
					break
					;;
				esac
			done
			case "$3" in 
				"--options")
				compopt -o nospace
				COMPREPLY=( $(compgen -W "${_options_prompt}" $2) )
				return 0
				;;
				"--section")
				COMPREPLY=( $(compgen -W "${_section_prompt}" -- $2) )
				return 0
				;;
				"--ini-file")
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
				"--port-type")
				COMPREPLY=( $(compgen -W "${_port_type_prompt}" -- $2) )
				return 0
				;;
				"--add-raw")
				;;
				"--print-ioc")
				;;
				"--verbose")
				;;
				"--help")
				;;
				*)
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
				;;
				"--force-silent")
				;;
				"--force-default")
				;;
				"--export-for-mount")
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
				;;
				"--gen-compose-file")
				;;
				"--base-image")
				return 0
				;;
				"--gen-backup-file")
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
				"--restore-backup-file")
				COMPREPLY=( $(compgen -W "--backup-file " -- $2) )
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
				"--verbose")
				;;
				"--help")
				;;
				*)
				;;
			esac
			prompt=$exec_prompt
			prompt="$prompt $ioc_list_temp"
			COMPREPLY=( $(compgen -W "${prompt}" -- $2) )
			return 0
		fi
		# options completion for "list".
		if [ ${COMP_WORDS[1]} == "list" ]; then 
			case "$3" in
				"--section")
				COMPREPLY=( $(compgen -W "${_section_prompt}" -- $2) )
				return 0
				;;
				"--ioc-list")
				;;
				"--show-info")
				;;
				"--raw-info")
				;;
				"--verbose")
				;;
				"--help")
				;;
				*)
				;;
			esac
			# "--ioc-list" option should be used at last, and no other options will be prompted under this situation.
			for word in ${COMP_WORDS[@]}; do
				case $word in
					"--ioc-list")
					COMPREPLY=( $(compgen -W "${ioc_list}" -- $2) )
					return 0
					;;
				esac
			done
			prompt=$list_prompt
			prompt="$prompt $_condition_type_prompt_temp"
			COMPREPLY=( $(compgen -W "${prompt}" -- $2) )
			return 0
		fi
		# options completion for "remove".
		if [ ${COMP_WORDS[1]} == "remove" ]; then 
			case "$3" in
				"--remove-all")
				;;
				"--force")
				;;				
				"--verbose")
				;;
				"--help")
				;;
				*)
				;;
			esac
			prompt=$remove_prompt
			prompt="$prompt $ioc_list_temp"
			COMPREPLY=( $(compgen -W "${prompt}" -- $2) )
			return 0
		fi		

	fi

}

complete -F _mycommand_completion "./IocManager.py"

# export $REPOSITORY_PATH here.
