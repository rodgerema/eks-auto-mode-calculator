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

def get_ec2_cpu_utilization(instance_ids, region, days=7):
    """Obtiene CPUUtilization promedio de las instancias EC2 (métricas básicas)"""
    logger.info(f"Obteniendo métricas EC2 básicas para {len(instance_ids)} instancias (últimos {days} días)")
    cloudwatch = boto3.client('cloudwatch', region_name=region)

    try:
        end_time = datetime.now(datetime.UTC) if hasattr(datetime, 'UTC') else datetime.utcnow()
        start_time = end_time - timedelta(days=days)

        cpu_values = []
        for instance_id in instance_ids:
            params = {
                'Namespace': 'AWS/EC2',
                'MetricName': 'CPUUtilization',
                'Dimensions': [{'Name': 'InstanceId', 'Value': instance_id}],
                'StartTime': start_time,
                'EndTime': end_time,
                'Period': 3600,
                'Statistics': ['Average']
            }

            log_aws_api_call(logger, 'CloudWatch', 'get_metric_statistics',
                           {'instance': instance_id, 'metric': 'CPUUtilization'})
            response = cloudwatch.get_metric_statistics(**params)

            if response['Datapoints']:
                avg = sum(dp['Average'] for dp in response['Datapoints']) / len(response['Datapoints'])
                cpu_values.append(avg)
                logger.debug(f"Instancia {instance_id}: CPU {avg:.2f}%")

        if cpu_values:
            avg_cpu = sum(cpu_values) / len(cpu_values)
            result = round(avg_cpu, 2)
            logger.info(f"CPU utilización promedio EC2: {result}% ({len(cpu_values)} instancias)")
            log_aws_api_call(logger, 'CloudWatch', 'get_metric_statistics',
                           result=f"EC2 CPU: {result}%")
            return result
        else:
            logger.warning("No se encontraron datos de CPU en métricas EC2")
            return None

    except Exception as e:
        log_aws_api_call(logger, 'CloudWatch', 'get_metric_statistics', error=str(e))
        print(f"⚠️  No se pudo obtener CPU de métricas EC2: {e}", file=sys.stderr)
        return None

def analyze_asg_stability(cluster_name, region, days=30):
    """Analiza estabilidad del ASG para inferir sobreasignación"""
    logger.info(f"Analizando estabilidad del ASG para {cluster_name} (últimos {days} días)")

    try:
        asg = boto3.client('autoscaling', region_name=region)
        cloudwatch = boto3.client('cloudwatch', region_name=region)

        # Buscar ASG del cluster
        log_aws_api_call(logger, 'AutoScaling', 'describe_auto_scaling_groups',
                       {'cluster': cluster_name})
        response = asg.describe_auto_scaling_groups()

        cluster_asgs = [
            g for g in response['AutoScalingGroups']
            if any(cluster_name in tag.get('Value', '') for tag in g.get('Tags', []))
        ]

        if not cluster_asgs:
            logger.warning(f"No se encontraron ASGs para el cluster {cluster_name}")
            return {'scaling_observed': True, 'reason': 'no_asg_found'}

        logger.info(f"Encontrados {len(cluster_asgs)} ASGs para el cluster")

        scaling_observed = False
        for asg_data in cluster_asgs:
            asg_name = asg_data['AutoScalingGroupName']
            logger.info(f"Analizando ASG: {asg_name}")

            end_time = datetime.now(datetime.UTC) if hasattr(datetime, 'UTC') else datetime.utcnow()
            start_time = end_time - timedelta(days=days)

            # Obtener métrica de capacidad deseada
            params = {
                'Namespace': 'AWS/AutoScaling',
                'MetricName': 'GroupDesiredCapacity',
                'Dimensions': [{'Name': 'AutoScalingGroupName', 'Value': asg_name}],
                'StartTime': start_time,
                'EndTime': end_time,
                'Period': 86400,  # 1 día
                'Statistics': ['Minimum', 'Maximum']
            }

            log_aws_api_call(logger, 'CloudWatch', 'get_metric_statistics',
                           {'asg': asg_name, 'metric': 'GroupDesiredCapacity'})
            response = cloudwatch.get_metric_statistics(**params)

            if response['Datapoints']:
                min_cap = min(dp['Minimum'] for dp in response['Datapoints'])
                max_cap = max(dp['Maximum'] for dp in response['Datapoints'])

                logger.info(f"ASG {asg_name}: Min={min_cap}, Max={max_cap}")

                if min_cap != max_cap:
                    scaling_observed = True
                    logger.info(f"ASG {asg_name} ha escalado (variación de capacidad detectada)")

        if not scaling_observed:
            logger.warning("⚠️  Ningún ASG ha escalado en los últimos 30 días - cluster posiblemente sobreaprovisionado")
            log_aws_api_call(logger, 'AutoScaling', 'analyze_asg_stability',
                           result="No scaling observed")
            return {
                'scaling_observed': False,
                'reason': 'static_capacity',
                'suggestion': 'conservative_estimate'
            }

        log_aws_api_call(logger, 'AutoScaling', 'analyze_asg_stability',
                       result="Scaling observed")
        return {'scaling_observed': True}

    except Exception as e:
        log_aws_api_call(logger, 'AutoScaling', 'analyze_asg_stability', error=str(e))
        logger.error(f"Error analizando ASG: {e}")
        return {'scaling_observed': True, 'reason': 'error'}

