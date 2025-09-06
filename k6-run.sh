#!/usr/bin/env bash

if [ ! -x k6 ]
then
    ./k6-go-build.sh
fi

DEFAULTTESTNAME='ob-loadtest'
DEFAULTBASEURL='http://znn.k8s.lab'
export BASE_URL="${1:-$DEFAULTBASEURL}"
TESTNAME="${2:-$DEFAULTTESTNAME}"

./k6 run tests/scenarios/$TESTNAME.js \
    --tag testid=$(date +%s) \
    -o csv=tests/results/$TESTNAME-$(date '+%Y-%m-%d-%H%M').csv
