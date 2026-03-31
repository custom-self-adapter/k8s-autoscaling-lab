#!/bin/bash
#
# Runs all the tests, consisting in the following:
# - kube-znn:800k
#   - 1 replica
#   - 5 replicas
# - hpa
#   - kube-znn:800k + hpa standard
#   - kube-znn:800k + hpa behavior scaledown stabilizationWindowSeconds=10
# - csa horizontal
#   - kube-znn:800k
# - csa horizontal + tag quality
#   - kube-znn:800k rollingUpdate maxSurge=25% & maxUnavailable=25%
#   - kube-znn:800k rollingUpdate maxSurge=50% & maxUnavailable=50%
# - vpa
# - csa vertical + tag quality
# sleeps for a minute between locust executions

RUN_TIME=$(date +%Y%m%d%H%M)

kubectl delete hpa znn
kubectl delete csa csa-znn
kubectl delete vpa znn
kubectl delete -k kube-znn/manifests/overlay/800k/

kubectl apply -k kube-znn/manifests/overlay/800k/
kubectl scale deployment kube-znn --replicas 1
sleep 5
PROM_EXTRACT_NAME=${RUN_TIME}_0_base_1 locust --headless --only-summary --processes 4 -H https://znn.k8s.lab -f tests/scenarios/locustfile.py
sleep 60

kubectl apply -k kube-znn/manifests/overlay/800k/
kubectl scale deployment kube-znn --replicas 5
sleep 5
PROM_EXTRACT_NAME=${RUN_TIME}_1_base_5 locust --headless --only-summary --processes 4 -H https://znn.k8s.lab -f tests/scenarios/locustfile.py
sleep 60

echo "####################################"
echo "#           Starting HPA           #"
echo "####################################"

kubectl apply -k kube-znn/manifests/overlay/800k/
kubectl scale deployment kube-znn --replicas 1
kubectl apply -f autoscalers/hpa/znn.yaml
sleep 5
PROM_EXTRACT_NAME=${RUN_TIME}_2_hpa_std locust --headless --only-summary --processes 4 -H https://znn.k8s.lab -f tests/scenarios/locustfile.py
sleep 60
kubectl delete -f autoscalers/hpa/znn.yaml

echo "####################################"
echo "#        Starting HPA Fast         #"
echo "####################################"

kubectl apply -k kube-znn/manifests/overlay/800k/
kubectl scale deployment kube-znn --replicas 1
kubectl apply -f autoscalers/hpa/znn_fast.yaml
sleep 5
PROM_EXTRACT_NAME=${RUN_TIME}_3_hpa_fast locust --headless --only-summary --processes 4 -H https://znn.k8s.lab -f tests/scenarios/locustfile.py
sleep 60
kubectl delete -f autoscalers/hpa/znn_fast.yaml


echo "####################################"
echo "#          Starting CSA H          #"
echo "####################################"

kubectl delete -k kube-znn/manifests/overlay/800k/
kubectl apply -k kube-znn/manifests/overlay/800k/
kubectl apply -f autoscalers/csa/custom-selfadapter-h.yaml
sleep 5
PROM_EXTRACT_NAME=${RUN_TIME}_4_csa_h locust --headless --only-summary --processes 4 -H https://znn.k8s.lab -f tests/scenarios/locustfile.py
sleep 60
kubectl delete -f autoscalers/csa/custom-selfadapter-h.yaml


echo "####################################"
echo "#       Starting CSA HQ 25%        #"
echo "####################################"

kubectl delete -k kube-znn/manifests/overlay/800k/
kubectl apply -k kube-znn/manifests/overlay/800k/
kubectl scale deployment kube-znn --replicas 1
kubectl patch deployment kube-znn --type=merge -p '{"spec":{"strategy":{"rollingUpdate":{"maxUnavailable":"25%","maxSurge":"25%"}}}}'
kubectl apply -f autoscalers/csa/custom-selfadapter-hq.yaml
sleep 5
PROM_EXTRACT_NAME=${RUN_TIME}_5_csa_hq_25 locust --headless --only-summary --processes 4 -H https://znn.k8s.lab -f tests/scenarios/locustfile.py
sleep 60


echo "####################################"
echo "#       Starting CSA HQ 50%        #"
echo "####################################"

kubectl patch deployment kube-znn --type=merge -p '{"spec":{"strategy":{"rollingUpdate":{"maxUnavailable":"50%","maxSurge":"50%"}}}}'
sleep 5
PROM_EXTRACT_NAME=${RUN_TIME}_6_csa_hq_50 locust --headless --only-summary --processes 4 -H https://znn.k8s.lab -f tests/scenarios/locustfile.py
sleep 60
kubectl delete -f autoscalers/csa/custom-selfadapter-hq.yaml


echo "####################################"
echo "#           Starting VPA           #"
echo "####################################"

kubectl delete csa csa-znn
kubectl delete -k kube-znn/manifests/overlay/800k/
kubectl apply -k kube-znn/manifests/overlay/800k/
kubectl apply -f autoscalers/vpa/znn.yaml
sleep 30
PROM_EXTRACT_NAME=${RUN_TIME}_7_vpa locust --headless --only-summary --processes 4 -H https://znn.k8s.lab -f tests/scenarios/locustfile.py
sleep 60
kubectl delete -f autoscalers/vpa/znn.yaml


echo "####################################"
echo "#         Starting CSA V+Q         #"
echo "####################################"

kubectl delete -k kube-znn/manifests/overlay/800k/
kubectl apply -k kube-znn/manifests/overlay/800k/
kubectl apply -f autoscalers/csa/custom-selfadapter-vq.yaml
sleep 5
PROM_EXTRACT_NAME=${RUN_TIME}_8_csa_vq locust --headless --only-summary --processes 4 -H https://znn.k8s.lab -f tests/scenarios/locustfile.py
kubectl delete -f autoscalers/csa/custom-selfadapter-vq.yaml
