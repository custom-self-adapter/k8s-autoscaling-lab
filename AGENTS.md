# Repository Guidelines

## Project Structure & Module Organization

`autoscalers/` holds Python/Java CSA code and HPA, VPA, and CPA manifests. Java code/tests are in `autoscalers/csa-java/src/{main,test}/java`; fixtures are in `contracts/cases/`. Cluster definitions live in `charts/`, `values/`, `bootstrapping/`, and `helmfile_step*.yaml`. `kube-znn/` and `vagrant-kubeadm-kubernetes/` are submodules. Locust scenarios are in `tests/scenarios/`, outputs in `tests/results/`, and Python scripts analyze them.

K8S Autoscaling Lab is divided into
1. **AutoScalers** — These are Kubernetes self-adaptation tools config files that will undergo a benchmarking process to determine which one performs best under specific load testing scenarios. Uses HPA, VPA and CSA(This is a operator created by me, for self-adaption strategys with any code language)
2. **Kube Znn** — It is the git submodule of the sample application that will be used to run the tests. Built in pure php and exposes a simple image
3. **Vagrant Kubeadm Kubernetes** — It is a famous script for creating a Kubernetes cluster using the kubeadm tool. Built in vagrant and shell scripts.
4. **Tests** — It is the folder containing the Locust test scenario scripts, the results folder, and the notebooks folder, where we save the Jupyter notebooks used to analyze the results.
5. **Some scripts** — At the root of the repository, we find several utility scripts that we will use to configure the cluster, run tests, extract information from the results, and manage components.


## Dependencies

### CSA Java

- Pure Java. No external tools
- Gradle
- Packages: JUnit, Kubernetes client, Gson, and SnakeYAML.

### CSA and CPA Python

- Pure Python. No external tools
- Packages: Kubernetes Python client, PyYAML

### Experiments and Analysis

- Python
- Locust

### Local Kubernetes Lab

- Ubuntu 24.04, Kubernetes 1.35.3, and Calico 3.31.4.
- Packages: Git, Vagrant, VirtualBox, Docker, kubectl, Helmfile, and envsubst.

## Autoscalers

All benchmark autoscalers target the `kube-znn` Deployment. CSA and HPA use the external `znn_latency_ms_p95` metric with a target value of `1000`.

### CSA Python (`autoscalers/csa/`)

- **`config.yaml`** — Wires the metric, evaluation, and adaptation shell hooks. The checked-in profile runs every 5 seconds, permits 1–5 replicas and up to `750m` CPU, and enables CPU and tag adaptation.
- **`custom-selfadapter-{h,hq,v,vq}.yaml`** — Select the packaged horizontal, horizontal-plus-tag, vertical CPU, and vertical-plus-tag profiles. The manifests otherwise target the same Deployment and grant access to `pods/resize`.
- **`scripts/metric_nginx_req_duration.py`** — Passes the current replica count and external metric target/current values to the evaluator.
- **`scripts/evaluate.py`** — Computes the load ratio. At `>= 0.95`, it tries replicas, CPU, then a lower image tag; below `0.90`, it applies the inverse adjustments. The `0.90–0.95` band is a no-op, and disabled strategies are skipped.
- **`scripts/adapt_replicas.py`** — Patches `Deployment.spec.replicas` with the evaluator's bounded replica count.
- **`scripts/adapt_cpu.py`** — Resizes CPU limits for the running `znn` and `nginx` containers, bounded by the initial limit and `maxCPU`; skips active rollouts.
- **`scripts/adapt_tag.py`** — Moves the `znn` image through `100k`, `200k`, `400k`, `600k`, and `800k`; high load selects a lower tag, while spare capacity restores the initial quality.
- **`scripts/adapt_base.py`** — Provides shared stdin parsing, in-cluster clients, Deployment and Pod lookup, rollout checks, and CPU quantity conversion.
- **`scripts/initial_data.py`** — Persists the original image tag and CPU limit so later adaptations cannot cross their baseline.

### CSA-JAVA (`autoscalers/csa-java/`)

The Java port implements the same stdin/stdout strategy contract in one executable.

