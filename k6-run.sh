#!/usr/bin/env bash

if [ ! -x k6 ]
then
    ./k6-go-build.sh
fi

DEFAULTTESTNAME='znn-loadtest'
DEFAULTBASEURL='http://znn.k8s.lab'
DEFAULTPROMURL='http://prometheus.k8s.lab'
export BASE_URL="${2:-$DEFAULTBASEURL}"
PROM_URL="${3:-$DEFAULTPROMURL}"
TESTNAME="${1:-$DEFAULTTESTNAME}"

export K6_PROMETHEUS_RW_SERVER_URL="${PROM_URL}/api/v1/write"
export K6_PROMETHEUS_RW_TREND_STATS='min,max,p(95),p(99)'

TIMESTAMP=$(date '+%Y%m%d%H%M')

./k6 run tests/scenarios/$TESTNAME.js \
    --tag testid=$TIMESTAMP \
    -o experimental-prometheus-rw \
    -o csv=tests/results/$TESTNAME-$TIMESTAMP.csv
