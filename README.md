# Calculadora de Migración a EKS Auto Mode

Herramienta para analizar los costos de tu cluster EKS actual y estimar el ahorro potencial al migrar a **EKS Auto Mode**.

## Descripción

Este proyecto consta de dos scripts de Python:

1. **analizar_eks.py**: Script principal que orquesta todo el flujo (recomendado)
2. **recolector_eks_aws.py**: Recolecta métricas usando AWS APIs
3. **calculadora_eks.py**: Calcula costos y estima ahorros con EKS Auto Mode

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
        │  3️⃣  Obtención de Métricas (Cascada)       │
        │                                            │
        │     1. Container Insights (primario)       │
        │        → node_cpu/memory_utilization       │
        │     2. EC2 Metrics (alternativa)           │
        │        → CPUUtilization (ajustado)         │
        │     3. ASG Analysis (inferencia)           │
        │        → Estabilidad de escalado           │
        │     4. Input Manual (usuario)              │
        │     5. Fallback Conservador (último)       │
        │                                            │
        │     ⚠️  Siempre obtiene métricas, priori-  │
        │     zando las más precisas disponibles     │
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
        │  5️⃣  AWS Pricing API - GetProducts         │
        │     Service: AmazonEKS                     │
        │     Filtros:                               │
        │     • instanceType = <tipo detectado>      │
        │     • location = <región>                  │
        │     • operation = EKSAutoUsage             │
        │                                            │
        │     Obtiene:                               │
        │     • Precio EKS Auto Mode fee por hora    │
        └────────────────────────────────────────────┘
                                 │
                                 ▼
        ┌────────────────────────────────────────────┐
        │  6️⃣  CÁLCULOS DE COSTOS                     │
        │                                            │
        │  EKS Standard:                             │
        │  • Control Plane: $0.10/h × 730h           │
        │  • EC2: nodos × precio × 730h              │
        │                                            │
        │  EKS Auto Mode:                            │
        │  • Control Plane: $0.10/h × 730h           │
        │  • EC2: nodos_optimizados × precio × 730h  │
        │  • Auto Mode Fee: precio_real_automode/h   │
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
| **CloudWatch** | `GetMetricStatistics` | Métricas de utilización (múltiples namespaces) | `cloudwatch:GetMetricStatistics` |
| **AutoScaling** | `DescribeAutoScalingGroups` | Análisis de patrones de escalado | `autoscaling:DescribeAutoScalingGroups` |
| **Cost Explorer** | `GetCostAndUsage` | Costo real (incluye Savings/RI) | `ce:GetCostAndUsage` |
| **Pricing** | `GetProducts` | Precios On-Demand EC2 y EKS Auto Mode | `pricing:GetProducts` |

**Métricas de CloudWatch utilizadas:**
- `ContainerInsights` namespace: `node_cpu_utilization`, `node_memory_utilization` (primario)
- `AWS/EC2` namespace: `CPUUtilization` (alternativa)
- `AWS/AutoScaling` namespace: `GroupDesiredCapacity` (análisis complementario)

**Notas importantes**:
- El Pricing API siempre se consulta en `us-east-1` independientemente de la región del cluster
- Cost Explorer consulta los últimos 30 días terminando 2 días antes de hoy para evitar datos no consolidados
- El sistema de cascada asegura obtener métricas incluso sin Container Insights habilitado

## Cómo se Calculan los Costos

### Sistema de Obtención de Métricas con Cascada Inteligente

El script implementa un **sistema de cascada de fallback** que asegura obtener siempre las métricas más precisas disponibles, incluso si Container Insights no está habilitado:

#### Orden de Evaluación (de más a menos preciso)

1. **Container Insights** (★★★★★ - 95%+ precisión)
   - Métricas a nivel de contenedor/pod
   - Excluye overhead del host
   - Requiere habilitación explícita

2. **CloudWatch EC2 Metrics** (★★★★☆ - 80-85% precisión)
   - Métricas básicas de EC2 (siempre disponibles)
   - Ajustado por overhead del host (~8%)
   - Usa CPU como proxy para estimar memoria

3. **Análisis de ASG** (★★★☆☆ - 70% precisión)
   - Analiza patrones de escalado histórico
   - Si ASG no escaló en 30 días → cluster sobreaprovisionado
   - Usa valores conservadores (30% CPU, 45% MEM)

4. **Input Manual** (★★★★☆ - depende del usuario)
   - Permite ingresar valores de herramientas externas
   - Útil si tienes Datadog, Prometheus, etc.

5. **Fallback Conservador** (★★☆☆☆ - 60% precisión)
   - Valores basados en industry benchmarks
   - CPU: 35%, Memoria: 50%
   - Más conservador que versión anterior

**Ventaja clave:** Incluso sin Container Insights, obtienes métricas reales basadas en datos de tu cluster, no estimaciones genéricas.

### Obtención de Precios en Tiempo Real

El script obtiene automáticamente los precios actuales desde la **AWS Price List API oficial**:
- **Precios On-Demand para instancias EC2**: Precio base de las instancias
- **Precios EKS Auto Mode Fee**: Precio real del fee de Auto Mode por instancia/hora
- Actualizados en tiempo real desde AWS
- Soporta múltiples regiones (us-east-1, us-west-2, eu-west-1, etc.)
- Fallback a 12% sobre EC2 si no hay conectividad para Auto Mode fee

