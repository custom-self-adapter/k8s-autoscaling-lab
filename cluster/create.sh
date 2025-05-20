#!/usr/bin/env bash

kubectl cluster-info --context kind-autoscaling-lab > /dev/null 2>&1 && exit 0

set -e
kind create cluster --name autoscaling-lab --config cluster/kind-config.yaml
