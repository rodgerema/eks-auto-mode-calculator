# Calculadora de Migración a EKS Auto Mode

Herramienta para analizar los costos de tu cluster EKS actual y estimar el ahorro potencial al migrar a **EKS Auto Mode**.

## Descripción

Este proyecto consta de tres scripts de Python:

1. **analizar_eks.py**: Script principal que orquesta todo el flujo (recomendado)
2. **recolector_eks.py**: Recolecta métricas usando kubectl (requiere acceso al cluster)
3. **recolector_eks_aws.py**: Recolecta métricas usando AWS APIs (sin kubectl)
4. **calculadora_eks.py**: Calcula costos y estima ahorros con EKS Auto Mode

## Diagrama de Flujo de Recolección de Datos

```
┌─────────────────────────────────────────────────────────────────┐
│                    RECOLECTOR (recolector_eks_aws.py)           │
└─────────────────────────────────────────────────────────────────┘
                                 │
                                 ▼
        ┌────────────────────────────────────────────┐
        │  1️⃣  AWS EKS API - DescribeCluster         │
        │     • Nombre del cluster                   │
        │     • Versión de Kubernetes                │
        │     • Estado del cluster                   │
        └────────────────────────────────────────────┘
                                 │
                                 ▼
        ┌────────────────────────────────────────────┐
        │  2️⃣  AWS EC2 API - DescribeInstances       │
        │     Filtros:                               │
        │     • tag:eks:cluster-name = <nombre>      │
        │     • instance-state-name = running        │
        │                                            │
        │     Obtiene:                               │
        │     • Cantidad de nodos (11)               │
        │     • Tipo de instancia (c5.4xlarge)       │
        │     • Instance IDs                         │
        └────────────────────────────────────────────┘
                                 │
                                 ▼
        ┌────────────────────────────────────────────┐
        │  3️⃣  AWS CloudWatch - GetMetricStatistics  │
        │     Namespace: ContainerInsights           │
        │     Métricas:                              │
        │     • node_cpu_utilization                 │
        │     • node_memory_utilization              │
        │     Período: últimos 7 días                │
        │                                            │
        │     ⚠️  Requiere Container Insights        │
        │     habilitado en el cluster               │
        └────────────────────────────────────────────┘
                                 │
                                 ▼
        ┌────────────────────────────────────────────┐
        │  📤 OUTPUT: Variables de Entorno           │
        │     export EKS_PRIMARY_INSTANCE='...'      │
        │     export EKS_NODE_COUNT='...'            │
        │     export EKS_UTIL_CPU='...'              │
        │     export EKS_UTIL_MEM='...'              │
        │     export AWS_REGION='...'                │
        └────────────────────────────────────────────┘
                                 │
                                 ▼
┌─────────────────────────────────────────────────────────────────┐
│                   CALCULADORA (calculadora_eks.py)              │
└─────────────────────────────────────────────────────────────────┘
                                 │
                                 ▼
        ┌────────────────────────────────────────────┐
        │  4️⃣  AWS Pricing API - GetProducts         │
        │     Service: AmazonEC2                     │
        │     Filtros:                               │
        │     • instanceType = <tipo detectado>      │
        │     • location = <región>                  │
        │     • operatingSystem = Linux              │
        │     • tenancy = Shared                     │
        │                                            │
        │     Obtiene:                               │
        │     • Precio On-Demand por hora ($0.68)    │
        └────────────────────────────────────────────┘
                                 │
                                 ▼
        ┌────────────────────────────────────────────┐
        │  💰 CÁLCULOS DE COSTOS                     │
        │                                            │
        │  EKS Standard:                             │
        │  • Control Plane: $0.10/h × 730h           │
        │  • EC2: nodos × precio × 730h              │
        │                                            │
        │  EKS Auto Mode:                            │
        │  • Control Plane: $0.10/h × 730h           │
        │  • EC2: nodos_optimizados × precio × 730h  │
        │  • Auto Mode Fee: EC2 × 12%                │
        └────────────────────────────────────────────┘
                                 │
                                 ▼
        ┌────────────────────────────────────────────┐
        │  📊 REPORTE FINAL                          │
        │  • Análisis de cluster actual              │
        │  • Desglose de costos                      │
        │  • Estimación de ahorros                   │
        │  • Referencias de pricing                  │
        └────────────────────────────────────────────┘
```

