#!/bin/sh
#/home/fkunzwei/data1/envs/bkg_pipe/bin/python -m luigi --module gbm_bkg_pipe CreateReportDate --workers 32 --date $(date +'%Y-%m-%d')
#source /home/fkunzwei/data1/envs/bkg_pipe/bin/activate

#/home/fkunzwei/data1/envs/bkg_pipe/bin/python -m luigi --workers 32 --module gbm_transient_search CreateReportDate --date $(date --date='-1 day' +'%Y-%m-%d')
#source /home/balrog/.cron_vars
#source /home/balrog/.venv/transient_search/bin/activate

/home/balrog/.venv/transient_search/bin/python /home/balrog/sw/gbm_transient_search/bin/data_available --date $(date --date='-1 day' +'%y%m%d')
/home/balrog/.venv/transient_search/bin/python -m luigi --workers 32 --scheduler-host localhost --scheduler-port 8666 --module gbm_transient_search CreateReportDate --date $(date --date='-1 day' +'%Y-%m-%d') --remote-host raven;
mv /home/balrog/logs/log.txt /home/balrog/logs/archive/log_$(date --date='-1 day' +'%y%m%d');
