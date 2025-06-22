#!/bin/bash

VAGRANT_CERTS='vagrant-kubeadm-kubernetes/certs'

kubectl create namespace cert-manager
kubectl -n cert-manager create secret tls lab-ca-keypair --cert=$VAGRANT_CERTS/rootCA.crt --key=$VAGRANT_CERTS/rootCA.key
