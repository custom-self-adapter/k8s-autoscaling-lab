########################################
# Control-plane
########################################
module "cp" {
  source  = "terraform-aws-modules/ec2-instance/aws"
  version = "~> 6.1"

  name                        = "${var.cluster_name}-cp"
  ami                         = data.aws_ami.al2023.id
  instance_type               = "t3a.small"
  subnet_id                   = module.vpc.public_subnets[0]
  vpc_security_group_ids      = [aws_security_group.k8s.id]
  associate_public_ip_address = false
  iam_instance_profile        = aws_iam_instance_profile.ssm_ec2.name

  tags = merge(local.tags, { "role" = "control-plane" })
}

########################################
# Workers
########################################
module "workers" {
  source  = "terraform-aws-modules/ec2-instance/aws"
  version = "~> 6.1"

  for_each = local.node_pools

  name                        = "${var.cluster_name}-worker-${each.key}"
  ami                         = data.aws_ami.al2023.id
  instance_type               = each.value.instance_type
  subnet_id                   = module.vpc.public_subnets[0]
  vpc_security_group_ids      = [aws_security_group.k8s.id]
  associate_public_ip_address = false
  iam_instance_profile        = aws_iam_instance_profile.ssm_ec2.name

  tags = merge(local.tags, each.value.node_labels, {
    "role" = "worker"
  })
}
