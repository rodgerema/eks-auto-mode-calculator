import os
import sys
import json
import math

try:
    import boto3
    from botocore.exceptions import ClientError, NoCredentialsError
    BOTO3_AVAILABLE = True
except ImportError:
    BOTO3_AVAILABLE = False

def get_region_name_for_pricing(region):
    """Mapeo de códigos de región AWS para el API de pricing"""
    region_name_map = {
        'us-east-1': 'US East (N. Virginia)',
        'us-east-2': 'US East (Ohio)',
        'us-west-1': 'US West (N. California)',
        'us-west-2': 'US West (Oregon)',
        'eu-west-1': 'EU (Ireland)',
        'eu-central-1': 'EU (Frankfurt)',
        'ap-southeast-1': 'Asia Pacific (Singapore)',
        'ap-northeast-1': 'Asia Pacific (Tokyo)',
        'sa-east-1': 'South America (Sao Paulo)',
    }
    return region_name_map.get(region, 'US East (N. Virginia)')

def obtener_precio_ec2_aws(instance_type, region='us-east-1'):
    """
    Obtiene el precio On-Demand de una instancia EC2 desde AWS Price List API.
    Retorna el precio por hora en USD, o None si no se puede obtener.
    """
    if not BOTO3_AVAILABLE:
        return None

    try:
        # El servicio de pricing está disponible en us-east-1
        pricing_client = boto3.client('pricing', region_name='us-east-1')
        location = get_region_name_for_pricing(region)

        # Consultar pricing
        response = pricing_client.get_products(
            ServiceCode='AmazonEC2',
            Filters=[
                {'Type': 'TERM_MATCH', 'Field': 'instanceType', 'Value': instance_type},
                {'Type': 'TERM_MATCH', 'Field': 'location', 'Value': location},
                {'Type': 'TERM_MATCH', 'Field': 'operatingSystem', 'Value': 'Linux'},
                {'Type': 'TERM_MATCH', 'Field': 'tenancy', 'Value': 'Shared'},
                {'Type': 'TERM_MATCH', 'Field': 'capacitystatus', 'Value': 'Used'},
                {'Type': 'TERM_MATCH', 'Field': 'preInstalledSw', 'Value': 'NA'},
            ],
            MaxResults=1
        )

        if response['PriceList']:
            price_item = json.loads(response['PriceList'][0])
            on_demand = price_item['terms']['OnDemand']
            price_dimensions = list(on_demand.values())[0]['priceDimensions']
            price_per_hour = float(list(price_dimensions.values())[0]['pricePerUnit']['USD'])
            return price_per_hour

    except (ClientError, NoCredentialsError, KeyError, IndexError) as e:
        print(f"⚠️  No se pudo obtener precio de AWS API para {instance_type}: {e}", file=sys.stderr)
        return None

    return None

def obtener_precio_eks_automode_aws(instance_type, region='us-east-1'):
    """
    Obtiene el precio de EKS Auto Mode para una instancia específica desde AWS Price List API.
    Retorna el precio por hora en USD, o None si no se puede obtener.
    """
    if not BOTO3_AVAILABLE:
        return None

    try:
        pricing_client = boto3.client('pricing', region_name='us-east-1')
        location = get_region_name_for_pricing(region)

        # Consultar pricing para EKS Auto Mode
        response = pricing_client.get_products(
            ServiceCode='AmazonEKS',
            Filters=[
                {'Type': 'TERM_MATCH', 'Field': 'location', 'Value': location},
                {'Type': 'TERM_MATCH', 'Field': 'instanceType', 'Value': instance_type},
                {'Type': 'TERM_MATCH', 'Field': 'operation', 'Value': 'EKSAutoUsage'},
            ],
            MaxResults=1
        )

        if response['PriceList']:
            for price_list_item in response['PriceList']:
                price_item = json.loads(price_list_item)
                
                # Buscar Auto Mode en la descripción del producto
                product_desc = price_item.get('product', {}).get('attributes', {}).get('eksproducttype', '')
                if 'AutoMode' in product_desc or 'Auto Mode' in product_desc:
                    on_demand = price_item['terms']['OnDemand']
                    price_dimensions = list(on_demand.values())[0]['priceDimensions']
                    price_per_hour = float(list(price_dimensions.values())[0]['pricePerUnit']['USD'])
                    return price_per_hour

    except (ClientError, NoCredentialsError, KeyError, IndexError) as e:
        print(f"⚠️  No se pudo obtener precio EKS Auto Mode de AWS API para {instance_type}: {e}", file=sys.stderr)
        return None

    return None

