#!/usr/bin/env bash

if [ ! -x k6 ]
then
    ./k6-go-build.sh
fi

DEFAULTTESTNAME='ob-loadtest'
TESTNAME="${1:-$DEFAULTTESTNAME}"
export K6_PROMETHEUS_RW_SERVER_URL='http://10.0.0.17:9090/api/v1/write'
export K6_PROMETHEUS_RW_TREND_STATS='min,max,p(95),p(99)'
export BASE_URL='http://znn.k8s.lab'

./k6 run tests/scenarios/$TESTNAME.js \
    --tag testid=$(date +%s) \
    -o experimental-prometheus-rw
    # -o csv=tests/results/$TESTNAME-$(date '+%Y-%m-%d-%H%M').csv \