def get_manual_utilization():
    """Permite al usuario ingresar utilización manualmente"""
    logger.info("Solicitando métricas manuales al usuario")
    print(f"\n⚠️  No se pudieron obtener métricas automáticas", file=sys.stderr)
    print(f"¿Deseas ingresar valores manualmente? (s/n): ", end='', file=sys.stderr, flush=True)

    response = input().strip().lower()

    if response == 's':
        try:
            print(f"Utilización CPU promedio (%): ", end='', file=sys.stderr, flush=True)
            cpu = float(input().strip())

            print(f"Utilización Memoria promedio (%): ", end='', file=sys.stderr, flush=True)
            mem = float(input().strip())

            if 0 <= cpu <= 100 and 0 <= mem <= 100:
                logger.info(f"Métricas manuales ingresadas: CPU={cpu}%, MEM={mem}%")
                return cpu, mem
            else:
                logger.warning("Valores fuera de rango (0-100)")
                print(f"⚠️  Valores deben estar entre 0 y 100", file=sys.stderr)
                return None, None

        except ValueError as e:
            logger.error(f"Error en input manual: {e}")
            print(f"⚠️  Error en los valores ingresados", file=sys.stderr)
            return None, None

    logger.info("Usuario optó por no ingresar valores manuales")
    return None, None

