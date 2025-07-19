# K8S Autoscaling Lab

This repository is used to create a Kubernetes Lab that allows to stabilish a cluster running on vagrant+virtualbox for executing various Autoscaling/Autoadapting solutions, in order to compare the Custom Self-Adapter with other Autoscaling solutions, as Horizontal Pod Autoscaler and Custom Pod Autoscaler.

## Dependencies

Ths cluster is deployed using vagrant on virtualbox.

The base components on the cluster (ingress, prometheus, grafana etc) are deployed using [helmfile](https://github.com/helmfile/helmfile).

The test suite used is Grafana K6, builded by xk6 with golang.

## Cluster Init

On the `vagrant-kubeadm-kubernetes` directory, configure the nodes on `settings.yaml` and init the cluster with

```bash
vagrant up
```

On `settings.yaml`, the `custom_ca` option allows the execution of scripts that generate a root CA certificate and installs it on the nodes. This certificate will be used to sign the Ingress certificate, and should be installed on the host machine that runs the lab, so k6 can trust it.

## Helmfile & Bootstrapping

The `helmfile.yaml` file and the `bootstrapping` dir are used to deploy the base for the lab. The files in `bootstrapping` deploy components not deployed by the charts in the `helmfile.yaml`. The `cluster_bootstrap.sh` script executes the commands necessary to run the deloys.

```bash
./cluster_bootstrap.sh
```

## K6 Build

The script `k6-go-build.sh` uses xk6 to build k6 with the `xk6-output-prometheus-remote` plugin, that allows k6 to send its result to Prometheus.

## Kube ZNN

Kube ZNN is used to act as the target system for the tests.
