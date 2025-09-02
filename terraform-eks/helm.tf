resource "helm_release" "metrics_server" {
  name       = "metrics-server"
  repository = "https://kubernetes-sigs.github.io/metrics-server/"
  chart      = "metrics-server"
  # Fixe uma versão estável do chart (ex.: 3.13.0 no momento da escrita)
  version    = "3.13.0"
  depends_on = [null_resource.wait_for_coredns]

  namespace        = "kube-system"
  create_namespace = false

}

resource "helm_release" "ingress_nginx" {
  name             = "ingress-nginx"
  namespace        = "ingress-nginx"
  chart            = "ingress-nginx"
  repository       = "https://kubernetes.github.io/ingress-nginx"
  version          = "4.13.2"
  create_namespace = true

  depends_on = [helm_release.kube_prometheus_stack]

  # NÃO cria Service LoadBalancer
  values = [
    yamlencode({
      controller = {

        service = {
          enabled = true
          type    = "NodePort"
          nodePorts = {
            http  = 30080
            https = 0
          }
        }

        nodeSelector = {
          edge = "ingress"
        }
        podAnnotations = {
          "prometheus.io/scrape" = "true"
          "prometheus.io/port"   = "10254"
        }
        metrics = {
          enabled = true
          serviceMonitor = {
            enabled = true
            additionalLabels = {
              release = "prom"
            }
          }
        }
        extraArgs = {
          "metrics-per-host" = "false"
        }
      }
    })
  ]
}