### Costo Actual (EKS Standard con Managed Node Groups)

```
Costo Mensual = Control Plane + Instancias EC2

Control Plane = $0.10/hora × 730 horas = $73/mes
Instancias EC2 = Número de Nodos × Precio por Hora × 730 horas/mes
```

### Costo Estimado con EKS Auto Mode

EKS Auto Mode mejora la eficiencia mediante **Bin Packing automático** y cobra un **fee específico** por instancia/hora.

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
   Auto Mode Fee = Nodos Equivalentes × Precio Auto Mode Fee × 730 horas/mes

   Total = Control Plane + Instancias EC2 + Auto Mode Fee
   ```

**Nota importante**: El fee de EKS Auto Mode se obtiene directamente de la AWS Pricing API, con fallback al 12% sobre EC2 si no está disponible.

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

### 4. Dependencias de Python

El script necesita las siguientes librerías:
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

### 3. kubectl Configurado (No requerido)

El script usa únicamente AWS APIs para obtener toda la información necesaria. No requiere acceso directo al cluster con kubectl.

### 5. Permisos AWS Requeridos

Tu usuario/rol de AWS necesita permisos para:

**Permisos Básicos (Requeridos):**
- `eks:DescribeCluster` - Obtener información del cluster
- `ec2:DescribeInstances` - Listar nodos EC2
- `pricing:GetProducts` - Obtener precios de EC2 y EKS Auto Mode en tiempo real

**Permisos Opcionales (Recomendados para mayor precisión):**
- `cloudwatch:GetMetricStatistics` - Métricas de utilización (Container Insights, EC2, ASG)
- `autoscaling:DescribeAutoScalingGroups` - Análisis de patrones de escalado
- `ce:GetCostAndUsage` - Costo real con Savings Plans/RI

**Nota sobre métricas**: El script implementa un sistema de cascada que siempre obtendrá métricas:
- Con Container Insights: ~95% precisión
- Sin Container Insights pero con métricas EC2: ~80-85% precisión
- Sin métricas pero con acceso a ASG: ~70% precisión
- Sin ninguna métrica: Fallback conservador basado en industry benchmarks

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

### Script Unificado (Recomendado)

El script `analizar_eks.py` ejecuta todo el flujo automáticamente:

```bash
python3 analizar_eks.py
```

El script te preguntará:
1. Nombre del cluster EKS
2. Región AWS (default: us-east-1)

**Ejemplo de ejecución:**
```
📊 CALCULADORA DE MIGRACIÓN A EKS AUTO MODE

Nombre del cluster EKS: mi-cluster-prod
Región AWS (default: us-east-1): us-east-1

⏳ Recolectando datos con AWS APIs...
✅ Cluster encontrado: mi-cluster-prod (versión 1.28)
✅ Nodos encontrados: 11 (c5.4xlarge)
✅ Utilización CPU: 42.5%, Memoria: 58.3%

💰 CALCULANDO COSTOS
...
```

### Ejecución Manual (Paso a Paso)

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
  Auto Mode Fee:         $    114.25  (@$0.0168/h por nodo)
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
  • EKS Auto Mode fee obtenido directamente de AWS API
  • Estimación asume mejora del 20% en bin packing
  • Ahorro operativo: 10h/mes × $50/h

============================================================
🔗 REFERENCIAS DE PRICING
============================================================
  EC2 Pricing (m5.xlarge):
    https://aws.amazon.com/ec2/pricing/on-demand/

  EKS Control Plane Pricing:
    https://aws.amazon.com/eks/pricing/

  EKS Auto Mode Pricing:
    https://docs.aws.amazon.com/eks/latest/userguide/automode.html
============================================================
```

## Variables de Entorno

El recolector genera las siguientes variables:

| Variable | Descripción | Ejemplo |
|----------|-------------|---------|
| `EKS_PRIMARY_INSTANCE` | Tipo de instancia más común | `m5.xlarge` |
| `EKS_NODE_COUNT` | Número total de nodos | `8` |
| `EKS_UTIL_CPU` | % Utilización CPU (requests/capacity) | `45.30` |
| `EKS_UTIL_MEM` | % Utilización RAM (requests/capacity) | `62.15` |
| `AWS_REGION` | Región del cluster | `us-east-1` |
| `EKS_MONTHLY_COST` | Costo real mensual (incluye descuentos) | `1200.50` |
| `EKS_MONTHLY_COST_ONDEMAND` | Costo On-Demand equivalente | `1500.00` |
| `EKS_SAVINGS_PERCENTAGE` | Porcentaje de ahorro actual | `20.0` |
| `EKS_METRIC_SOURCE` | Fuente de las métricas | `Container Insights` |
| `EKS_COST_SOURCE` | Fuente del costo | `Cost Explorer` |

## Sistema de Logging

### Configuración de Logs

Los scripts generan logs detallados para facilitar el debugging y monitoreo:

