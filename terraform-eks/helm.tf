resource "helm_release" "metrics_server" {
  name       = "metrics-server"
  repository = "https://kubernetes-sigs.github.io/metrics-server/"
  chart      = "metrics-server"
  # Fixe uma versão estável do chart (ex.: 3.13.0 no momento da escrita)
  version = "3.13.0"

  namespace        = "kube-system"
  create_namespace = false

  # Aguarde o cluster e o CoreDNS (você já tem um wait_coredns)
  # depends_on = [
  #   null_resource.wait_coredns
  # ]

  # Exemplos de overrides (descomente somente se precisar)
  # set {
  #   name  = "args.kubelet-preferred-address-types"
  #   value = "InternalIP,ExternalIP,Hostname"
  # }
  # set {
  #   name  = "args.kubelet-insecure-tls"
  #   value = "true"       # use SOMENTE se houver erro de TLS ao falar com os kubelets
  # }
  #
  # Se desejar fixar a porta segura do metrics-server (normalmente não precisa):
  # set { name = "containerPort" value = "10258" }
  #
  # Se quiser expor ServiceMonitor p/ Prometheus:
  # set { name = "metrics.enabled" value = "true" }
  # set { name = "metrics.serviceMonitor.enabled" value = "true" }
}

resource "helm_release" "ingress_nginx" {
  name             = "ingress-nginx"
  namespace        = "ingress-nginx"
  chart            = "ingress-nginx"
  repository       = "https://kubernetes.github.io/ingress-nginx"
  version          = "4.13.1"
  create_namespace = true

  # NÃO cria Service LoadBalancer
  values = [
    yamlencode({
      controller = {
        service = {
          external = {
            enabled = false
          }
          internal = {
            enabled = true
            annotations = {
              "service.beta.kubernetes.io/aws-load-balancer-backend-protocol"                  = "tcp"
              "service.beta.kubernetes.io/aws-load-balancer-type"                              = "nlb"
              "service.beta.kubernetes.io/aws-load-balancer-scheme"                            = "internal"
              "service.beta.kubernetes.io/aws-load-balancer-cross-zone-load-balancing-enabled" = "true"
              "service.beta.kubernetes.io/aws-load-balancer-internal"                          = "true"
            }
          }
        }

        # (opcional) para fixar scheduling/afinidade/tolerations, adicione aqui
        # nodeSelector = { "node.kubernetes.io/ingress" = "true" }
      }
    })
  ]
}

