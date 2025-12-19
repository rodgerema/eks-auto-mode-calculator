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

def calculate_ondemand_equivalent(cost_by_purchase, total_amortized):
    """
    Calcula el costo On-Demand equivalente cuando hay RIs/SPs
    Asume que RIs dan ~30% descuento y SPs ~10-20%
    """
    # Estimación conservadora de descuentos
    RI_DISCOUNT = 0.30  # 30% descuento típico
    SP_DISCOUNT = 0.15  # 15% descuento típico

    ondemand_from_ri = cost_by_purchase['reserved'] / (1 - RI_DISCOUNT) if cost_by_purchase['reserved'] > 0 else 0
    ondemand_from_sp = cost_by_purchase['savings_plans'] / (1 - SP_DISCOUNT) if cost_by_purchase['savings_plans'] > 0 else 0
    ondemand_direct = cost_by_purchase['on_demand']

    return ondemand_from_ri + ondemand_from_sp + ondemand_direct + cost_by_purchase['spot']

def calculate_fallback_cost(cluster_name, instances, region, days):
    """
    Cálculo de fallback cuando no hay tag
    Usa: nodos detectados + control plane fijo
    """
    logger.warning(f"")
    logger.warning(f"{'='*60}")
    logger.warning(f"⚠️  MODO FALLBACK - Tag 'aws:eks:cluster-name' no encontrado")
    logger.warning(f"{'='*60}")
    logger.warning(f"")

    # Control Plane fijo
    CONTROL_PLANE_MONTHLY = 0.10 * 24 * 30  # $72/mes

    logger.info(f"✅ Control Plane EKS: ${CONTROL_PLANE_MONTHLY:.2f}/mes (calculado)")
    logger.warning(f"⚠️  Data Plane: No se puede calcular sin acceso a Cost Explorer")
    logger.warning(f"⚠️  Recomendación: Verificar que las instancias tengan el tag:")
    logger.warning(f"    aws:eks:cluster-name = {cluster_name}")

    instance_types = Counter([inst['instance_type'] for inst in instances])
    logger.info(f"")
    logger.info(f"📊 Instancias detectadas:")
    for itype, count in instance_types.most_common():
        logger.info(f"   {itype}: {count} nodos")

    return {
        'monthly_cost': CONTROL_PLANE_MONTHLY,
        'monthly_ondemand': 0,
        'savings_amount': 0,
        'savings_percentage': 0,
        'ri_percentage': 0,
        'sp_percentage': 0,
        'by_service': {'Amazon Elastic Kubernetes Service': CONTROL_PLANE_MONTHLY},
        'by_purchase': {},
        'has_control_plane': True,
        'data_source': 'Fallback (solo Control Plane)',
        'warning': f'Tag aws:eks:cluster-name no encontrado. Solo se calculó Control Plane.',
        'days_analyzed': days
    }

def get_control_plane_cost(cluster_name, region, days=30):
    """
    Obtiene el costo del Control Plane de EKS de manera separada

    IMPORTANTE: El Control Plane de EKS NO tiene el tag aws:eks:cluster-name
    (ese tag solo se aplica a los nodos EC2 del Data Plane).

    Estrategia:
    - Filtra por SERVICIO: "Amazon Elastic Kubernetes Service"
    - Filtra por REGIÓN: La región del cluster

    Limitación: Si hay múltiples clusters EKS en la misma región,
    esta query sumará todos sus Control Planes. Para separar por cluster
    específico, se necesitaría un tag adicional que AWS actualmente no provee.

    Returns:
        float: Costo mensual del Control Plane, o None si no se encuentra
    """
    logger.info(f"Consultando costo de Control Plane EKS para: {cluster_name}")
    ce = boto3.client('ce', region_name='us-east-1')

    try:
        end_date = datetime.now().date() - timedelta(days=2)
        start_date = end_date - timedelta(days=days)

        # Query para EKS Control Plane
        # Estrategia: Filtrar por servicio EKS + región
        log_aws_api_call(logger, 'CostExplorer', 'get_cost_and_usage_control_plane', {
            'cluster': cluster_name,
            'service': 'Amazon Elastic Kubernetes Service',
            'region': region
        })

        response = ce.get_cost_and_usage(
            TimePeriod={
                'Start': start_date.strftime('%Y-%m-%d'),
                'End': end_date.strftime('%Y-%m-%d')
            },
            Granularity='DAILY',
            Metrics=['AmortizedCost'],
            Filter={
                'And': [
                    {
                        'Dimensions': {
                            'Key': 'SERVICE',
                            'Values': ['Amazon Elastic Kubernetes Service']
                        }
                    },
                    {
                        'Dimensions': {
                            'Key': 'REGION',
                            'Values': [region]
                        }
                    }
                ]
            }
        )

        total_cost = 0
        for result in response['ResultsByTime']:
            if 'Total' in result and 'AmortizedCost' in result['Total']:
                total_cost += float(result['Total']['AmortizedCost']['Amount'])

        actual_days = (end_date - start_date).days
        monthly_cost = (total_cost / actual_days) * 30 if actual_days > 0 else 0

        if monthly_cost > 0:
            logger.info(f"✅ Control Plane EKS encontrado: ${monthly_cost:.2f}/mes")
            log_aws_api_call(logger, 'CostExplorer', 'get_cost_and_usage_control_plane',
                           result=f"${monthly_cost:.2f}/mes")
            return monthly_cost
        else:
            logger.warning(f"⚠️  No se detectó costo de Control Plane para región {region}")
            return None

    except Exception as e:
        logger.error(f"❌ Error obteniendo costo de Control Plane: {e}")
        log_aws_api_call(logger, 'CostExplorer', 'get_cost_and_usage_control_plane', error=str(e))
        return None

