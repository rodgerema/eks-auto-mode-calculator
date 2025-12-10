#!/usr/bin/env python3
import boto3
import sys
from collections import Counter
from datetime import datetime, timedelta
from logger_utils import setup_logger, log_aws_api_call

# Configurar logging
logger = setup_logger('recolector_aws', 'eks_collector_aws.log')

def get_cluster_info(cluster_name, region):
    """Obtiene información del cluster EKS"""
    logger.info(f"Obteniendo información del cluster: {cluster_name} en {region}")
    eks = boto3.client('eks', region_name=region)
    try:
        log_aws_api_call(logger, 'EKS', 'describe_cluster', {'name': cluster_name})
        response = eks.describe_cluster(name=cluster_name)
        cluster = response['cluster']
        logger.info(f"Cluster encontrado: {cluster['name']}, versión: {cluster['version']}")
        log_aws_api_call(logger, 'EKS', 'describe_cluster', result=f"Cluster {cluster['name']}")
        return cluster
    except Exception as e:
        log_aws_api_call(logger, 'EKS', 'describe_cluster', error=str(e))
        print(f"❌ Error obteniendo info del cluster: {e}", file=sys.stderr)
        return None

def get_cluster_nodes(cluster_name, region):
    """Obtiene los nodos EC2 del cluster EKS"""
    logger.info(f"Buscando nodos EC2 para cluster: {cluster_name}")
    ec2 = boto3.client('ec2', region_name=region)
    filters = [
        {'Name': 'tag:eks:cluster-name', 'Values': [cluster_name]},
        {'Name': 'instance-state-name', 'Values': ['running']}
    ]
    
    try:
        log_aws_api_call(logger, 'EC2', 'describe_instances', {'Filters': filters})
        response = ec2.describe_instances(Filters=filters)
        
        instances = []
        for reservation in response['Reservations']:
            for instance in reservation['Instances']:
                instances.append({
                    'instance_id': instance['InstanceId'],
                    'instance_type': instance['InstanceType'],
                    'launch_time': instance['LaunchTime']
                })
        
        logger.info(f"Encontrados {len(instances)} nodos")
        if instances:
            types = [i['instance_type'] for i in instances]
            logger.info(f"Tipos de instancia: {Counter(types)}")
        
        log_aws_api_call(logger, 'EC2', 'describe_instances', result=f"{len(instances)} instancias")
        return instances
    except Exception as e:
        log_aws_api_call(logger, 'EC2', 'describe_instances', error=str(e))
        print(f"❌ Error obteniendo nodos: {e}", file=sys.stderr)
        return []

def get_cpu_utilization(cluster_name, region, days=7):
    """Obtiene utilización promedio de CPU desde CloudWatch"""
    logger.info(f"Obteniendo utilización CPU de CloudWatch para {cluster_name} (últimos {days} días)")
    cloudwatch = boto3.client('cloudwatch', region_name=region)
    try:
        end_time = datetime.now(datetime.UTC) if hasattr(datetime, 'UTC') else datetime.utcnow()
        start_time = end_time - timedelta(days=days)
        
        params = {
            'Namespace': 'ContainerInsights',
            'MetricName': 'node_cpu_utilization',
            'Dimensions': [{'Name': 'ClusterName', 'Value': cluster_name}],
            'StartTime': start_time,
            'EndTime': end_time,
            'Period': 3600,
            'Statistics': ['Average']
        }
        
        log_aws_api_call(logger, 'CloudWatch', 'get_metric_statistics', params)
        response = cloudwatch.get_metric_statistics(**params)
        
        if response['Datapoints']:
            avg_cpu = sum(dp['Average'] for dp in response['Datapoints']) / len(response['Datapoints'])
            result = round(avg_cpu, 2)
            logger.info(f"CPU utilización promedio: {result}% ({len(response['Datapoints'])} puntos de datos)")
            log_aws_api_call(logger, 'CloudWatch', 'get_metric_statistics', result=f"CPU: {result}%")
            return result
        else:
            logger.warning("No se encontraron datos de CPU en CloudWatch")
            return None
    except Exception as e:
        log_aws_api_call(logger, 'CloudWatch', 'get_metric_statistics', error=str(e))
        print(f"⚠️  No se pudo obtener CPU de CloudWatch: {e}", file=sys.stderr)
        return None

