#!/bin/bash

VAGRANT_CERTS='vagrant-kubeadm-kubernetes/certs'

helmfile sync

kubectl apply -f bootstrapping/ipaddresspool.yaml

kubectl create namespace cert-manager
kubectl -n cert-manager create secret tls lab-ca-keypair --cert=$VAGRANT_CERTS/rootCA.crt --key=$VAGRANT_CERTS/rootCA.key
kubectl apply -f bootstrapping/cluster-certs.yaml

kubectl apply -f bootstrapping/ingress-cert.yaml