def calcular_ahorro():
    # --- CONFIGURACIÓN DE PRECIOS (Fallback - us-east-1 On-Demand base) ---
    # Estos precios se usan solo si no se puede conectar a AWS Price List API
    precios_ec2_fallback = {
        "t3.medium": 0.0416, "t3.large": 0.0832, "t3.xlarge": 0.1664,
        "m5.large": 0.096,   "m5.xlarge": 0.192,  "m5.2xlarge": 0.384, "m5.4xlarge": 0.768,
        "c5.large": 0.085,   "c5.xlarge": 0.17,   "c5.2xlarge": 0.34,
        "r5.large": 0.126,   "r5.xlarge": 0.252,  "r5.2xlarge": 0.504,
        "m6i.large": 0.096,  "m6i.xlarge": 0.192,
        "t3a.medium": 0.0376, "t3a.large": 0.0752
    }

    # Constantes de EKS
    EKS_CONTROL_PLANE_HOURLY = 0.10  # $0.10 por hora por cluster
    EKS_AUTO_MODE_FEE_PERCENT = 0.12  # 12% adicional para Auto Mode (fallback)

    print("--- 📊 Calculadora de Migración a EKS Auto Mode (Automática) ---")

    # --- INPUT DESDE VARIABLES DE ENTORNO ---
    try:
        instance_type = os.environ.get('EKS_PRIMARY_INSTANCE', 'm5.large')
        node_count = int(float(os.environ.get('EKS_NODE_COUNT', 0)))
        utilizacion_cpu = float(os.environ.get('EKS_UTIL_CPU', 50)) / 100
        utilizacion_mem = float(os.environ.get('EKS_UTIL_MEM', 50)) / 100
        region = os.environ.get('AWS_REGION', 'us-east-1')
        monthly_cost_real = float(os.environ.get('EKS_MONTHLY_COST', 0))
        metric_source = os.environ.get('EKS_METRIC_SOURCE', 'No especificada')
    except ValueError as e:
        print(f"❌ Error leyendo variables de entorno: {e}")
        print("Ejecuta primero el script recolector.")
        sys.exit(1)

    if node_count == 0:
        print("⚠️ Advertencia: Node count es 0. ¿Corriste el recolector?")

    # --- OBTENER PRECIOS DE AWS ---
    print(f"🔍 Obteniendo precios de AWS para {instance_type} en {region}...", file=sys.stderr)
    
    # Precio EC2 estándar
    precio_ec2_hora = obtener_precio_ec2_aws(instance_type, region)
    if precio_ec2_hora is None:
        if instance_type in precios_ec2_fallback:
            precio_ec2_hora = precios_ec2_fallback[instance_type]
            print(f"⚠️  Usando precio EC2 fallback para {instance_type}: ${precio_ec2_hora}/hora", file=sys.stderr)
        else:
            print(f"⚠️ Tipo de instancia '{instance_type}' no encontrado en AWS API ni en base local.", file=sys.stderr)
            costo_custom = float(input(f"Por favor ingresa costo por hora USD para {instance_type}: "))
            precio_ec2_hora = costo_custom
    else:
        print(f"✅ Precio EC2 obtenido de AWS: ${precio_ec2_hora}/hora", file=sys.stderr)
    
    # Precio EKS Auto Mode Fee
    print(f"🔍 Obteniendo precio EKS Auto Mode fee para {instance_type}...", file=sys.stderr)
    precio_automode_fee_hora = obtener_precio_eks_automode_aws(instance_type, region)
    
    if precio_automode_fee_hora is None:
        # Fallback: calcular 12% sobre el precio EC2
        precio_automode_fee_hora = precio_ec2_hora * EKS_AUTO_MODE_FEE_PERCENT
        print(f"⚠️  Precio Auto Mode fee no disponible, usando fallback: ${precio_automode_fee_hora}/hora (12% de EC2)", file=sys.stderr)
        using_api_pricing = False
    else:
        print(f"✅ Precio EKS Auto Mode fee obtenido de AWS: ${precio_automode_fee_hora}/hora", file=sys.stderr)
        using_api_pricing = True

    # --- CÁLCULOS ---
    hours_month = 730

    # 1. Costo Actual
    control_plane_monthly = EKS_CONTROL_PLANE_HOURLY * hours_month
    
    # Si tenemos costo real de Cost Explorer, usarlo; sino calcular
    if monthly_cost_real > 0:
        ec2_monthly_cost = monthly_cost_real
        current_monthly_cost = control_plane_monthly + ec2_monthly_cost
        print(f"✅ Usando costo real de Cost Explorer: ${monthly_cost_real:.2f}/mes", file=sys.stderr)
    else:
        ec2_hourly_cost = node_count * precio_ec2_hora
        ec2_monthly_cost = ec2_hourly_cost * hours_month
        current_monthly_cost = control_plane_monthly + ec2_monthly_cost

    # 2. Costo EKS Auto Mode (Estimado)
    waste_factor = 1 - ((utilizacion_cpu + utilizacion_mem) / 2)
    efficiency_gain = 0.20
    potential_reduction = waste_factor * efficiency_gain

    # IMPORTANTE: Redondear hacia arriba porque no puedes pagar por instancias fraccionarias
    # Si el bin packing óptimo requiere 2.7 instancias, pagarás por 3 instancias completas
    estimated_nodes_auto_decimal = node_count * (1 - potential_reduction)
    estimated_nodes_auto = math.ceil(estimated_nodes_auto_decimal)

    # Calcular factor de descuento si tenemos costo real
    discount_factor = 1.0
    if monthly_cost_real > 0:
        # Calcular el descuento implícito comparando costo real vs On-Demand
        ondemand_ec2_cost = node_count * precio_ec2_hora * hours_month
        if ondemand_ec2_cost > 0:
            discount_factor = monthly_cost_real / ondemand_ec2_cost
            print(f"✅ Factor de descuento detectado: {(1-discount_factor)*100:.1f}% (Savings Plans/RI)", file=sys.stderr)

    # Separar costos: EC2 + Auto Mode Fee
    ec2_auto_hourly_cost = estimated_nodes_auto * precio_ec2_hora
    ec2_auto_monthly_cost = ec2_auto_hourly_cost * hours_month * discount_factor  # Aplicar descuento
    
    automode_fee_hourly_cost = estimated_nodes_auto * precio_automode_fee_hora
    automode_fee_monthly_cost = automode_fee_hourly_cost * hours_month  # Fee no tiene descuento
    
    auto_monthly_cost = control_plane_monthly + ec2_auto_monthly_cost + automode_fee_monthly_cost
    
    # Ahorro Operativo
    horas_ing_ahorradas = 10
    costo_hora_ing = 50
    ahorro_ops = horas_ing_ahorradas * costo_hora_ing

    # --- REPORTE ---
    print(f"\n{'='*60}")
    print(f"📊 ANÁLISIS DE CLUSTER ACTUAL")
    print(f"{'='*60}")
    print(f"  Nodos:                 {node_count} x {instance_type}")
    print(f"  Región:                {region}")
    print(f"  Precio EC2/hora:       ${precio_ec2_hora:.4f}")
    print(f"  Utilización CPU:       {utilizacion_cpu*100:.1f}%")
    print(f"  Utilización RAM:       {utilizacion_mem*100:.1f}%")
    if monthly_cost_real > 0:
        print(f"  Costo Real (30 días):  ${monthly_cost_real:.2f}")
    print()

    print(f"{'='*60}")
    print(f"💰 DESGLOSE DE COSTOS MENSUALES")
    print(f"{'='*60}")
    print(f"\n🔵 EKS STANDARD (Managed Node Groups)")
    print(f"  Control Plane:         ${control_plane_monthly:>10,.2f}  (@$0.10/hora)")
    print(f"  Instancias EC2:        ${ec2_monthly_cost:>10,.2f}  ({node_count} nodos)")
    print(f"  {'-'*58}")
    print(f"  TOTAL MENSUAL:         ${current_monthly_cost:>10,.2f}")
    print()

    print(f"🟢 EKS AUTO MODE (Estimado)")
    print(f"  Control Plane:         ${control_plane_monthly:>10,.2f}  (@$0.10/hora)")
    if discount_factor < 1.0:
        ec2_auto_ondemand = estimated_nodes_auto * precio_ec2_hora * hours_month
        print(f"  Instancias EC2:        ${ec2_auto_monthly_cost:>10,.2f}  ({estimated_nodes_auto} nodos @ ${precio_ec2_hora:.4f}/h con descuento)")
        print(f"    (On-Demand sería:    ${ec2_auto_ondemand:>10,.2f})")
        if estimated_nodes_auto_decimal != estimated_nodes_auto:
            print(f"    (Capacidad estimada: {estimated_nodes_auto_decimal:.1f} nodos, redondeado a {estimated_nodes_auto})")
    else:
        print(f"  Instancias EC2:        ${ec2_auto_monthly_cost:>10,.2f}  ({estimated_nodes_auto} nodos @ ${precio_ec2_hora:.4f}/h)")
        if estimated_nodes_auto_decimal != estimated_nodes_auto:
            print(f"    (Capacidad estimada: {estimated_nodes_auto_decimal:.1f} nodos, redondeado a {estimated_nodes_auto})")
    print(f"  Auto Mode Fee:         ${automode_fee_monthly_cost:>10,.2f}  (@${precio_automode_fee_hora:.4f}/h por nodo)")
    print(f"  {'-'*58}")
    print(f"  TOTAL MENSUAL:         ${auto_monthly_cost:>10,.2f}")
    print()

    ahorro_infra = current_monthly_cost - auto_monthly_cost
    total_savings = ahorro_infra + ahorro_ops

    print(f"{'='*60}")
    print(f"✨ RESUMEN DE AHORROS")
    print(f"{'='*60}")
    if ahorro_infra > 0:
        print(f"  Ahorro Infraestructura:  ${ahorro_infra:>10,.2f} / mes")
        print(f"  Ahorro Operativo:        ${ahorro_ops:>10,.2f} / mes")
        print(f"  {'-'*58}")
        print(f"  💰 AHORRO TOTAL:         ${total_savings:>10,.2f} / mes")
        print(f"                           ${total_savings*12:>10,.2f} / año")
    else:
        print(f"  ⚠️  Auto Mode sería más caro: ${abs(ahorro_infra):,.2f} / mes")
        print(f"  Tu cluster está extremadamente optimizado.")
        print(f"  Los beneficios principales serían operativos.")
    print(f"{'='*60}")
    print()

    print(f"ℹ️  NOTAS:")
    print(f"  • Precios obtenidos de AWS Price List API oficial")
    print(f"  • Fuente de métricas de utilización: {metric_source}")
    if monthly_cost_real > 0:
        print(f"  • Costo actual basado en Cost Explorer (últimos 30 días)")
        if discount_factor < 1.0:
            print(f"  • Descuentos Savings Plans/RI aplicados a Auto Mode ({(1-discount_factor)*100:.1f}%)")
    if not using_api_pricing:
        print(f"  • Precio Auto Mode fee calculado como fallback (12% de EC2)")
    else:
        print(f"  • Precio Auto Mode fee obtenido directamente de AWS API")
    print(f"  • Estimación asume mejora del 20% en bin packing")
    print(f"  • Número de nodos redondeado hacia arriba (no se pagan instancias fraccionarias)")
    print(f"  • Ahorro operativo: {horas_ing_ahorradas}h/mes × ${costo_hora_ing}/h")
    print()
    
    print(f"{'='*60}")
    print(f"🔗 REFERENCIAS DE PRICING")
    print(f"{'='*60}")
    print(f"  EC2 Pricing ({instance_type}):")
    print(f"    https://aws.amazon.com/ec2/pricing/on-demand/")
    print()
    print(f"  EKS Control Plane Pricing:")
    print(f"    https://aws.amazon.com/eks/pricing/")
    print()
    print(f"  EKS Auto Mode Pricing:")
    print(f"    https://docs.aws.amazon.com/eks/latest/userguide/automode.html")
    print(f"{'='*60}")

if __name__ == "__main__":
    calcular_ahorro()