def get_memory_utilization(cluster_name, region, days=7):
    """Obtiene utilización promedio de memoria desde CloudWatch"""
    logger.info(f"Obteniendo utilización memoria de CloudWatch para {cluster_name} (últimos {days} días)")
    cloudwatch = boto3.client('cloudwatch', region_name=region)
    try:
        end_time = datetime.now(datetime.UTC) if hasattr(datetime, 'UTC') else datetime.utcnow()
        start_time = end_time - timedelta(days=days)
        
        params = {
            'Namespace': 'ContainerInsights',
            'MetricName': 'node_memory_utilization',
            'Dimensions': [{'Name': 'ClusterName', 'Value': cluster_name}],
            'StartTime': start_time,
            'EndTime': end_time,
            'Period': 3600,
            'Statistics': ['Average']
        }
        
        log_aws_api_call(logger, 'CloudWatch', 'get_metric_statistics', params)
        response = cloudwatch.get_metric_statistics(**params)
        
        if response['Datapoints']:
            avg_mem = sum(dp['Average'] for dp in response['Datapoints']) / len(response['Datapoints'])
            result = round(avg_mem, 2)
            logger.info(f"Memoria utilización promedio: {result}% ({len(response['Datapoints'])} puntos de datos)")
            log_aws_api_call(logger, 'CloudWatch', 'get_metric_statistics', result=f"Memoria: {result}%")
            return result
        else:
            logger.warning("No se encontraron datos de memoria en CloudWatch")
            return None
    except Exception as e:
        log_aws_api_call(logger, 'CloudWatch', 'get_metric_statistics', error=str(e))
        print(f"⚠️  No se pudo obtener memoria de CloudWatch: {e}", file=sys.stderr)
        return None

def get_real_cost_from_cost_explorer(cluster_name, region, instance_ids, days=30):
    """Obtiene el costo real de EC2 del cluster desde Cost Explorer (últimos 30 días)"""
    ce = boto3.client('ce', region_name='us-east-1')  # Cost Explorer siempre en us-east-1
    try:
        # Terminar 2 días antes de hoy para evitar problemas de consolidación
        end_date = datetime.now().date() - timedelta(days=2)
        start_date = end_date - timedelta(days=days)
        
        # Intentar primero con filtro de tags
        try:
            response = ce.get_cost_and_usage(
                TimePeriod={
                    'Start': start_date.strftime('%Y-%m-%d'),
                    'End': end_date.strftime('%Y-%m-%d')
                },
                Granularity='DAILY',
                Metrics=['UnblendedCost'],
                Filter={
                    'And': [
                        {
                            'Dimensions': {
                                'Key': 'SERVICE',
                                'Values': ['Amazon Elastic Compute Cloud - Compute']
                            }
                        },
                        {
                            'Tags': {
                                'Key': 'eks:cluster-name',
                                'Values': [cluster_name]
                            }
                        }
                    ]
                }
            )
            
            if response['ResultsByTime']:
                total_cost = sum(float(result['Total']['UnblendedCost']['Amount']) 
                               for result in response['ResultsByTime'] 
                               if float(result['Total']['UnblendedCost']['Amount']) > 0)
                
                if total_cost > 0:
                    actual_days = (end_date - start_date).days
                    monthly_cost = (total_cost / actual_days) * 30 if actual_days > 0 else total_cost
                    return round(monthly_cost, 2)
        except Exception:
            pass
        
        # Fallback: intentar con instance IDs si están disponibles
        if instance_ids and len(instance_ids) <= 10:  # Límite de CE para valores
            try:
                response = ce.get_cost_and_usage(
                    TimePeriod={
                        'Start': start_date.strftime('%Y-%m-%d'),
                        'End': end_date.strftime('%Y-%m-%d')
                    },
                    Granularity='DAILY',
                    Metrics=['UnblendedCost'],
                    Filter={
                        'And': [
                            {
                                'Dimensions': {
                                    'Key': 'SERVICE',
                                    'Values': ['Amazon Elastic Compute Cloud - Compute']
                                }
                            },
                            {
                                'Dimensions': {
                                    'Key': 'INSTANCE_TYPE',
                                    'Values': list(set([inst['instance_type'] for inst in instance_ids]))
                                }
                            }
                        ]
                    },
                    GroupBy=[{'Type': 'DIMENSION', 'Key': 'INSTANCE_TYPE'}]
                )
                
                if response['ResultsByTime']:
                    total_cost = 0
                    for result in response['ResultsByTime']:
                        for group in result.get('Groups', []):
                            total_cost += float(group['Metrics']['UnblendedCost']['Amount'])
                    
                    if total_cost > 0:
                        actual_days = (end_date - start_date).days
                        monthly_cost = (total_cost / actual_days) * 30 if actual_days > 0 else total_cost
                        print(f"   (usando filtro por tipo de instancia como aproximación)", file=sys.stderr)
                        return round(monthly_cost, 2)
            except Exception:
                pass
        
        return None
    except Exception as e:
        print(f"⚠️  No se pudo obtener costo de Cost Explorer: {e}", file=sys.stderr)
        return None