### APIs Utilizadas

| API | Servicio | Propósito | Permisos Requeridos |
|-----|----------|-----------|---------------------|
| **EKS** | `DescribeCluster` | Información del cluster | `eks:DescribeCluster` |
| **EC2** | `DescribeInstances` | Nodos y tipos de instancia | `ec2:DescribeInstances` |
| **CloudWatch** | `GetMetricStatistics` | Métricas de utilización | `cloudwatch:GetMetricStatistics` |
| **Pricing** | `GetProducts` | Precios On-Demand EC2 | `pricing:GetProducts` |

**Nota**: El Pricing API siempre se consulta en `us-east-1` independientemente de la región del cluster.

## Cómo se Calculan los Costos

### Obtención de Precios en Tiempo Real

El script obtiene automáticamente los precios actuales desde la **AWS Price List API oficial**:
- Precios On-Demand para instancias EC2
- Actualizados en tiempo real desde AWS
- Soporta múltiples regiones (us-east-1, us-west-2, eu-west-1, etc.)
- Fallback a precios locales si no hay conectividad

### Costo Actual (EKS Standard con Managed Node Groups)

```
Costo Mensual = Control Plane + Instancias EC2

Control Plane = $0.10/hora × 730 horas = $73/mes
Instancias EC2 = Número de Nodos × Precio por Hora × 730 horas/mes
```

### Costo Estimado con EKS Auto Mode

EKS Auto Mode mejora la eficiencia mediante **Bin Packing automático** y cobra un **fee del 12%** sobre las instancias EC2.

#### Metodología de Cálculo:

1. **Factor de Desperdicio Actual**:
   ```
   Desperdicio = 1 - ((Utilización CPU + Utilización RAM) / 2)
   ```
   La utilización se calcula como: `Requests de Pods / Capacidad Allocatable del Cluster`

2. **Ganancia de Eficiencia**:
   El script asume una mejora del **20% en el empaquetado** respecto a un ASG estático.

3. **Reducción Potencial**:
   ```
   Reducción = Factor de Desperdicio × 20%
   ```

4. **Nodos Estimados en Auto Mode**:
   ```
   Nodos Equivalentes = Nodos Actuales × (1 - Reducción Potencial)
   ```

5. **Costo Mensual Auto Mode**:
   ```
   Control Plane = $0.10/hora × 730 horas = $73/mes
   Instancias EC2 = Nodos Equivalentes × Precio por Hora × 730 horas/mes
   Auto Mode Fee = Costo EC2 × 12%

   Total = Control Plane + Instancias EC2 + Auto Mode Fee
   ```

**Nota importante**: El fee del 12% de EKS Auto Mode se aplica sobre el costo de las instancias EC2, no sobre el control plane.

### Ahorros Operativos

Además del ahorro en infraestructura, el script calcula ahorros operativos:

```
Ahorro Operativo = 10 horas/mes × $50/hora = $500/mes
```

Esto representa el tiempo de ingeniería ahorrado en:
- Gestión manual de escalado
- Optimización de node groups
- Troubleshooting de scheduling
- Mantenimiento de ASGs

### Ahorro Total

```
Ahorro Total = (Costo Actual - Costo Auto Mode) + Ahorro Operativo
```

## Prerrequisitos

### 1. Python 3.x

Verifica tu versión de Python:
```bash
python3 --version
```

### 2. Dependencias de Python

