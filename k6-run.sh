#!/usr/bin/env bash

if [ ! -x k6 ]
then
    ./k6-go-build.sh
fi

TESTNAME='ob-loadtest'
K6_PROMETHEUS_RW_SERVER_URL='http://prometheus.k8s.lab/api/v1/write'

./k6 run tests/scenarios/$TESTNAME.js \
    -o csv=tests/results/$TESTNAME-$(date '+%Y-%m-%d-%H%M').csv \
    -o experimental-prometheus-rw