def get_real_cost_from_cost_explorer(cluster_name, region, instances, days=30):
    """
    Obtiene costo real del cluster con análisis de ahorros
    - Incluye Control Plane + Data Plane
    - Calcula % ahorro por RIs y Savings Plans
    - Fallback si no encuentra tag
    """
    logger.info(f"Consultando Cost Explorer para cluster: {cluster_name} (últimos {days} días)")
    ce = boto3.client('ce', region_name='us-east-1')  # Cost Explorer siempre en us-east-1

    try:
        end_date = datetime.now().date() - timedelta(days=2)
        start_date = end_date - timedelta(days=days)

        logger.info(f"Período: {start_date} a {end_date}")

        # ============================================
        # QUERY 0: Control Plane (servicio EKS)
        # ============================================
        control_plane_cost_monthly = get_control_plane_cost(cluster_name, region, days)

        # ============================================
        # QUERY 1: Data Plane - Costo Real (con descuentos)
        # ============================================
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
            Metrics=['AmortizedCost', 'UsageQuantity'],  # ✅ Costo real con RIs/SPs
            Filter={
                'Tags': {
                    'Key': 'aws:eks:cluster-name',
                    'Values': [cluster_name]
                }
            },
            GroupBy=[
                {'Type': 'DIMENSION', 'Key': 'SERVICE'},
                {'Type': 'DIMENSION', 'Key': 'PURCHASE_TYPE'}  # ✅ Tipo de compra
            ]
        )

        # ============================================
        # PROCESAR RESULTADOS
        # ============================================
        total_amortized = 0
        cost_by_service = {}
        cost_by_purchase = {
            'on_demand': 0,
            'reserved': 0,
            'savings_plans': 0,
            'spot': 0
        }

        # Agregar Control Plane si se obtuvo
        if control_plane_cost_monthly and control_plane_cost_monthly > 0:
            # Convertir costo mensual a costo del período
            control_plane_cost_period = (control_plane_cost_monthly / 30) * days
            total_amortized += control_plane_cost_period
            cost_by_service['Amazon Elastic Kubernetes Service'] = control_plane_cost_period
            logger.info(f"Control Plane agregado: ${control_plane_cost_monthly:.2f}/mes")

        # Si no hay resultados de Data Plane pero sí Control Plane, continuar
        if not response['ResultsByTime']:
            if control_plane_cost_monthly and control_plane_cost_monthly > 0:
                logger.warning("⚠️  Tag 'aws:eks:cluster-name' no encontrado para Data Plane")
                logger.info("✅ Pero se encontró costo de Control Plane")
                # Continuar con solo Control Plane
            else:
                logger.warning("❌ No se encontraron costos ni para Control Plane ni Data Plane")
                return calculate_fallback_cost(cluster_name, instances, region, days)

        for result in response['ResultsByTime']:
            for group in result.get('Groups', []):
                service = group['Keys'][0]
                purchase_option = group['Keys'][1] if len(group['Keys']) > 1 else 'Unknown'

                cost = float(group['Metrics']['AmortizedCost']['Amount'])
                usage = float(group['Metrics']['UsageQuantity']['Amount'])

                total_amortized += cost

                # Por servicio
                cost_by_service[service] = cost_by_service.get(service, 0) + cost

                # Por tipo de compra (normalizar nombres)
                po_lower = purchase_option.lower()
                if 'on demand' in po_lower or 'ondemand' in po_lower:
                    cost_by_purchase['on_demand'] += cost
                elif 'reserved' in po_lower or 'reservation' in po_lower:
                    cost_by_purchase['reserved'] += cost
                elif 'saving' in po_lower:
                    cost_by_purchase['savings_plans'] += cost
                elif 'spot' in po_lower:
                    cost_by_purchase['spot'] += cost

        if total_amortized == 0:
            logger.warning("❌ No se encontraron costos en el período")
            return calculate_fallback_cost(cluster_name, instances, region, days)

        # ============================================
        # CALCULAR COSTO ON-DEMAND EQUIVALENTE
        # ============================================
        total_ondemand_equivalent = calculate_ondemand_equivalent(
            cost_by_purchase, total_amortized
        )

        # ============================================
        # CALCULAR AHORROS
        # ============================================
        actual_days = (end_date - start_date).days
        monthly_cost = (total_amortized / actual_days) * 30
        monthly_ondemand = (total_ondemand_equivalent / actual_days) * 30

        total_savings_amount = monthly_ondemand - monthly_cost
        savings_percentage = (total_savings_amount / monthly_ondemand * 100) if monthly_ondemand > 0 else 0

        # Desglose de ahorros
        ri_percentage = (cost_by_purchase['reserved'] / total_amortized * 100) if total_amortized > 0 else 0
        sp_percentage = (cost_by_purchase['savings_plans'] / total_amortized * 100) if total_amortized > 0 else 0

        # ============================================
        # LOGGING DETALLADO
        # ============================================
        logger.info(f"")
        logger.info(f"{'='*60}")
        logger.info(f"📊 ANÁLISIS DE COSTOS - {cluster_name}")
        logger.info(f"{'='*60}")
        logger.info(f"")
        logger.info(f"💰 COSTOS MENSUALES:")
        logger.info(f"   Costo Real:       ${monthly_cost:>10.2f}/mes")
        logger.info(f"   Costo On-Demand:  ${monthly_ondemand:>10.2f}/mes")
        logger.info(f"   Ahorro Total:     ${total_savings_amount:>10.2f}/mes ({savings_percentage:.1f}%)")
        logger.info(f"")
        logger.info(f"📋 DESGLOSE POR TIPO DE COMPRA:")
        logger.info(f"   On-Demand:        ${cost_by_purchase['on_demand']:>10.2f} ({cost_by_purchase['on_demand']/total_amortized*100:>5.1f}%)")
        logger.info(f"   Reserved Inst.:   ${cost_by_purchase['reserved']:>10.2f} ({ri_percentage:>5.1f}%)")
        logger.info(f"   Savings Plans:    ${cost_by_purchase['savings_plans']:>10.2f} ({sp_percentage:>5.1f}%)")
        if cost_by_purchase['spot'] > 0:
            logger.info(f"   Spot:             ${cost_by_purchase['spot']:>10.2f} ({cost_by_purchase['spot']/total_amortized*100:>5.1f}%)")
        logger.info(f"")
        logger.info(f"🏗️  DESGLOSE POR SERVICIO:")
        for service, cost in sorted(cost_by_service.items(), key=lambda x: x[1], reverse=True):
            service_monthly = (cost / actual_days) * 30
            service_name = service.replace('Amazon ', '').replace('Elastic ', 'E')[:30]
            logger.info(f"   {service_name:<30} ${service_monthly:>10.2f}/mes")
        logger.info(f"{'='*60}")

        # Verificar si hay control plane (ahora se busca explícitamente)
        has_control_plane = 'Amazon Elastic Kubernetes Service' in cost_by_service
        if not has_control_plane:
            logger.warning(f"⚠️  No se detectó costo de Control Plane (debería ser ~$72/mes)")
            logger.warning(f"⚠️  Verifica que el cluster esté activo en la región {region}")
        else:
            cp_cost = cost_by_service['Amazon Elastic Kubernetes Service']
            cp_monthly = (cp_cost / actual_days) * 30
            logger.info(f"✅ Control Plane detectado: ${cp_monthly:.2f}/mes")

        log_aws_api_call(logger, 'CostExplorer', 'get_cost_and_usage',
                       result=f"${monthly_cost:.2f}/mes (ahorro: {savings_percentage:.1f}%)")

        return {
            'monthly_cost': round(monthly_cost, 2),
            'monthly_ondemand': round(monthly_ondemand, 2),
            'savings_amount': round(total_savings_amount, 2),
            'savings_percentage': round(savings_percentage, 1),
            'ri_percentage': round(ri_percentage, 1),
            'sp_percentage': round(sp_percentage, 1),
            'by_service': {k: round((v/actual_days)*30, 2) for k, v in cost_by_service.items()},
            'by_purchase': cost_by_purchase,
            'has_control_plane': has_control_plane,
            'data_source': 'Cost Explorer',
            'days_analyzed': actual_days
        }

    except Exception as e:
        logger.error(f"❌ Error en Cost Explorer: {e}")
        log_aws_api_call(logger, 'CostExplorer', 'get_cost_and_usage', error=str(e))
        print(f"⚠️  Error consultando Cost Explorer: {e}", file=sys.stderr)
        return calculate_fallback_cost(cluster_name, instances, region, days)

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
    cost_data = get_real_cost_from_cost_explorer(cluster_name, region, instances)

    # Mostrar resultados al usuario
    if cost_data and cost_data.get('monthly_cost', 0) > 0:
        print(f"", file=sys.stderr)
        print(f"✅ Costo real obtenido de {cost_data['data_source']}", file=sys.stderr)
        print(f"   Costo mensual:    ${cost_data['monthly_cost']:.2f}/mes", file=sys.stderr)

        if cost_data.get('savings_percentage', 0) > 0:
            print(f"   Costo On-Demand:  ${cost_data['monthly_ondemand']:.2f}/mes", file=sys.stderr)
            print(f"   💰 Ahorro total:  ${cost_data['savings_amount']:.2f}/mes ({cost_data['savings_percentage']}%)", file=sys.stderr)
            print(f"", file=sys.stderr)
            if cost_data.get('ri_percentage', 0) > 0:
                print(f"      - Reserved Instances: {cost_data['ri_percentage']}%", file=sys.stderr)
            if cost_data.get('sp_percentage', 0) > 0:
                print(f"      - Savings Plans:      {cost_data['sp_percentage']}%", file=sys.stderr)

        if not cost_data.get('has_control_plane', True):
            print(f"   ⚠️  Control Plane no detectado en costos", file=sys.stderr)

        if cost_data.get('warning'):
            print(f"", file=sys.stderr)
            print(f"   ⚠️  {cost_data['warning']}", file=sys.stderr)
    else:
        logger.warning("No se pudo obtener costo real")
        print(f"⚠️  No se pudo obtener costo real", file=sys.stderr)
        cost_data = {
            'monthly_cost': 0,
            'savings_percentage': 0,
            'data_source': 'No disponible'
        }

    # Generar variables de entorno (a stdout)
    env_vars = {
        'EKS_PRIMARY_INSTANCE': primary_instance,
        'EKS_NODE_COUNT': str(node_count),
        'EKS_UTIL_CPU': str(cpu_util),
        'EKS_UTIL_MEM': str(mem_util),
        'AWS_REGION': region,
        'EKS_MONTHLY_COST': str(cost_data.get('monthly_cost', 0)),
        'EKS_MONTHLY_COST_ONDEMAND': str(cost_data.get('monthly_ondemand', 0)),
        'EKS_SAVINGS_PERCENTAGE': str(cost_data.get('savings_percentage', 0)),
        'EKS_METRIC_SOURCE': metric_source,
        'EKS_COST_SOURCE': cost_data.get('data_source', 'Unknown')
    }

    logger.info(f"Variables generadas: {env_vars}")
    
    for key, value in env_vars.items():
        print(f"export {key}='{value}'")
    
    logger.info("=== RECOLECTOR AWS COMPLETADO ===")

if __name__ == "__main__":
    main()
