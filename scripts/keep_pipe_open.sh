#!/usr/bin/bash

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
log_path="/home/balrog/logs/keep_pipe_open.log"

echo "Keeping pipe open --- $(date)" >> $log_path

while true; do
	for i in $(seq 1 $(($nr_hosts)) ) ; do
		(ssh -S "~/.ssh/master-socket/gbmtrans@${host}_${i}:22" $host touch /u/gbmtrans/still_open)
		res=$?
		echo "Done for ${i} - exit code $res"
		if (($res != 0)) ; then
			echo "$(date) - $(i) failed with $res" >> $log_path;
	   	else
			echo "All clear - $i, $res"
		fi;
    	done
	sleep 10
done;
