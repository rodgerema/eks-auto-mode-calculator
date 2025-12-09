#!/usr/bin/env python3
import boto3
import sys
from collections import Counter
from datetime import datetime, timedelta

def get_cluster_info(cluster_name, region):
    """Obtiene información del cluster EKS"""
    eks = boto3.client('eks', region_name=region)
    try:
        response = eks.describe_cluster(name=cluster_name)
        return response['cluster']
    except Exception as e:
        print(f"❌ Error obteniendo info del cluster: {e}", file=sys.stderr)
        return None

def get_cluster_nodes(cluster_name, region):
    """Obtiene los nodos EC2 del cluster EKS"""
    ec2 = boto3.client('ec2', region_name=region)
    try:
        response = ec2.describe_instances(
            Filters=[
                {'Name': 'tag:eks:cluster-name', 'Values': [cluster_name]},
                {'Name': 'instance-state-name', 'Values': ['running']}
            ]
        )
        
        instances = []
        for reservation in response['Reservations']:
            for instance in reservation['Instances']:
                instances.append({
                    'instance_id': instance['InstanceId'],
                    'instance_type': instance['InstanceType'],
                    'launch_time': instance['LaunchTime']
                })
        return instances
    except Exception as e:
        print(f"❌ Error obteniendo nodos: {e}", file=sys.stderr)
        return []

def get_cpu_utilization(cluster_name, region, days=7):
    """Obtiene utilización promedio de CPU desde CloudWatch"""
    cloudwatch = boto3.client('cloudwatch', region_name=region)
    try:
        end_time = datetime.now(datetime.UTC) if hasattr(datetime, 'UTC') else datetime.utcnow()
        start_time = end_time - timedelta(days=days)
        
        response = cloudwatch.get_metric_statistics(
            Namespace='ContainerInsights',
            MetricName='node_cpu_utilization',
            Dimensions=[
                {'Name': 'ClusterName', 'Value': cluster_name}
            ],
            StartTime=start_time,
            EndTime=end_time,
            Period=3600,
            Statistics=['Average']
        )
        
        if response['Datapoints']:
            avg_cpu = sum(dp['Average'] for dp in response['Datapoints']) / len(response['Datapoints'])
            return round(avg_cpu, 2)
        return None
    except Exception as e:
        print(f"⚠️  No se pudo obtener CPU de CloudWatch: {e}", file=sys.stderr)
        return None

def get_memory_utilization(cluster_name, region, days=7):
    """Obtiene utilización promedio de memoria desde CloudWatch"""
    cloudwatch = boto3.client('cloudwatch', region_name=region)
    try:
        end_time = datetime.now(datetime.UTC) if hasattr(datetime, 'UTC') else datetime.utcnow()
        start_time = end_time - timedelta(days=days)
        
        response = cloudwatch.get_metric_statistics(
            Namespace='ContainerInsights',
            MetricName='node_memory_utilization',
            Dimensions=[
                {'Name': 'ClusterName', 'Value': cluster_name}
            ],
            StartTime=start_time,
            EndTime=end_time,
            Period=3600,
            Statistics=['Average']
        )
        
        if response['Datapoints']:
            avg_mem = sum(dp['Average'] for dp in response['Datapoints']) / len(response['Datapoints'])
            return round(avg_mem, 2)
        return None
    except Exception as e:
        print(f"⚠️  No se pudo obtener memoria de CloudWatch: {e}", file=sys.stderr)
        return None

def main():
    print("Nombre del cluster EKS: ", end='', file=sys.stderr, flush=True)
    cluster_name = input().strip() or "ppay-arg-dev-eks-tools"
    
    print("Región AWS (default: us-east-1): ", end='', file=sys.stderr, flush=True)
    region = input().strip() or "us-east-1"
    
    print(f"\n⏳ Recolectando datos del cluster {cluster_name} en {region}...", file=sys.stderr)
    
    # Obtener información del cluster
    cluster_info = get_cluster_info(cluster_name, region)
    if not cluster_info:
        sys.exit(1)
    
    print(f"✅ Cluster encontrado: {cluster_info['name']} (versión {cluster_info['version']})", file=sys.stderr)
    
    # Obtener nodos
    instances = get_cluster_nodes(cluster_name, region)
    if not instances:
        print("❌ No se encontraron nodos en el cluster", file=sys.stderr)
        sys.exit(1)
    
    node_count = len(instances)
    instance_types = [inst['instance_type'] for inst in instances]
    primary_instance = Counter(instance_types).most_common(1)[0][0]
    
    print(f"✅ Nodos encontrados: {node_count} ({primary_instance})", file=sys.stderr)
    
    # Obtener métricas de utilización
    cpu_util = get_cpu_utilization(cluster_name, region)
    mem_util = get_memory_utilization(cluster_name, region)
    
    if cpu_util is None or mem_util is None:
        print("⚠️  CloudWatch Container Insights no disponible, usando valores por defecto", file=sys.stderr)
        cpu_util = 45.0
        mem_util = 60.0
    else:
        print(f"✅ Utilización CPU: {cpu_util}%, Memoria: {mem_util}%", file=sys.stderr)
    
    # Generar variables de entorno (a stdout)
    print(f"export EKS_PRIMARY_INSTANCE='{primary_instance}'")
    print(f"export EKS_NODE_COUNT='{node_count}'")
    print(f"export EKS_UTIL_CPU='{cpu_util}'")
    print(f"export EKS_UTIL_MEM='{mem_util}'")
    print(f"export AWS_REGION='{region}'")

if __name__ == "__main__":
    main()