El script necesita las siguientes librerías:
- `kubernetes`: Cliente de Kubernetes para Python (solo si usas kubectl)
- `boto3`: AWS SDK para obtener precios y métricas

```bash
pip install -r requirements.txt
```

O si usas un entorno virtual (recomendado):
```bash
python3 -m venv venv
source venv/bin/activate  # En Linux/Mac
# o en Windows: venv\Scripts\activate
pip install -r requirements.txt
```

### 3. Credenciales AWS Configuradas

El script usa boto3 para obtener información del cluster y precios. Configura tus credenciales AWS:

```bash
aws configure
```

O asegúrate de tener variables de entorno configuradas:
```bash
export AWS_ACCESS_KEY_ID="tu-access-key"
export AWS_SECRET_ACCESS_KEY="tu-secret-key"
export AWS_REGION="us-east-1"  # Opcional, por defecto usa us-east-1
```

### 4. kubectl Configurado (Opcional)

Si eliges el método con kubectl (más preciso), asegúrate de tener acceso a tu cluster EKS:

```bash
# Configurar kubeconfig
aws eks update-kubeconfig --region <tu-region> --name <nombre-cluster>

# Verificar acceso
kubectl get nodes
```

### 5. Permisos AWS Requeridos

Tu usuario/rol de AWS necesita permisos para:
- `eks:DescribeCluster` (obtener información del cluster)
- `ec2:DescribeInstances` (listar nodos EC2)
- `cloudwatch:GetMetricStatistics` (métricas de utilización - opcional)
- `pricing:GetProducts` (para obtener precios de EC2 en tiempo real)

**Con kubectl** también necesitas permisos de lectura en Kubernetes:
- `nodes` (list)
- `pods` (list en todos los namespaces)

**Nota**: Si no tienes acceso a CloudWatch Container Insights, el script usará valores por defecto de utilización.

## Instalación

```bash
# Clonar o descargar los scripts
cd eks-auto-mode-calculator

# Crear entorno virtual (recomendado)
python3 -m venv venv
source venv/bin/activate

# Instalar dependencias
pip install -r requirements.txt

# Configurar credenciales AWS (si aún no lo hiciste)
aws configure
```

## Uso

### Opción 1: Script Unificado (Recomendado)

El script `analizar_eks.py` ejecuta todo el flujo automáticamente:

```bash
python3 analizar_eks.py
```

El script te preguntará:
1. Nombre del cluster EKS
2. Región AWS (default: us-east-1)
3. Si tienes acceso con kubectl o solo AWS APIs

**Ejemplo de ejecución:**
```
📊 CALCULADORA DE MIGRACIÓN A EKS AUTO MODE

Nombre del cluster EKS: mi-cluster-prod
Región AWS (default: us-east-1): us-east-1

¿Tienes acceso directo al cluster con kubectl?
  1) Sí - Usar kubectl (más preciso)
  2) No - Usar AWS APIs solamente

Selecciona opción [1/2]: 2

⏳ Recolectando datos con AWS APIs...
✅ Cluster encontrado: mi-cluster-prod (versión 1.28)
✅ Nodos encontrados: 11 (c5.4xlarge)
✅ Utilización CPU: 42.5%, Memoria: 58.3%

💰 CALCULANDO COSTOS
...
```

### Opción 2: Ejecución Manual (Paso a Paso)

#### Con kubectl (más preciso)

```bash
# Paso 1: Recolectar datos
eval $(python3 recolector_eks.py)

# Paso 2: Calcular costos
python3 calculadora_eks.py
```

#### Sin kubectl (solo AWS APIs)

```bash
# Paso 1: Recolectar datos
eval $(python3 recolector_eks_aws.py)

# Paso 2: Calcular costos
python3 calculadora_eks.py
```

#### Verificar variables recolectadas

