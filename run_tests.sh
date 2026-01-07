#!/bin/bash
# 
# Runs all the tests, consisting in the following:
# - kube-znn:800k
#   - 1 replica
#   - 3 replicas
#   - 5 replicas
# - kube-znn:400k
#   - 1 replica
#   - 3 replicas
#   - 5 replicas
# - kube-znn:200k
#   - 1 replica
#   - 3 replicas
#   - 5 replicas
# - hpa
#   - kube-znn:800k + hpa standard
#   - kube-znn:800k + hpa behavior scaledown stabilizationWindowSeconds=10
# - csa horizontal
#   - kube-znn:800k
# - csa horizontal + tag quality
#   - kube-znn:800k rollingUpdate maxSurge=25% & maxUnavailable=25%
#   - kube-znn:800k rollingUpdate maxSurge=50% & maxUnavailable=50%
#   - kube-znn:800k rollingUpdate maxSurge=75% & maxUnavailable=75%
#   - kube-znn:800k rollingUpdate maxSurge=100% & maxUnavailable=100%
# sleeps for a minute between locust executions

kubectl delete hpa znn
kubectl delete csa csa-quality

kubectl apply -k kube-znn/manifests/overlay/800k/
kubectl scale deployment kube-znn --replicas 1
sleep 5
locust --headless --processes 4 -H https://znn.k8s.lab -f tests/scenarios/locustfile.py
sleep 60

kubectl apply -k kube-znn/manifests/overlay/800k/
kubectl scale deployment kube-znn --replicas 3
sleep 5
locust --headless --processes 4 -H https://znn.k8s.lab -f tests/scenarios/locustfile.py
sleep 60

kubectl apply -k kube-znn/manifests/overlay/800k/
kubectl scale deployment kube-znn --replicas 5
sleep 5
locust --headless --processes 4 -H https://znn.k8s.lab -f tests/scenarios/locustfile.py
sleep 60

kubectl apply -k kube-znn/manifests/overlay/400k/
kubectl scale deployment kube-znn --replicas 1
sleep 5
locust --headless --processes 4 -H https://znn.k8s.lab -f tests/scenarios/locustfile.py
sleep 60

kubectl apply -k kube-znn/manifests/overlay/400k/
kubectl scale deployment kube-znn --replicas 3
sleep 5
locust --headless --processes 4 -H https://znn.k8s.lab -f tests/scenarios/locustfile.py
sleep 60

kubectl apply -k kube-znn/manifests/overlay/400k/
kubectl scale deployment kube-znn --replicas 5
sleep 5
locust --headless --processes 4 -H https://znn.k8s.lab -f tests/scenarios/locustfile.py
sleep 60

kubectl apply -k kube-znn/manifests/overlay/200k/
kubectl scale deployment kube-znn --replicas 1
sleep 5
locust --headless --processes 4 -H https://znn.k8s.lab -f tests/scenarios/locustfile.py
sleep 60

kubectl apply -k kube-znn/manifests/overlay/200k/
kubectl scale deployment kube-znn --replicas 3
sleep 5
locust --headless --processes 4 -H https://znn.k8s.lab -f tests/scenarios/locustfile.py
sleep 60

kubectl apply -k kube-znn/manifests/overlay/200k/
kubectl scale deployment kube-znn --replicas 5
sleep 5
locust --headless --processes 4 -H https://znn.k8s.lab -f tests/scenarios/locustfile.py
sleep 60


echo "####################################"
echo "#           Starting HPA           #"
echo "####################################"

kubectl apply -k kube-znn/manifests/overlay/800k/
kubectl scale deployment kube-znn --replicas 1
kubectl apply -f autoscalers/hpa/znn.yaml
sleep 5
locust --headless --processes 4 -H https://znn.k8s.lab -f tests/scenarios/locustfile.py
sleep 60
kubectl delete -f autoscalers/hpa/znn.yaml


echo "####################################"
echo "#        Starting HPA Fast         #"
echo "####################################"

kubectl apply -k kube-znn/manifests/overlay/800k/
kubectl scale deployment kube-znn --replicas 1
kubectl apply -f autoscalers/hpa/znn_fast.yaml
sleep 5
locust --headless --processes 4 -H https://znn.k8s.lab -f tests/scenarios/locustfile.py
sleep 60
kubectl delete -f autoscalers/hpa/znn_fast.yaml


echo "####################################"
echo "#          Starting CSA H          #"
echo "####################################"

kubectl apply -k kube-znn/manifests/overlay/800k/
kubectl scale deployment kube-znn --replicas 1
IMAGE="registry.k8s.lab/csa-quality-znn" TAG="h" envsubst < autoscalers/csa/custom-selfadapter-template.yaml > autoscalers/csa/custom-selfadapter.yaml
kubectl apply -f autoscalers/csa/custom-selfadapter.yaml
sleep 5
locust --headless --processes 4 -H https://znn.k8s.lab -f tests/scenarios/locustfile.py
sleep 60


echo "####################################"
echo "#       Starting CSA HQ 25%        #"
echo "####################################"

kubectl apply -k kube-znn/manifests/overlay/800k/
kubectl scale deployment kube-znn --replicas 1
kubectl patch deployment kube-znn --type=merge -p '{"spec":{"strategy":{"rollingUpdate":{"maxUnavailable":"25%","maxSurge":"25%"}}}}'
IMAGE="registry.k8s.lab/csa-quality-znn" TAG="hq" envsubst < autoscalers/csa/custom-selfadapter-template.yaml > autoscalers/csa/custom-selfadapter.yaml
kubectl apply -f autoscalers/csa/custom-selfadapter.yaml
sleep 5
locust --headless --processes 4 -H https://znn.k8s.lab -f tests/scenarios/locustfile.py
sleep 60


echo "####################################"
echo "#       Starting CSA HQ 50%        #"
echo "####################################"

kubectl apply -k kube-znn/manifests/overlay/800k/
kubectl scale deployment kube-znn --replicas 1
kubectl patch deployment kube-znn --type=merge -p '{"spec":{"strategy":{"rollingUpdate":{"maxUnavailable":"50%","maxSurge":"50%"}}}}'
sleep 5
locust --headless --processes 4 -H https://znn.k8s.lab -f tests/scenarios/locustfile.py
sleep 60


echo "####################################"
echo "#       Starting CSA HQ 75%        #"
echo "####################################"

kubectl apply -k kube-znn/manifests/overlay/800k/
kubectl scale deployment kube-znn --replicas 1
kubectl patch deployment kube-znn --type=merge -p '{"spec":{"strategy":{"rollingUpdate":{"maxUnavailable":"75%","maxSurge":"75%"}}}}'
sleep 5
locust --headless --processes 4 -H https://znn.k8s.lab -f tests/scenarios/locustfile.py
sleep 60


echo "####################################"
echo "#      Starting CSA HQ 100%        #"
echo "####################################"

kubectl apply -k kube-znn/manifests/overlay/800k/
kubectl scale deployment kube-znn --replicas 1
kubectl patch deployment kube-znn --type=merge -p '{"spec":{"strategy":{"rollingUpdate":{"maxUnavailable":"100%","maxSurge":"100%"}}}}'
sleep 5
locust --headless --processes 4 -H https://znn.k8s.lab -f tests/scenarios/locustfile.py
sleep 60
