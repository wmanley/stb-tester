#!/bin/bash

script_dir=$(readlink -f $(dirname $BASH_SOURCE))

mkdir -p ~/results/test &&
stbt batch run -o ~/results/test -1 "$script_dir"/tests/test.py