def main():
    logger.info("=== INICIANDO RECOLECTOR AWS ===")
    
    print("Nombre del cluster EKS: ", end='', file=sys.stderr, flush=True)
    cluster_name = input().strip() or "ppay-arg-dev-eks-tools"
    
    print("Región AWS (default: us-east-1): ", end='', file=sys.stderr, flush=True)
    region = input().strip() or "us-east-1"
    
    logger.info(f"Parámetros: cluster={cluster_name}, region={region}")
    
    print(f"\n⏳ Recolectando datos del cluster {cluster_name} en {region}...", file=sys.stderr)
    
    # Obtener información del cluster
    cluster_info = get_cluster_info(cluster_name, region)
    if not cluster_info:
        logger.error("No se pudo obtener información del cluster")
        sys.exit(1)
    
    print(f"✅ Cluster encontrado: {cluster_info['name']} (versión {cluster_info['version']})", file=sys.stderr)
    
    # Obtener nodos
    instances = get_cluster_nodes(cluster_name, region)
    if not instances:
        logger.error("No se encontraron nodos en el cluster")
        print("❌ No se encontraron nodos en el cluster", file=sys.stderr)
        sys.exit(1)
    
    node_count = len(instances)
    instance_types = [inst['instance_type'] for inst in instances]
    primary_instance = Counter(instance_types).most_common(1)[0][0]
    
    logger.info(f"Nodos: {node_count}, Tipo principal: {primary_instance}")
    print(f"✅ Nodos encontrados: {node_count} ({primary_instance})", file=sys.stderr)
    
    # Obtener métricas de utilización
    cpu_util = get_cpu_utilization(cluster_name, region)
    mem_util = get_memory_utilization(cluster_name, region)
    
    if cpu_util is None or mem_util is None:
        logger.warning("CloudWatch Container Insights no disponible, usando valores por defecto")
        print("⚠️  CloudWatch Container Insights no disponible, usando valores por defecto", file=sys.stderr)
        cpu_util = 45.0
        mem_util = 60.0
    else:
        logger.info(f"Métricas obtenidas - CPU: {cpu_util}%, Memoria: {mem_util}%")
        print(f"✅ Utilización CPU: {cpu_util}%, Memoria: {mem_util}%", file=sys.stderr)
    
    # Obtener costo real desde Cost Explorer
    print(f"⏳ Consultando costo real en Cost Explorer...", file=sys.stderr)
    real_cost = get_real_cost_from_cost_explorer(cluster_name, region, instances)
    
    if real_cost:
        logger.info(f"Costo real obtenido: ${real_cost:.2f}/mes")
        print(f"✅ Costo real EC2 (últimos 30 días): ${real_cost:.2f}/mes", file=sys.stderr)
        print(f"   (incluye Savings Plans / Reserved Instances si aplica)", file=sys.stderr)
    else:
        logger.warning("No se pudo obtener costo real, se usarán precios On-Demand")
        print(f"⚠️  No se pudo obtener costo real, se usarán precios On-Demand", file=sys.stderr)
        real_cost = 0
    
    # Generar variables de entorno (a stdout)
    env_vars = {
        'EKS_PRIMARY_INSTANCE': primary_instance,
        'EKS_NODE_COUNT': str(node_count),
        'EKS_UTIL_CPU': str(cpu_util),
        'EKS_UTIL_MEM': str(mem_util),
        'AWS_REGION': region,
        'EKS_MONTHLY_COST': str(real_cost)
    }
    
    logger.info(f"Variables generadas: {env_vars}")
    
    for key, value in env_vars.items():
        print(f"export {key}='{value}'")
    
    logger.info("=== RECOLECTOR AWS COMPLETADO ===")

if __name__ == "__main__":
    main()
