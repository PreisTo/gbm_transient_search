#! /bin/bash

if [ -z "$1" ]
  then
    echo "No host supplied"
fi
if [ -z "$2" ]
  then
    echo "No nr_hosts supplied"
fi

host=$1
nr_hosts=$2
log_path="/home/balrog/logs/create_master_ssh.log"

echo "Creating new SSH Master --- $(date)" >> $log_path

rm -rf ~/.ssh/master-socket/connection_cache/*

for i in $(seq 1 $(($nr_hosts)) ) ; do
    ssh -MNnv -S "~/.ssh/master-socket/gbmtrans@${host}_${i}:22" $host
done

