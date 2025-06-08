#!/usr/bin/env bash

if [ ! -x k6 ]
then
    ./k6-go-build.sh
fi

DEFAULTTESTNAME='ob-loadtest'
TESTNAME="${1:-$DEFAULTTESTNAME}"
export K6_PROMETHEUS_RW_SERVER_URL='http://10.0.0.17:9090/api/v1/write'
export BASE_URL='http://boutique.k8s.lab'

./k6 run tests/scenarios/$TESTNAME.js \
    -o experimental-prometheus-rw
    # -o csv=tests/results/$TESTNAME-$(date '+%Y-%m-%d-%H%M').csv \
