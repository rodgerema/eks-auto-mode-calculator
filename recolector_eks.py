import sys
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

def main():
    try:
        primary_instance, node_count, util_cpu_pct, util_mem_pct = collect_from_kubernetes()
        print(f"✅ Datos recolectados: {node_count} nodos, Instancia {primary_instance}", file=sys.stderr)
    except Exception as e:
        print(f"❌ Error accediendo al cluster: {e}", file=sys.stderr)
        sys.exit(1)
    
    # Generar variables de entorno
    print(f"export EKS_PRIMARY_INSTANCE='{primary_instance}'")
    print(f"export EKS_NODE_COUNT='{node_count}'")
    print(f"export EKS_UTIL_CPU='{util_cpu_pct:.2f}'")
    print(f"export EKS_UTIL_MEM='{util_mem_pct:.2f}'")

if __name__ == "__main__":
    main()