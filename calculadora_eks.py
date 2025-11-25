import os
import sys

def calcular_ahorro():
    # --- CONFIGURACIÓN DE PRECIOS (us-east-1 On-Demand base) ---
    precios_ec2 = {
        "t3.medium": 0.0416, "t3.large": 0.0832, "t3.xlarge": 0.1664,
        "m5.large": 0.096,   "m5.xlarge": 0.192,  "m5.2xlarge": 0.384, "m5.4xlarge": 0.768,
        "c5.large": 0.085,   "c5.xlarge": 0.17,   "c5.2xlarge": 0.34,
        "r5.large": 0.126,   "r5.xlarge": 0.252,  "r5.2xlarge": 0.504,
        "m6i.large": 0.096,  "m6i.xlarge": 0.192,
        "t3a.medium": 0.0376, "t3a.large": 0.0752
    }

    print("--- 📊 Calculadora de Migración a EKS Auto Mode (Automática) ---")

    # --- INPUT DESDE VARIABLES DE ENTORNO ---
    try:
        instance_type = os.environ.get('EKS_PRIMARY_INSTANCE', 'm5.large')
        node_count = int(float(os.environ.get('EKS_NODE_COUNT', 0))) # float primero por seguridad
        utilizacion_cpu = float(os.environ.get('EKS_UTIL_CPU', 50)) / 100
        utilizacion_mem = float(os.environ.get('EKS_UTIL_MEM', 50)) / 100
    except ValueError as e:
        print(f"❌ Error leyendo variables de entorno: {e}")
        print("Ejecuta primero el script recolector.")
        sys.exit(1)

    if node_count == 0:
        print("⚠️ Advertencia: Node count es 0. ¿Corriste el recolector?")
        # Fallback a manual si se desea, o salir
        
    # Precio dinámico si no está en la lista
    if instance_type not in precios_ec2:
        print(f"⚠️ Tipo de instancia detectado '{instance_type}' no está en mi DB local.")
        costo_custom = float(input(f"Por favor ingresa costo por hora USD para {instance_type}: "))
        precios_ec2[instance_type] = costo_custom

    # --- CÁLCULOS ---
    hours_month = 730
    
    # 1. Costo Actual (ASG / Managed Node Groups)
    current_hourly_cost = node_count * precios_ec2[instance_type]
    current_monthly_cost = current_hourly_cost * hours_month
    
    # 2. Costo EKS Auto Mode (Estimado)
    # EKS Auto Mode cobra por los recursos de EC2 subyacentes que orquesta.
    # La ventaja es el "Bin Packing" automático.
    
    # Calculamos el desperdicio promedio actual basado en los requests vs capacidad total
    waste_factor = 1 - ((utilizacion_cpu + utilizacion_mem) / 2)
    
    # Hipótesis: Auto Mode mejorará el empaquetado un 20% respecto a un ASG estático
    efficiency_gain = 0.20
    
    # Si el desperdicio actual es bajo (<15%), Auto Mode no puede hacer magia con el cómputo,
    # pero si el desperdicio es alto (muy común), el ahorro es masivo.
    potential_reduction = waste_factor * efficiency_gain
    
    # Nodos equivalentes en Auto Mode
    estimated_nodes_auto = node_count * (1 - potential_reduction)
    
    auto_hourly_cost = estimated_nodes_auto * precios_ec2[instance_type]
    auto_monthly_cost = auto_hourly_cost * hours_month
    
    # Ahorro Operativo (Ops)
    horas_ing_ahorradas = 10 
    costo_hora_ing = 50 
    ahorro_ops = horas_ing_ahorradas * costo_hora_ing

    # --- REPORTE ---
    print(f"\nCluster Actual Detectado:")
    print(f"  - Nodos: {node_count} x {instance_type}")
    print(f"  - Utilización (Requests/Capacity): CPU {utilizacion_cpu*100:.1f}% | RAM {utilizacion_mem*100:.1f}%")
    print("-" * 40)
    
    print(f"💰 ANÁLISIS DE COSTOS")
    print(f"Costo Mensual ACTUAL:              ${current_monthly_cost:,.2f}")
    print(f"Costo Mensual AUTO MODE (Est.):    ${auto_monthly_cost:,.2f}")
    print(f"----------------------------------------")
    
    ahorro_infra = current_monthly_cost - auto_monthly_cost
    total_savings = ahorro_infra + ahorro_ops
    
    if total_savings > 0:
        print(f"✅ AHORRO TOTAL ESTIMADO:          ${total_savings:,.2f} / mes")
        print(f"   (Infra: ${ahorro_infra:.2f} + Ops: ${ahorro_ops:.2f})")
    else:
        print(f"⚠️ DIFERENCIA ESTIMADA:            ${total_savings:,.2f} / mes")
        print("   Tu cluster actual está extremadamente optimizado.")

if __name__ == "__main__":
    calcular_ahorro()