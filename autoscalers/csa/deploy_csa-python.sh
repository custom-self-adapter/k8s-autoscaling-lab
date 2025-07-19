#!/bin/bash

export IMAGE="registry.k8s.lab/csa-quality-znn"
export TAG="v0.1.$(date +%s)"

docker build -t $IMAGE:$TAG .
docker push $IMAGE:$TAG

envsubst < custom-selfadapter-template.yaml > custom-selfadapter.yaml

# kubectl apply -f role-cpa-python.yaml
kubectl apply -f custom-selfadapter.yaml