#!/bin/sh -e
set -x

ruff check app tests scripts --fix
ruff format app tests scripts
