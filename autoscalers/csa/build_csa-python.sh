#!/bin/bash

export IMAGE="registry.k8s.lab/csa-znn"
export TAG="vq"

docker build -t $IMAGE:$TAG .
docker push $IMAGE:$TAG

envsubst < custom-selfadapter-template.yaml > custom-selfadapter-${TAG}.yaml
