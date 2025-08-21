#!/usr/bin/env bash

if [ ! -x k6 ]
then
    ./k6-go-build.sh
fi

DEFAULTTESTNAME='ob-loadtest'
TESTNAME="${1:-$DEFAULTTESTNAME}"
export BASE_URL='http://znn.k8s.lab'

./k6 run tests/scenarios/$TESTNAME.js \
    --tag testid=$(date +%s) \
    -o csv=tests/results/$TESTNAME-$(date '+%Y-%m-%d-%H%M').csv