```bash
# Ver las variables generadas
python3 recolector_eks_aws.py > eks_vars.sh
cat eks_vars.sh

# Salida esperada:
# export EKS_PRIMARY_INSTANCE='c5.4xlarge'
# export EKS_NODE_COUNT='11'
# export EKS_UTIL_CPU='42.50'
# export EKS_UTIL_MEM='58.30'
# export AWS_REGION='us-east-1'
```

## Ejemplo de Salida

```
============================================================
📊 CALCULADORA DE MIGRACIÓN A EKS AUTO MODE
============================================================

Nombre del cluster EKS: mi-cluster-prod
Región AWS (default: us-east-1): us-east-1

¿Tienes acceso directo al cluster con kubectl?
  1) Sí - Usar kubectl (más preciso)
  2) No - Usar AWS APIs solamente

Selecciona opción [1/2]: 2

⏳ Recolectando datos con AWS APIs...
✅ Cluster encontrado: mi-cluster-prod (versión 1.28)
✅ Nodos encontrados: 8 (m5.xlarge)
✅ Utilización CPU: 42.5%, Memoria: 58.3%

============================================================
💰 CALCULANDO COSTOS
============================================================

🔍 Obteniendo precio real de AWS para m5.xlarge en us-east-1...
✅ Precio obtenido de AWS: $0.1920/hora

============================================================
📊 ANÁLISIS DE CLUSTER ACTUAL
============================================================
  Nodos:                 8 x m5.xlarge
  Región:                us-east-1
  Precio EC2/hora:       $0.1920
  Utilización CPU:       42.5%
  Utilización RAM:       58.3%

============================================================
💰 DESGLOSE DE COSTOS MENSUALES
============================================================

🔵 EKS STANDARD (Managed Node Groups)
  Control Plane:         $     73.00  (@$0.10/hora)
  Instancias EC2:        $  1,121.28  (8 nodos)
  ----------------------------------------------------------
  TOTAL MENSUAL:         $  1,194.28

🟢 EKS AUTO MODE (Estimado)
  Control Plane:         $     73.00  (@$0.10/hora)
  Instancias EC2:        $    952.09  (6.8 nodos)
  Auto Mode Fee (12%):   $    114.25  (sobre EC2)
  ----------------------------------------------------------
  TOTAL MENSUAL:         $  1,139.34

============================================================
✨ RESUMEN DE AHORROS
============================================================
  Ahorro Infraestructura:  $      54.94 / mes
  Ahorro Operativo:        $     500.00 / mes
  ----------------------------------------------------------
  💰 AHORRO TOTAL:         $     554.94 / mes
                           $   6,659.28 / año
============================================================

ℹ️  NOTAS:
  • Precios obtenidos de AWS Price List API oficial
  • EKS Auto Mode incluye fee del 12% sobre costos de EC2
  • Estimación asume mejora del 20% en bin packing
  • Ahorro operativo: 10h/mes × $50/h
```

## Variables de Entorno

El recolector genera las siguientes variables:

| Variable | Descripción | Ejemplo |
|----------|-------------|---------|
| `EKS_PRIMARY_INSTANCE` | Tipo de instancia más común | `m5.xlarge` |
| `EKS_NODE_COUNT` | Número total de nodos | `8` |
| `EKS_UTIL_CPU` | % Utilización CPU (requests/capacity) | `45.30` |
| `EKS_UTIL_MEM` | % Utilización RAM (requests/capacity) | `62.15` |

## Notas Importantes

### Sobre los Precios

- **Precios en Tiempo Real**: El script obtiene automáticamente los precios actuales desde la AWS Price List API
- **Multi-Región**: Soporta múltiples regiones de AWS (usa la variable `AWS_REGION`)
- **Precios On-Demand**: Se consultan precios On-Demand de instancias Linux
- **Reserved Instances**: Si usas Reserved Instances o Savings Plans, los ahorros reales serán diferentes
- **Fallback**: Si no hay conectividad con AWS, usa precios predefinidos de us-east-1
- **EKS Auto Mode Fee**: Se aplica un 12% adicional sobre las instancias EC2 (no sobre control plane)

