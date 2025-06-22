#!/bin/bash

export TIMESTAMP=$(date +%s)

docker build -t registry.k8s.lab/cpa-python:latest \
            -t registry.k8s.lab/cpa-python:0.1-$TIMESTAMP .

docker push registry.k8s.lab/cpa-python:latest
docker push registry.k8s.lab/cpa-python:0.1-$TIMESTAMP

envsubst < cpa-template.yaml > cpa.yaml

kubectl apply -f role-cpa-python.yaml
kubectl apply -f cpa.yaml