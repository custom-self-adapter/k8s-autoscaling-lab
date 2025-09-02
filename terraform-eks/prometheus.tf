resource "helm_release" "kube_prometheus_stack" {
  name             = "prom"
  namespace        = "monitoring"
  create_namespace = true
  repository       = "https://prometheus-community.github.io/helm-charts"
  chart            = "kube-prometheus-stack"
  depends_on       = [null_resource.wait_for_coredns]

  values = [
    yamlencode({
      prometheusOperator = {
        nodeSelector = {
          workload = "monitoring"
        }
      }
      alertManager = {
        alertManagerSpec = {
          nodeSelector = {
            workload = "monitoring"
          }
        }
      }
      prometheus = {
        prometheusSpec = {
          nodeSelector = {
            workload = "monitoring"
          }
        }
      }
    })
  ]
}

resource "helm_release" "prometheus_adapter" {
  name             = "prometheus-adapter"
  namespace        = "monitoring"
  create_namespace = true
  repository       = "https://prometheus-community.github.io/helm-charts"
  chart            = "prometheus-adapter"

  values = [
    yamlencode({
      nodeSelector = {
        workload = "monitoring"
      }
      prometheus = {
        url = "http://prometheus-operated.monitoring.svc"
      }
      rules = {
        default = false
        external = [
          {
            seriesQuery = "nginx_ingress_controller_request_duration_seconds_bucket{ingress!=\"\"}"
            resources = {
              overrides = {
                exported_namespace = {
                  resource = "namespace"
                }
                ingress = {
                  resource = "ingress"
                }
              }
            }
            name = {
              as = "nginx_ingress_p95_ms"
            }
            metricsQuery = <<-EOT
              histogram_quantile(
                0.95,
                sum(rate(<<.Series>>{<<.LabelMatchers>>}[1m]))
                by (le, ingress, exported_namespace)
              ) * 1000
            EOT
          }
        ]
      }
    })
  ]

  depends_on = [
    helm_release.kube_prometheus_stack,
    helm_release.ingress_nginx
  ]
}

