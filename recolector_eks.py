import os
import sys
from kubernetes import client, config
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
            # Devolvemos en GiB para estandarizar
            return (float(q_str[:-len(unit)]) * multiplier) / (2**30)
    
    # Si viene en bytes puros o 'e' notación
    return float(q_str) / (2**30)

def main():
    try:
        # Intenta cargar la config del archivo ~/.kube/config
        # Si estás dentro de un pod, usarías config.load_incluster_config()
        config.load_kube_config()
    except Exception as e:
        print(f"Error cargando configuración de K8s: {e}", file=sys.stderr)
        print("Asegúrate de haber ejecutado: aws eks update-kubeconfig ...", file=sys.stderr)
        sys.exit(1)

    v1 = client.CoreV1Api()

    print("⏳ Recolectando datos del cluster...", file=sys.stderr)

    # 1. Obtener Nodos e Instancias
    nodes = v1.list_node()
    node_count = 0
    instance_types = defaultdict(int)
    total_capacity_cpu = 0
    total_capacity_mem = 0

    for node in nodes.items:
        node_count += 1
        # Detectar tipo de instancia desde los labels estándar
        itype = node.metadata.labels.get('node.kubernetes.io/instance-type', 'unknown')
        instance_types[itype] += 1
        
        # Capacidad total (allocatable)
        total_capacity_cpu += parse_cpu(node.status.allocatable['cpu'])
        total_capacity_mem += parse_memory(node.status.allocatable['memory'])

    # Encontrar la instancia más común (moda) para el cálculo base
    primary_instance = max(instance_types, key=instance_types.get) if instance_types else "m5.large"

    # 2. Obtener Pods y Requests
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

    # Calcular utilización basada en requests vs capacidad actual
    # (Esto simula qué tan lleno "cree" Kubernetes que está el cluster)
    util_cpu_pct = (total_request_cpu / total_capacity_cpu) * 100 if total_capacity_cpu > 0 else 0
    util_mem_pct = (total_request_mem / total_capacity_mem) * 100 if total_capacity_mem > 0 else 0

    # 3. Generar Output para ser consumido (source) o leído por Python
    # Imprimimos en formato compatible con bash export
    print(f"export EKS_PRIMARY_INSTANCE='{primary_instance}'")
    print(f"export EKS_NODE_COUNT='{node_count}'")
    print(f"export EKS_UTIL_CPU='{util_cpu_pct:.2f}'")
    print(f"export EKS_UTIL_MEM='{util_mem_pct:.2f}'")
    
    # Debug visual en stderr para no ensuciar el pipe
    print(f"✅ Datos recolectados: {node_count} nodos, Instancia {primary_instance}", file=sys.stderr)

if __name__ == "__main__":
    main()