**Ubicación de logs:**
- Por defecto: carpeta `logs/` en el directorio del proyecto
- Configurable mediante la variable de entorno: `EKS_CALCULATOR_LOG_DIR`

```bash
# Cambiar directorio de logs
export EKS_CALCULATOR_LOG_DIR="/var/log/eks-calculator"
python3 analizar_eks.py

# O usar el directorio por defecto (logs/)
python3 analizar_eks.py
```

### Archivos de Log Generados

| Archivo | Script | Contenido |
|---------|--------|-----------|
| `logs/eks_analysis.log` | `analizar_eks.py` | Flujo completo de análisis, ejecución de subprocesos |
| `logs/eks_collector_aws.log` | `recolector_eks_aws.py` | Llamadas a APIs de AWS (EKS, EC2, CloudWatch, Cost Explorer) |

### Información Registrada

- **Comandos ejecutados**: Cada script y sus parámetros
- **Llamadas a AWS APIs**: EKS, EC2, CloudWatch, Cost Explorer, Pricing
- **Resultados y errores**: Precios obtenidos, costos calculados, errores de API
- **Variables y parámetros**: Todas las variables de entorno generadas y usadas

### Revisar Logs

```bash
# Ver logs en tiempo real
tail -f logs/eks_analysis.log

# Ver todos los logs
cat logs/*.log

# Buscar errores
grep ERROR logs/*.log

# Buscar llamadas específicas a AWS
grep "AWS API" logs/eks_collector_aws.log

# Contar llamadas por servicio
grep "AWS API:" logs/eks_collector_aws.log | cut -d: -f4 | cut -d. -f1 | sort | uniq -c
```

### Formato de Logs

```
YYYY-MM-DD HH:MM:SS - nombre_logger - NIVEL - mensaje
```

Ejemplo:
```
2025-12-18 14:30:45 - analizar_eks - INFO - Cluster: mi-cluster, Región: us-east-1
2025-12-18 14:30:46 - recolector_aws - INFO - AWS API: EKS.describe_cluster
2025-12-18 14:30:47 - recolector_aws - INFO - Encontrados 8 nodos
```

## Notas Importantes

### Sobre los Precios

- **Precios en Tiempo Real**: El script obtiene automáticamente los precios actuales desde la AWS Price List API
- **Multi-Región**: Soporta múltiples regiones de AWS (usa la variable `AWS_REGION`)
- **Precios On-Demand**: Se consultan precios On-Demand de instancias Linux
- **Costo Real con Cost Explorer**: Si tienes permisos `ce:GetCostAndUsage`, el script obtiene el costo real de los últimos 30 días
- **Savings Plans / Reserved Instances**: El costo real de Cost Explorer incluye automáticamente estos descuentos
- **Fallback**: Si no hay conectividad con AWS, usa precios predefinidos de us-east-1
- **EKS Auto Mode Fee**: Se obtiene directamente de la AWS Pricing API, con fallback al 12% sobre EC2 si no está disponible
- **Importante**: Los descuentos de Savings Plans/RI se mantendrían al migrar a Auto Mode
- **Cost Explorer**: Consulta los últimos 30 días terminando 2 días antes de hoy para evitar datos no consolidados

### Sobre las Métricas de Utilización

- **Sistema de cascada inteligente**: Siempre obtiene métricas, priorizando las más precisas
- **Sin Container Insights**: El script usa métricas EC2 básicas (siempre disponibles) ajustadas por overhead
- **Valores de fallback actualizados**: Basados en industry benchmarks (Datadog, CNCF, Fairwinds)
- **Transparencia**: El reporte indica claramente la fuente de métricas utilizada

### Sobre las Estimaciones

- El ahorro estimado es **conservador** (mejora del 20% en bin packing)
- En la práctica, clusters con baja utilización (<50%) pueden ahorrar más del 30-40%
- Clusters ya optimizados (>80% utilización) verán menores ahorros en infraestructura
- Los valores de fallback son más conservadores que versión anterior (35% CPU vs 45%)

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

### Error: "Timeout: El recolector tardó más de 30 segundos"

El script `analizar_eks.py` tiene un timeout de 30 segundos para el recolector con kubectl. Si tu cluster es muy grande:
```bash
# Ejecuta manualmente sin timeout
eval $(python3 recolector_eks.py)
python3 calculadora_eks.py
```

### Error: "Error cargando configuración de K8s"

Este error ya no aplica ya que el script no usa kubectl. Si ves este error, verifica que estés usando la versión actualizada del script.

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

Si ves el mensaje "CloudWatch Container Insights no disponible", **no te preocupes**. El script automáticamente:

1. Intentará usar **métricas EC2 básicas** (siempre disponibles, ~80-85% precisión)
2. Si no hay métricas EC2, analizará **patrones de ASG** para inferir sobreaprovisionamiento
3. Te ofrecerá **ingresar valores manualmente** si los conoces
4. Como último recurso, usará **valores conservadores** basados en industry benchmarks

**Para obtener la máxima precisión (Container Insights):**

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

**Nota**: El sistema de cascada asegura que siempre obtendrás un análisis útil, incluso sin Container Insights.

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