### Sobre las Estimaciones

- El ahorro estimado es **conservador** (mejora del 20% en bin packing)
- En la práctica, clusters con baja utilización (<50%) pueden ahorrar más del 30-40%
- Clusters ya optimizados (>80% utilización) verán menores ahorros en infraestructura

### Limitaciones

- No considera costos de transferencia de datos
- No incluye costos de EBS adicionales
- Asume patrones de uso constantes (no considera variabilidad estacional)

## Interpretación de Resultados

### Alta Utilización (>70%)

Tu cluster está bien optimizado. Los beneficios principales serán operativos:
- Menos trabajo manual de gestión
- Auto-scaling más inteligente
- Simplificación operativa

### Utilización Media (40-70%)

Buen candidato para Auto Mode. Espera:
- Ahorro moderado en infraestructura (10-20%)
- Significativo ahorro operativo
- Mejor eficiencia durante picos y valles

### Baja Utilización (<40%)

Excelente candidato para Auto Mode. Potencial para:
- Ahorro sustancial en infraestructura (20-40%)
- Reducción de nodos requeridos
- Mejor aprovechamiento de recursos

## Troubleshooting

### Error: "Error cargando configuración de K8s"

Si elegiste el método con kubectl, verifica tu acceso:
```bash
aws eks update-kubeconfig --region <region> --name <cluster-name>
kubectl get nodes  # Verificar acceso
```

Si no tienes acceso con kubectl, ejecuta nuevamente y selecciona la opción 2 (AWS APIs).

### Error: "Error leyendo variables de entorno"

Si ejecutas manualmente, asegúrate de cargar las variables primero:
```bash
eval $(python3 recolector_eks_aws.py)
```

### Error: "No se encontraron nodos en el cluster"

Verifica que:
- El nombre del cluster sea correcto
- Los nodos tengan el tag `eks:cluster-name` con el nombre del cluster
- Los nodos estén en estado `running`

### CloudWatch Container Insights no disponible

Si ves el mensaje "CloudWatch Container Insights no disponible", el script usará valores por defecto (CPU: 45%, Memoria: 60%). Para obtener métricas reales:

1. Habilita Container Insights en tu cluster:
```bash
aws eks update-cluster-config \
  --region <region> \
  --name <cluster-name> \
  --logging '{"clusterLogging":[{"types":["api","audit","authenticator","controllerManager","scheduler"],"enabled":true}]}'
```

2. Instala CloudWatch agent en el cluster:
```bash
kubectl apply -f https://raw.githubusercontent.com/aws-samples/amazon-cloudwatch-container-insights/latest/k8s-deployment-manifest-templates/deployment-mode/daemonset/container-insights-monitoring/quickstart/cwagent-fluentd-quickstart.yaml
```

### Instancia no reconocida

Si el script no reconoce tu tipo de instancia, te pedirá el precio manualmente:
```
⚠️ Tipo de instancia detectado 'm6i.2xlarge' no está en mi DB local.
Por favor ingresa costo por hora USD para m6i.2xlarge: 0.384
```

## Próximos Pasos

Después de ejecutar el análisis:

1. **Revisar los resultados** con tu equipo
2. **Validar supuestos** de utilización con CloudWatch
3. **Planificar la migración** si los ahorros justifican el cambio
4. **Consultar documentación oficial** de EKS Auto Mode

## Referencias

- [EKS Auto Mode Documentation](https://docs.aws.amazon.com/eks/latest/userguide/automode.html)
- [EC2 Pricing](https://aws.amazon.com/ec2/pricing/on-demand/)
- [EKS Pricing](https://aws.amazon.com/eks/pricing/)

## Licencia

Este es un script de análisis. Úsalo bajo tu propio riesgo y valida los resultados con tu equipo de FinOps.
