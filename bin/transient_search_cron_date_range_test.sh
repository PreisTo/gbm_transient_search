#!/bin/bash

echo -n "Please type in your start date for the transient search for the last 5 days. The format should be 2023-05-07."
read custom_date
#put here a fail-save if the date is not correct or doesn't exist at all or it isn't a date


date +"Starting the transient search pipeline at %Y-%m-%d %X for the last 5 days."

#/home/fkunzwei/data1/envs/bkg_pipe/bin/python -m luigi --module gbm_bkg_pipe CreateReportDate --workers 32 --date $(date +'%Y-%m-%d')
#source /home/fkunzwei/data1/envs/bkg_pipe/bin/activate

/home/balrog/.venv/transient_search/bin/python -m luigi --workers 32 --module gbm_transient_search RangeDailyBase --of CreateReportDate --days-back=5 --stop $custom_date --reverse