def get_real_cost_from_cost_explorer(cluster_name, region, instance_ids, days=30):
    """Obtiene el costo real de EC2 del cluster desde Cost Explorer usando aws:eks:cluster-name"""
    logger.info(f"Consultando Cost Explorer para cluster: {cluster_name} (últimos {days} días)")
    ce = boto3.client('ce', region_name='us-east-1')  # Cost Explorer siempre en us-east-1
    try:
        # Terminar 2 días antes de hoy para evitar problemas de consolidación
        end_date = datetime.now().date() - timedelta(days=2)
        start_date = end_date - timedelta(days=days)

        logger.info(f"Período de consulta: {start_date} a {end_date}")

        # Consulta optimizada usando aws:eks:cluster-name tag
        log_aws_api_call(logger, 'CostExplorer', 'get_cost_and_usage', {
            'cluster': cluster_name,
            'start': start_date,
            'end': end_date
        })

        response = ce.get_cost_and_usage(
            TimePeriod={
                'Start': start_date.strftime('%Y-%m-%d'),
                'End': end_date.strftime('%Y-%m-%d')
            },
            Granularity='DAILY',
            Metrics=['UnblendedCost', 'UsageQuantity'],
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
                            'Key': 'aws:eks:cluster-name',
                            'Values': [cluster_name]
                        }
                    }
                ]
            },
            GroupBy=[
                {'Type': 'DIMENSION', 'Key': 'INSTANCE_TYPE'}
            ]
        )

        if not response['ResultsByTime']:
            logger.warning("No se encontraron resultados en Cost Explorer")
            log_aws_api_call(logger, 'CostExplorer', 'get_cost_and_usage',
                           result="Sin resultados")
            return None

        # Calcular costo total y detalles por tipo de instancia
        total_cost = 0
        instance_type_costs = {}
        days_with_data = 0

        for result in response['ResultsByTime']:
            if result.get('Groups'):
                days_with_data += 1
                for group in result['Groups']:
                    instance_type = group['Keys'][0]
                    cost = float(group['Metrics']['UnblendedCost']['Amount'])
                    usage = float(group['Metrics']['UsageQuantity']['Amount'])

                    total_cost += cost

                    if instance_type not in instance_type_costs:
                        instance_type_costs[instance_type] = {'cost': 0, 'usage': 0}
                    instance_type_costs[instance_type]['cost'] += cost
                    instance_type_costs[instance_type]['usage'] += usage

        if total_cost > 0:
            actual_days = (end_date - start_date).days
            monthly_cost = (total_cost / actual_days) * 30 if actual_days > 0 else total_cost

            logger.info(f"Costo total en período: ${total_cost:.2f} ({days_with_data} días con datos)")
            logger.info(f"Costo mensual proyectado: ${monthly_cost:.2f}")

            # Log detalles por tipo de instancia
            for inst_type, data in sorted(instance_type_costs.items(),
                                         key=lambda x: x[1]['cost'], reverse=True):
                logger.info(f"  {inst_type}: ${data['cost']:.2f} "
                          f"({data['usage']:.2f} horas)")

            log_aws_api_call(logger, 'CostExplorer', 'get_cost_and_usage',
                           result=f"${monthly_cost:.2f}/mes")

            return round(monthly_cost, 2)
        else:
            logger.warning("No se encontraron costos en el período consultado")
            log_aws_api_call(logger, 'CostExplorer', 'get_cost_and_usage',
                           result="Sin costos")
            return None

    except Exception as e:
        logger.error(f"Error consultando Cost Explorer: {e}")
        log_aws_api_call(logger, 'CostExplorer', 'get_cost_and_usage', error=str(e))
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
    
    # Obtener métricas de utilización con cascada de fallback
    logger.info("=== Iniciando obtención de métricas de utilización ===")
    cpu_util = None
    mem_util = None
    metric_source = None

    # 1. Intentar Container Insights (más preciso)
    print(f"⏳ Intentando obtener métricas de Container Insights...", file=sys.stderr)
    cpu_util = get_cpu_utilization(cluster_name, region)
    mem_util = get_memory_utilization(cluster_name, region)

    if cpu_util is not None and mem_util is not None:
        metric_source = "Container Insights"
        logger.info(f"✅ Métricas obtenidas de Container Insights - CPU: {cpu_util}%, Memoria: {mem_util}%")
        print(f"✅ Utilización obtenida de Container Insights", file=sys.stderr)
        print(f"   CPU: {cpu_util}%, Memoria: {mem_util}%", file=sys.stderr)
    else:
        # 2. Intentar CloudWatch EC2 Metrics (alternativa)
        logger.warning("Container Insights no disponible, intentando métricas EC2 básicas...")
        print(f"⚠️  Container Insights no disponible", file=sys.stderr)
        print(f"⏳ Intentando obtener métricas EC2 básicas...", file=sys.stderr)

        instance_ids = [inst['instance_id'] for inst in instances]
        cpu_util_ec2 = get_ec2_cpu_utilization(instance_ids, region)

        if cpu_util_ec2 is not None:
            # Ajustar por overhead del host (kubelet, kube-proxy, containerd ~8%)
            cpu_util = max(cpu_util_ec2 - 8, 0)
            # Para memoria, usar CPU como proxy con ajuste típico
            mem_util = min(cpu_util + 15, 80)

            metric_source = "EC2 Metrics (ajustado)"
            logger.info(f"✅ Métricas obtenidas de EC2: CPU raw {cpu_util_ec2:.1f}% "
                       f"(ajustado a {cpu_util:.1f}%), MEM estimada {mem_util:.1f}%")
            print(f"✅ Utilización obtenida de métricas EC2 (ajustado por overhead)", file=sys.stderr)
            print(f"   CPU: {cpu_util:.1f}% (raw: {cpu_util_ec2:.1f}%), Memoria: {mem_util:.1f}% (estimada)", file=sys.stderr)
        else:
            # 3. Analizar estabilidad del ASG
            logger.warning("Métricas EC2 no disponibles, analizando patrones de ASG...")
            print(f"⚠️  Métricas EC2 no disponibles", file=sys.stderr)
            print(f"⏳ Analizando patrones de Auto Scaling Groups...", file=sys.stderr)

            asg_analysis = analyze_asg_stability(cluster_name, region)

            if not asg_analysis.get('scaling_observed'):
                # ASG estático = cluster probablemente sobreaprovisionado
                cpu_util = 30.0
                mem_util = 45.0
                metric_source = "ASG Analysis (conservador)"
                logger.warning("⚠️  ASG no ha escalado en 30 días - usando estimación conservadora")
                print(f"⚠️  ASG no ha escalado en 30 días - cluster posiblemente sobreaprovisionado", file=sys.stderr)
                print(f"   Usando valores conservadores: CPU: {cpu_util}%, Memoria: {mem_util}%", file=sys.stderr)
            else:
                # 4. Intentar input manual
                logger.info("ASG con escalado observado, ofreciendo input manual...")
                cpu_manual, mem_manual = get_manual_utilization()

                if cpu_manual is not None and mem_manual is not None:
                    cpu_util = cpu_manual
                    mem_util = mem_manual
                    metric_source = "Input Manual"
                    logger.info(f"✅ Métricas ingresadas manualmente - CPU: {cpu_util}%, Memoria: {mem_util}%")
                    print(f"✅ Utilizando valores manuales", file=sys.stderr)
                    print(f"   CPU: {cpu_util}%, Memoria: {mem_util}%", file=sys.stderr)
                else:
                    # 5. Fallback conservador (último recurso)
                    cpu_util = 35.0
                    mem_util = 50.0
                    metric_source = "Fallback (conservador)"
                    logger.warning("Usando valores de fallback conservadores")
                    print(f"⚠️  Usando valores de fallback conservadores", file=sys.stderr)
                    print(f"   CPU: {cpu_util}%, Memoria: {mem_util}%", file=sys.stderr)

    logger.info(f"Métricas finales - Fuente: {metric_source}, CPU: {cpu_util}%, MEM: {mem_util}%")
    print(f"   Fuente de métricas: {metric_source}", file=sys.stderr)
    
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
        'EKS_MONTHLY_COST': str(real_cost),
        'EKS_METRIC_SOURCE': metric_source
    }

    logger.info(f"Variables generadas: {env_vars}")
    
    for key, value in env_vars.items():
        print(f"export {key}='{value}'")
    
    logger.info("=== RECOLECTOR AWS COMPLETADO ===")

if __name__ == "__main__":
    main()