- **`config.yaml`** — Maps CSA phases to binary modes, polls every 5 seconds, bounds replicas at 1–5 and CPU at `1000m`, and currently enables CPU adaptation.
- **`src/main/java/org/csajava/App.java`** — Loads stdin and `/config.yaml`, validates the requested mode, dispatches it, and emits structured errors.
- **`src/main/java/org/csajava/runtime/ModeHandlers.java`** — Maps metric, evaluation, replica, CPU, and tag modes to their runtime handlers.
- **`src/main/java/org/csajava/runtime/metric/MetricRuntime.java`** — Validates and normalizes the external metric payload for evaluation.
- **`src/main/java/org/csajava/runtime/evaluate/EvaluateRuntime.java`** — Mirrors the Python thresholds, strategy priority, replica calculation, and configured CPU/replica bounds.
- **`src/main/java/org/csajava/runtime/adapt/replicas/AdaptReplicasRuntime.java`** — Applies horizontal scaling with a strategic merge patch on `spec.replicas`.
- **`src/main/java/org/csajava/runtime/adapt/cpu/AdaptCpuRuntime.java`** — Uses the Pod resize subresource for `znn` and `nginx`, clamping CPU between the stored baseline and `maxCPU`.
- **`src/main/java/org/csajava/runtime/adapt/tag/AdaptTagRuntime.java`** — Changes the image along the same tag ladder and skips changes during an active rollout.
- **`src/main/java/org/csajava/runtime/initialdata/InitialDataStore.java`** — Stores initial tag and CPU values through the CSA annotation/status contract.

### HPA (`autoscalers/hpa/`)

- **`znn.yaml`** — Scales `kube-znn` from 1 to 5 replicas against p95 latency `1000`; Kubernetes default behavior policies apply.
- **`znn_fast.yaml`** — Uses the same target and bounds, but reduces scale-down stabilization to 10 seconds and allows a 100% reduction every 15 seconds.

### VPA (`autoscalers/vpa/`)

- **`znn.yaml`** — Recreates Pods to apply CPU recommendations for `znn` and `nginx`, controlling requests and limits between `150m` and `500m`; memory is untouched.

Note: CPA is no longer used by the test scenarios.

## Build, Test, and Development Commands

- `git submodule update --init --recursive` initializes submodules.
- `python -m venv .venv && . .venv/bin/activate && pip install -r requirements.txt` creates the analysis environment.
- `(cd vagrant-kubeadm-kubernetes && vagrant up)` provisions the lab. Then export `KUBECONFIG="$PWD/vagrant-kubeadm-kubernetes/configs/config"` and run `./cluster_bootstrap.sh`.
- `cd autoscalers/csa-java && ./gradlew test` runs tests; `./gradlew build` builds Java.
- `./run_tests.sh 1` runs one destructive cluster matrix; no argument means 50 iterations.

## Coding Style & Naming Conventions

Use four spaces for Python/Java and two for YAML. No global formatter or linter exists; follow adjacent code. Python uses `snake_case` files/functions and `UPPER_SNAKE_CASE` constants. Java uses `PascalCase` types, `camelCase` members, and lowercase packages.

## Testing Guidelines

Write a failing test before non-trivial behavior changes. JUnit 4 tests mirror production packages and end in `Test.java`. Add dotted fixtures such as `evaluate.high_load_cpu.json` when contracts change. Locust scenarios are integration experiments. No coverage threshold exists; run Java tests, then the cluster matrix for manifest or adaptation changes.

## Commit & Pull Request Guidelines

- Never commit directly to `main` or any branch whose name starts with `csa-`. Make changes on a separate short-lived branch or Git worktree and submit a pull request to the intended protected branch.
- Name working branches using Conventional Branches style: `<type>/<short-kebab-case-description>`, with types aligned to Conventional Commits, such as `feat/`, `fix/`, `docs/`, `refactor/`, `test/`, `chore/`, or `perf/`.
- Keep each pull request focused on one objective. Limit production logic to at most 500 lines per pull request; tests, documentation, and configuration do not count toward this limit. Split larger changes into separate pull requests.
- Prefer removing or simplifying existing code over adding new code.
- Document all work, decisions, relevant commands, and validation results in the appropriate project documentation.

Use short, imperative Conventional Commit subjects, for example `fix(csa-java): handle null evaluation`. Keep one logical change per commit and stage explicitly. Pull requests explain scope and cluster impact, link applicable issues, and list verification. Attach plots for visual changes; avoid unrelated bulk results.

## Security & Configuration

Verify the Kubernetes context before running scripts. Never commit private keys, kubeconfigs, registry credentials, Terraform state, or generated certificates.
