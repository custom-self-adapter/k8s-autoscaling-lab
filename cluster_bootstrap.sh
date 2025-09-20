#!/bin/bash

VAGRANT_CERTS='vagrant-kubeadm-kubernetes/certs'

kubectl label node node01 app=yes
kubectl label node node02 db=yes
kubectl label node node02 adaptation=yes
kubectl label node node02 cert=yes
kubectl label node node02 ingress=yes
kubectl label node node03 monitoring=yes
kubectl patch -n kube-system deployments.apps metrics-server -p '{"spec": {"template": {"spec": {"nodeSelector": {"monitoring": "yes"}}}}}'

helmfile sync

kubectl apply -f bootstrapping/ipaddresspool.yaml

kubectl create namespace cert-manager
kubectl -n cert-manager create secret tls lab-ca-keypair --cert=$VAGRANT_CERTS/rootCA.crt --key=$VAGRANT_CERTS/rootCA.key
kubectl apply -f bootstrapping/cluster-certs.yaml

kubectl apply -f bootstrapping/ingress-cert.yaml
