#!/bin/bash

OUTPUT_DIR=$1

SCRIPT_DIR=$( cd -- "$( dirname -- "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )

cd $SCRIPT_DIR/..

docker compose exec db pg_dumpall -c -U postgres | zstd > $1/dump_`date +%Y-%m-%d"_"%H_%M_%S`.sql.zst
