CLUSTER_NAME = autoscaling-lab

up:          ## Cria cluster + instala charts
	./cluster/create.sh
	helmfile sync

load-test:   ## Exemplo de carga com k6 (assume k6 instalado)
	k6 run -o experimental-prom tests/scenarios/spike.js

down:        ## Remove tudo
	helmfile destroy
	./cluster/destroy.sh

.PHONY: up load-test down
