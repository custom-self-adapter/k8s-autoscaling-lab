#!/bin/bash

VAGRANT_CERTS='vagrant-kubeadm-kubernetes/certs'

kubectl label node node01 autoscaling.lab/app=yes
kubectl label node node02 autoscaling.lab/db=yes
kubectl label node node02 autoscaling.lab/adaptation=yes
kubectl label node node02 autoscaling.lab/cert=yes
kubectl label node node02 autoscaling.lab/ingress=yes
kubectl label node node03 autoscaling.lab/ingress=yes
kubectl label node node03 autoscaling.lab/registry=yes
kubectl label node node03 autoscaling.lab/monitoring=yes
kubectl patch -n kube-system deployments.apps metrics-server -p '{"spec": {"template": {"spec": {"nodeSelector": {"autoscaling.lab/monitoring": "yes"}}}}}'

helmfile sync -f helmfile_step1.yaml

kubectl apply -f bootstrapping/ipaddresspool.yaml
kubectl -n cert-manager create secret tls lab-ca-keypair --cert=$VAGRANT_CERTS/rootCA.crt --key=$VAGRANT_CERTS/rootCA.key
kubectl apply -f bootstrapping/cluster-certs.yaml
kubectl create namespace ingress-nginx
kubectl apply -f bootstrapping/ingress-cert.yaml

helmfile sync -f helmfile_step2.yaml
