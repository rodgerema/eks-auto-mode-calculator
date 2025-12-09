import os
import sys
import boto3
from datetime import datetime, timedelta
from collections import defaultdict

def parse_cpu(quantity):
    """Convierte unidades de K8s (m, n, o entero) a vCPU (float)."""
    if str(quantity).endswith('m'):
        return float(quantity[:-1]) / 1000
    if str(quantity).endswith('n'):
        return float(quantity[:-1]) / 1000000000
    return float(quantity)

def parse_memory(quantity):
    """Convierte unidades de K8s (Ki, Mi, Gi) a GiB (float)."""
    units = {'Ki': 2**10, 'Mi': 2**20, 'Gi': 2**30, 'Ti': 2**40}
    q_str = str(quantity)
    
    for unit, multiplier in units.items():
        if q_str.endswith(unit):
            return (float(q_str[:-len(unit)]) * multiplier) / (2**30)
    
    return float(q_str) / (2**30)

def collect_from_kubernetes():
    """Recolecta datos directamente del cluster Kubernetes."""
    from kubernetes import client, config
    
    config.load_kube_config()
    v1 = client.CoreV1Api()

    nodes = v1.list_node()
    node_count = 0
    instance_types = defaultdict(int)
    total_capacity_cpu = 0
    total_capacity_mem = 0

    for node in nodes.items:
        node_count += 1
        itype = node.metadata.labels.get('node.kubernetes.io/instance-type', 'unknown')
        instance_types[itype] += 1
        total_capacity_cpu += parse_cpu(node.status.allocatable['cpu'])
        total_capacity_mem += parse_memory(node.status.allocatable['memory'])

    primary_instance = max(instance_types, key=instance_types.get) if instance_types else "m5.large"

    pods = v1.list_pod_for_all_namespaces(field_selector='status.phase=Running')
    total_request_cpu = 0
    total_request_mem = 0

    for pod in pods.items:
        for container in pod.spec.containers:
            resources = container.resources
            if resources and resources.requests:
                if 'cpu' in resources.requests:
                    total_request_cpu += parse_cpu(resources.requests['cpu'])
                if 'memory' in resources.requests:
                    total_request_mem += parse_memory(resources.requests['memory'])

    util_cpu_pct = (total_request_cpu / total_capacity_cpu) * 100 if total_capacity_cpu > 0 else 0
    util_mem_pct = (total_request_mem / total_capacity_mem) * 100 if total_capacity_mem > 0 else 0

    return primary_instance, node_count, util_cpu_pct, util_mem_pct

def collect_from_aws(cluster_name, region):
    """Recolecta datos desde AWS APIs (EKS + EC2 + Cost Explorer)."""
    eks = boto3.client('eks', region_name=region)
    ec2 = boto3.client('ec2', region_name=region)
    ce = boto3.client('ce', region_name=region)
    
    # Obtener nodegroups del cluster
    print(f"🔍 Obteniendo información del cluster {cluster_name}...", file=sys.stderr)
    nodegroups = eks.list_nodegroups(clusterName=cluster_name)['nodegroups']
    
    instance_types = defaultdict(int)
    total_nodes = 0
    
    for ng_name in nodegroups:
        ng = eks.describe_nodegroup(clusterName=cluster_name, nodegroupName=ng_name)['nodegroup']
        instance_type = ng.get('instanceTypes', ['m5.large'])[0]
        desired_size = ng.get('scalingConfig', {}).get('desiredSize', 0)
        instance_types[instance_type] += desired_size
        total_nodes += desired_size
    
    primary_instance = max(instance_types, key=instance_types.get) if instance_types else "m5.large"
    
    # Obtener costos reales de Cost Explorer (últimos 30 días)
    print(f"💰 Consultando Cost Explorer para costos reales...", file=sys.stderr)
    end_date = datetime.now().date()
    start_date = end_date - timedelta(days=30)
    
    try:
        response = ce.get_cost_and_usage(
            TimePeriod={'Start': start_date.strftime('%Y-%m-%d'), 'End': end_date.strftime('%Y-%m-%d')},
            Granularity='MONTHLY',
            Filter={
                'And': [
                    {'Dimensions': {'Key': 'SERVICE', 'Values': ['Amazon Elastic Compute Cloud - Compute']}},
                    {'Tags': {'Key': 'eks:cluster-name', 'Values': [cluster_name]}}
                ]
            },
            Metrics=['UnblendedCost']
        )
        
        if response['ResultsByTime']:
            monthly_cost = float(response['ResultsByTime'][0]['Total']['UnblendedCost']['Amount'])
            print(f"✅ Costo mensual real (últimos 30 días): ${monthly_cost:.2f}", file=sys.stderr)
        else:
            monthly_cost = 0
    except Exception as e:
        print(f"⚠️ No se pudo obtener costo de Cost Explorer: {e}", file=sys.stderr)
        monthly_cost = 0
    
    # Estimación conservadora de utilización (50% si no tenemos datos del cluster)
    util_cpu_pct = 50.0
    util_mem_pct = 50.0
    
    return primary_instance, total_nodes, util_cpu_pct, util_mem_pct, monthly_cost

def main():
    print("⏳ Recolectando datos del cluster...", file=sys.stderr)
    print("", file=sys.stderr)
    
    # Preguntar método de recolección
    print("¿Tienes acceso directo al cluster de Kubernetes? (s/n): ", file=sys.stderr, end='')
    has_k8s_access = input().strip().lower() == 's'
    
    monthly_cost = 0
    
    if has_k8s_access:
        try:
            primary_instance, node_count, util_cpu_pct, util_mem_pct = collect_from_kubernetes()
            print(f"✅ Datos recolectados: {node_count} nodos, Instancia {primary_instance}", file=sys.stderr)
        except Exception as e:
            print(f"❌ Error accediendo al cluster: {e}", file=sys.stderr)
            sys.exit(1)
    else:
        print("Nombre del cluster EKS: ", file=sys.stderr, end='')
        cluster_name = input().strip()
        print("Región AWS (ej: us-east-1): ", file=sys.stderr, end='')
        region = input().strip() or 'us-east-1'
        
        try:
            primary_instance, node_count, util_cpu_pct, util_mem_pct, monthly_cost = collect_from_aws(cluster_name, region)
            print(f"✅ Datos recolectados: {node_count} nodos, Instancia {primary_instance}", file=sys.stderr)
        except Exception as e:
            print(f"❌ Error consultando AWS: {e}", file=sys.stderr)
            sys.exit(1)
    
    # Generar variables de entorno
    print(f"export EKS_PRIMARY_INSTANCE='{primary_instance}'")
    print(f"export EKS_NODE_COUNT='{node_count}'")
    print(f"export EKS_UTIL_CPU='{util_cpu_pct:.2f}'")
    print(f"export EKS_UTIL_MEM='{util_mem_pct:.2f}'")
    print(f"export EKS_MONTHLY_COST='{monthly_cost:.2f}'")

if __name__ == "__main__":
    main()

if __name__ == "__main__":
    main()