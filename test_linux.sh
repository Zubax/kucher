#!/bin/bash

timeout 20s ./zubax-kucher
exit_status=$?
if [ $exit_status -eq 124 ]; then
    echo No error found
    exit 0
else
    echo error found
    exit 1
fi
