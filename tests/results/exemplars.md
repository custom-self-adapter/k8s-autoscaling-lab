# Featured Test Results

## Baseline - no Autoscaling
### 1 Replica Quality 800k
![tests/results/prom_extract_202601061948.csv](0_baseline_1_800k.png "Baseline 1 Replica")

### 3 Replicas Quality 800k
![tests/results/prom_extract_202601061954.csv](0_baseline_3_800k.png "Baseline 3 Replicas")

### 5 Replicas Quality 800k
![tests/results/prom_extract_202601062001.csv](0_baseline_5_800k.png "Baseline 5 Replicas")

### 1 Replica Quality 400k
![tests/results/prom_extract_202601062007.csv](0_baseline_1_400k.png "Baseline 1 Replica @400k")

### 3 Replicas Quality 400k
![tests/results/prom_extract_202601062013.csv](0_baseline_3_400k.png "Baseline 3 Replicas @400k")

### 5 Replicas Quality 400k
![tests/results/prom_extract_202601062019.csv](0_baseline_5_400k.png "Baseline 5 Replicas @400k")

### 1 Replica Quality 200k
![tests/results/prom_extract_202601062025.csv](0_baseline_1_200k.png "Baseline 1 Replica @200k")

### 3 Replicas Quality 200k
![tests/results/prom_extract_202601062032.csv](0_baseline_3_200k.png "Baseline 3 Replicas @200k")

### 5 Replicas Quality 200k
![tests/results/prom_extract_202601062038.csv](0_baseline_5_200k.png "Baseline 5 Replicas @200k")

## HPA Default Behavior
![tests/results/prom_extract_202601062044.csv](1_hpa_800k.png)

## HPA Behavior fast scaleDown
*stabilizationWindowSeconds=10*
![tests/results/prom_extract_202601062050.csv](1_hpa_fast_800k.png)

## CSA Horizontal (HPA-like)
![tests/results/prom_extract_202601062057.csv](2_csa_h.png)

## CSA Horizontal + Quality
### Deployment with maxSurge 25% and maxUnavailable 25%
![tests/results/prom_extract_202601062103.csv](3_csa_hq_surge25.png)

### Deployment with maxSurge 50% and maxUnavailable 50%
![tests/results/prom_extract_202601062109.csv](3_csa_hq_surge50.png)

### Deployment with maxSurge 75% and maxUnavailable 75%
![tests/results/prom_extract_202601062115.csv](3_csa_hq_surge75.png)

### Deployment with maxSurge 100% and maxUnavailable 100%
![tests/results/prom_extract_202601062121.csv](3_csa_hq_surge100.png)
