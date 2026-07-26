# Kubernetes Autoscaling Lab

Custom Self-Adapter (CSA) is a framework for implementing Kubernetes adaptation
policies with user-provided metric, evaluation, and adaptation logic. Unlike a
standard autoscaler, a CSA can select among multiple strategies and, subject to
RBAC, update more than a workload's replica count.

This repository is the reproducible experiment environment for the CSA project.
It creates a local multi-node Kubernetes cluster, deploys the observability and
image-registry services needed by the experiments, runs a controlled workload
against several autoscaling configurations, and turns the collected metrics
into comparison data and plots.

The other project repositories are:

- [custom-self-adapter](https://github.com/custom-self-adapter/custom-self-adapter),
  which contains the CSA runtime and base images.
- [custom-self-adapter-operator](https://github.com/custom-self-adapter/custom-self-adapter-operator),
  which installs the `CustomSelfAdapter` API and manages CSA Pods and RBAC.

## What the lab contains

- `vagrant-kubeadm-kubernetes/`: Vagrant/VirtualBox cluster definition.
- `cluster_bootstrap.sh`, `helmfile_step*.yaml`, `bootstrapping/`, and
  `values/`: cluster services and lab-specific configuration.
- `kube-znn/`: ZNN target application, fidelity-specific images, and Kubernetes
  manifests.
- `autoscalers/`: HPA, VPA, CPA, and CSA configurations.
- `tests/scenarios/`: Locust load shapes.
- `run_tests.sh`: complete comparison suite.
- `extract_prom.py`: Prometheus data extraction used at the end of each load
  test.
- `build_comparison_summary.py` and `plot_*.py`: analysis-data and plot
  generation.
- `tests/results/`: raw CSVs, derived CSVs, and generated figures.

The default Vagrant topology has one control-plane VM and three worker VMs.
Each VM receives 2 vCPUs and 3 GiB of RAM. The bootstrap assigns the application
to `node01`, database and adaptation workloads to `node02`, and registry and
monitoring workloads to `node03`.

## Prerequisites

Install these tools on the host:

- Git with SSH access to the two Git submodules.
- Vagrant and VirtualBox.
- `kubectl`, Helm, and Helmfile.
- Docker, for building and pushing experiment images.
- Python 3.12 or later, for Locust and analysis scripts.
- A Unix-like shell environment with Bash.

The default cluster requires at least 8 available virtual CPUs and 12 GiB of RAM
for its VMs, in addition to resources used by the host.

Clone the repository together with its submodules:

```bash
git clone --recurse-submodules \
  git@github.com:custom-self-adapter/k8s-autoscaling-lab.git
cd k8s-autoscaling-lab
```

If the repository was cloned without them:

```bash
git submodule update --init --recursive
```

## Create the cluster

### 1. Review the Vagrant settings

The current defaults in `vagrant-kubeadm-kubernetes/settings.yaml` create:

- Kubernetes `1.35.3-*`;
- a control plane at `10.0.0.10`;
- three workers at `10.0.0.11` through `10.0.0.13`;
- Calico networking;
- a custom root CA shared by the lab services.

Keep three workers unless `cluster_bootstrap.sh` is updated too, because it
labels `node01`, `node02`, and `node03` explicitly. Make sure the selected host
network is allowed by VirtualBox; on Linux this may require a matching range in
`/etc/vbox/networks.conf`.

### 2. Start and provision the VMs

```bash
cd vagrant-kubeadm-kubernetes
vagrant up
vagrant status
cd ..
```

Vagrant runs the provisioning scripts in
`vagrant-kubeadm-kubernetes/scripts/`. They install Kubernetes, initialize the
control plane, join the workers, install Calico and Metrics Server, generate the
lab CA, and save the admin kubeconfig.

Use that kubeconfig from the repository root:

```bash
export KUBECONFIG="$PWD/vagrant-kubeadm-kubernetes/configs/config"

kubectl cluster-info
kubectl get nodes -o wide
kubectl get pods -A
```

All four nodes should become `Ready` before continuing.

### 3. Trust the lab CA on the host

With `custom_ca: true`, Vagrant writes the CA certificate and key below
`vagrant-kubeadm-kubernetes/certs/`. Locust reads the certificate directly, but
the host and Docker must also trust it to access the HTTPS endpoints and push to
`registry.k8s.lab`.

On Debian and derivatives:

```bash
sudo cp vagrant-kubeadm-kubernetes/certs/rootCA.crt \
  /usr/local/share/ca-certificates/k8s-lab-root-ca.crt
sudo update-ca-certificates
sudo systemctl restart docker
```

Use the equivalent system and container-runtime trust-store procedure on other
platforms. The generated `rootCA.key` is sensitive lab material; do not copy or
publish it outside this disposable environment.

### 4. Bootstrap the lab services

Run the bootstrap from the repository root:

```bash
./cluster_bootstrap.sh
```

The script labels the nodes, pins Metrics Server to the monitoring node, and
uses the two Helmfile stages plus the manifests in `bootstrapping/` to install:

- cert-manager, MetalLB, and local-path storage;
- an in-cluster Docker registry;
- Prometheus, Grafana, and Prometheus Adapter;
- ingress-nginx;
- the Custom Self-Adapter Operator.

Verify the resulting cluster:

```bash
helmfile list -f helmfile_step1.yaml
helmfile list -f helmfile_step2.yaml
kubectl get pods -A
kubectl get crd customselfadapters.custom-self-adapter.net
kubectl get svc -n ingress-nginx ingress-nginx-controller
```

Wait until workloads are `Running` or `Completed`, and confirm that the ingress
controller has an external IP.

### 5. Configure the lab hostnames

Read the MetalLB address assigned to ingress-nginx:

```bash
kubectl get svc ingress-nginx-controller -n ingress-nginx \
  -o jsonpath='{.status.loadBalancer.ingress[0].ip}{"\n"}'
```

Add that address to the host's `/etc/hosts`. With the current address pool it is
normally:

```text
10.0.0.15 grafana.k8s.lab prometheus.k8s.lab registry.k8s.lab znn.k8s.lab
```

Validate the endpoints after their backing workloads have been deployed:

```bash
curl --cacert vagrant-kubeadm-kubernetes/certs/rootCA.crt \
  https://prometheus.k8s.lab/-/ready
curl --cacert vagrant-kubeadm-kubernetes/certs/rootCA.crt \
  https://registry.k8s.lab/v2/
```

## Build and deploy the experiment images

### CSA runtime image

The CSA experiment image currently starts from
`registry.k8s.lab/custom-self-adapter:python-3-12-latest`. Build that base from
the `custom-self-adapter` repository with its Makefile, then push the required
tag. If it is not already next to the lab clone, clone it first:

```bash
cd ..
git clone git@github.com:custom-self-adapter/custom-self-adapter.git
cd custom-self-adapter
mkdir -p dist/linux_amd64
make REGISTRY=registry.k8s.lab VERSION=latest
docker push registry.k8s.lab/custom-self-adapter:python-3-12-latest
cd ../k8s-autoscaling-lab
```

If the runtime repository already exists as a sibling, skip the `git clone`
line.

### ZNN application images

`kube-znn/build.sh` builds and pushes the `20k`, `100k`, `200k`, `400k`, `600k`,
and `800k` fidelity variants:

```bash
cd kube-znn
./build.sh
cd ..
```

Pass another repository as the first argument when not using the lab registry:

```bash
cd kube-znn
./build.sh REGISTRY/znn
cd ..
```

Deploy one variant and wait for both the application and database:

```bash
kubectl apply -k kube-znn/manifests/overlay/800k/
kubectl rollout status deployment/kube-znn
kubectl rollout status deployment/kube-znn-db
kubectl get deployment,pod,service,ingress

curl --cacert vagrant-kubeadm-kubernetes/certs/rootCA.crt \
  https://znn.k8s.lab/readiness.php
```

### CSA policy images

`autoscalers/csa/` contains the Python policy used by the CSA scenarios. Its
`build_csa-python.sh` builds and pushes the tag selected by `TAG`, then renders
`custom-selfadapter-${TAG}.yaml` from the template. The current script defaults
to `vq`.

Before producing a scenario image, review `config.yaml`, the enabled strategies,
and the `IMAGE`/`TAG` variables in the script:

```bash
cd autoscalers/csa
./build_csa-python.sh
cd ../..
```

The committed manifests expect the tags `h`, `hq`, `v`, and `vq`. Rebuild each
tag after making the corresponding policy/configuration change.

The lab repository itself has no Makefile: it is an orchestration and analysis
repository. Changes to the CSA runtime and operator are compiled and packaged
with the Makefiles in their respective repositories; lab application and policy
images are built by the scripts above.

## Run the comparison suite

### 1. Prepare Python

From the repository root:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

Before running the full suite, confirm:

- `znn.k8s.lab` and `prometheus.k8s.lab` resolve to the ingress IP;
- the ZNN and CSA images exist in `registry.k8s.lab`;
- the CSA CRD is installed;
- Prometheus exposes the ZNN metric series;
- the Vertical Pod Autoscaler CRD and controllers are installed.

VPA is referenced by `autoscalers/vpa/znn.yaml`, but is not installed by
`cluster_bootstrap.sh`. The current upstream VPA `1.7.x` supports Kubernetes
`1.35` and its `InPlaceOrRecreate` mode. Install it before running this suite,
following the
[upstream installation procedure](https://github.com/kubernetes/autoscaler/blob/master/vertical-pod-autoscaler/docs/installation.md):

```bash
cd ..
git clone https://github.com/kubernetes/autoscaler.git
cd autoscaler/vertical-pod-autoscaler
./hack/vpa-up.sh
cd ../../k8s-autoscaling-lab
```

The installer uses the current kubeconfig and creates cluster-scoped resources
and three VPA components in `kube-system`. Check their availability with:

```bash
kubectl api-resources | grep -i verticalpodautoscaler
kubectl get crd verticalpodautoscalers.autoscaling.k8s.io
kubectl get pods -n kube-system | grep vpa
```

Do not run the complete `run_tests.sh` without VPA: the script has no
`--skip-vpa` option and would still generate a `_vpa.csv` file after the
failed `kubectl apply`, producing an invalid comparison.

### 2. Execute tests

Run one iteration first:

```bash
./run_tests.sh 1
```

When no argument is supplied, the script runs 50 iterations:

```bash
./run_tests.sh
```

Each iteration exercises these configurations:

- one- and five-replica baselines;
- standard and fast-scale-down HPA;
- horizontal CSA;
- horizontal plus quality CSA with 25% and 50% rollout settings;
- a fixed 1.5-CPU baseline;
- VPA;
- vertical CSA;
- vertical plus quality CSA.

Locust runs a five-minute double-wave load with four worker processes for each
configuration. Including the cooldowns, one complete iteration takes about one
hour. Run the command in a durable terminal session and keep the cluster and
host awake.

At the end of every Locust run, `extract_prom.py` queries the previous five
minutes from Prometheus and merges those series with Locust users, response
times, response sizes, and status codes. With the default 50 iterations, raw
results are written to `tests/results/` using:

```text
<two-digit-run>_<order>_<configuration>.csv
```

For example: `01_3_csa_h.csv`.

The summary builder currently accepts exactly two digits in the run prefix.
Because `seq -w 1 1` produces `1`, the one-iteration smoke command creates
`1_*.csv`; rename that prefix to `01_` before passing those files to
`build_comparison_summary.py`. Runs with a total of 10 or more are padded by the
test script automatically.

## Build analysis data and plots

Activate the Python environment before running the analysis scripts:

```bash
source .venv/bin/activate
```

### Extract the latest Prometheus window manually

This writes the last five minutes to a timestamped CSV:

```bash
python extract_prom.py
```

Set `PROM_EXTRACT_NAME` to select the output basename:

```bash
PROM_EXTRACT_NAME=manual_check python extract_prom.py
```

The result is written to `tests/results/manual_check.csv`.

### Build comparison datasets

Convert all raw files matching
`<run>_<order>_<configuration>.csv` into per-run and aggregate datasets:

```bash
python build_comparison_summary.py
```

This creates:

- `tests/results/compare_runs.csv`: one row of calculated metrics per run and
  configuration.
- `tests/results/compare_summary.csv`: mean, min, max, median, standard
  deviation, and quartiles by configuration and metric.

Use `--results-dir`, `--runs-csv`, and `--summary-csv` to change the paths.

### Generate aggregate and Pareto plots

Build the aggregate boxplots:

```bash
python plot_comparison_aggregated.py
```

The default output is `tests/results/compare_aggregated.png`. Use
`--plot-metrics` to select a comma-separated subset and `--show` to also open an
interactive window.

Build the resource/SLO bubble plot and Pareto data:

```bash
python plot_comparison_bubble.py \
  --response-size-objective ignore
```

This creates `tests/results/compare_bubble.png` and
`tests/results/compare_pareto.csv`. The response-size objective can be
`ignore`, `minimize`, or `maximize`.

### Generate a plot for one run

```bash
python plot_graphs.py \
  tests/results/01_3_csa_h.csv \
  tests/results/01_3_csa_h.png
```

Omit the PNG argument to display the plot interactively.

### Generate the exemplar catalog

`generate_exemplars.py` reads `tests/results/exemplars.json`, renders every
listed CSV through `plot_graphs.py`, and rebuilds the Markdown catalog:

```bash
python generate_exemplars.py
```

It writes the figures beside the source CSVs and updates
`tests/results/exemplars.md`.

`plot_comparison.py` remains available for a manually selected, JSON-defined
set of raw files:

```bash
python plot_comparison.py comparison_p95_hpa_csa.json
```

Update the filenames in that JSON before using it with a new experiment.

## Stop or remove the cluster

Preserve the VMs without using host resources:

```bash
cd vagrant-kubeadm-kubernetes
vagrant halt
```

Permanently remove the lab VMs and their local cluster state:

```bash
cd vagrant-kubeadm-kubernetes
vagrant destroy -f
```

The CSV and plot files under `tests/results/` remain in the Git working tree.

## License

The two submodules retain their own licenses. Refer to each component
repository for its licensing terms.
