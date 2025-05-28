#!/usr/bin/env bash

if [ ! -x k6 ]
then
    ./k6-go-build.sh
fi

TESTNAME='ob-loadtest'
export K6_PROMETHEUS_RW_SERVER_URL='http://10.0.0.17:9090/api/v1/write'

./k6 run tests/scenarios/$TESTNAME.js \
    -o csv=tests/results/$TESTNAME-$(date '+%Y-%m-%d-%H%M').csv \
    -o experimental-prometheus-rw
