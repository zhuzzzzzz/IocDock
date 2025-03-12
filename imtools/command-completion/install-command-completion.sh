#!/bin/bash


cat ./command-completion.sh > ./IocManagerCompletion

sudo cp ./IocManagerCompletion /etc/bash_completion.d/

. ./IocManagerCompletion


