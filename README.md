# Calculadora de Migración a EKS Auto Mode

Herramienta para analizar los costos de tu cluster EKS actual y estimar el ahorro potencial al migrar a **EKS Auto Mode**.

## Descripción

Este proyecto consta de dos scripts de Python que trabajan en conjunto:

1. **recolector_eks.py**: Recolecta métricas del cluster EKS actual
2. **calculadora_eks.py**: Calcula costos y estima ahorros con EKS Auto Mode

## Cómo se Calculan los Costos

### Costo Actual (Managed Node Groups / ASG)

```
Costo Mensual Actual = Número de Nodos × Precio por Hora × 730 horas/mes
```

El script usa precios On-Demand de us-east-1 para las instancias EC2 más comunes:
- Familias T3/T3a (general purpose burstable)
- Familias M5/M6i (general purpose)
- Familia C5 (compute optimized)
- Familia R5 (memory optimized)

### Costo Estimado con EKS Auto Mode

EKS Auto Mode mejora la eficiencia del cluster mediante **Bin Packing automático** (empaquetado óptimo de pods en nodos).

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
   Costo Auto Mode = Nodos Equivalentes × Precio por Hora × 730 horas/mes
   ```

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

### 2. Kubernetes Python Client

```bash
pip install kubernetes
```

O si usas un entorno virtual:
```bash
python3 -m venv venv
source venv/bin/activate  # En Linux/Mac
# o en Windows: venv\Scripts\activate
pip install kubernetes
```

### 3. kubectl Configurado

Asegúrate de tener acceso a tu cluster EKS:

```bash
# Configurar kubeconfig
aws eks update-kubeconfig --region <tu-region> --name <nombre-cluster>

# Verificar acceso
kubectl get nodes
```

### 4. Permisos AWS

Tu usuario/rol de AWS necesita permisos para:
- `eks:DescribeCluster`
- `eks:UpdateClusterConfig` (solo para obtener kubeconfig)

Y en Kubernetes necesitas permisos de lectura:
- `nodes` (list)
- `pods` (list en todos los namespaces)

## Instalación

```bash
# Clonar o descargar los scripts
cd eks-auto-mode-calculator

# Crear entorno virtual (recomendado)
python3 -m venv venv
source venv/bin/activate

# Instalar dependencias
pip install kubernetes
```

## Uso

### Ejecución Automática (Recomendado)

Ejecuta ambos scripts en un solo comando:

```bash
# Linux/Mac
eval $(python3 recolector_eks.py) && python3 calculadora_eks.py

# Windows (PowerShell)
python recolector_eks.py | Invoke-Expression
python calculadora_eks.py
```

### Ejecución Manual (Paso a Paso)

#### Paso 1: Recolectar Datos

```bash
# Generar variables de entorno
python3 recolector_eks.py > eks_vars.sh

# Verificar las variables generadas
cat eks_vars.sh
```

Salida esperada:
```bash
export EKS_PRIMARY_INSTANCE='m5.large'
export EKS_NODE_COUNT='5'
export EKS_UTIL_CPU='45.30'
export EKS_UTIL_MEM='62.15'
```

#### Paso 2: Cargar Variables

```bash
# Cargar las variables en tu sesión
source eks_vars.sh

# Verificar que se cargaron
echo $EKS_NODE_COUNT
```

#### Paso 3: Calcular Costos

```bash
python3 calculadora_eks.py
```

## Ejemplo de Salida

```
⏳ Recolectando datos del cluster...
✅ Datos recolectados: 8 nodos, Instancia m5.xlarge

--- 📊 Calculadora de Migración a EKS Auto Mode (Automática) ---

Cluster Actual Detectado:
  - Nodos: 8 x m5.xlarge
  - Utilización (Requests/Capacity): CPU 42.5% | RAM 58.3%

----------------------------------------
💰 ANÁLISIS DE COSTOS
Costo Mensual ACTUAL:              $1,121.28
Costo Mensual AUTO MODE (Est.):    $952.09
----------------------------------------
✅ AHORRO TOTAL ESTIMADO:          $669.19 / mes
   (Infra: $169.19 + Ops: $500.00)
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

- Los precios son para instancias **On-Demand en us-east-1**
- Si usas Reserved Instances o Savings Plans, ajusta los cálculos manualmente
- Para instancias no listadas, el script te pedirá ingresar el precio por hora

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

Solución:
```bash
aws eks update-kubeconfig --region <region> --name <cluster-name>
kubectl get nodes  # Verificar acceso
```

### Error: "Error leyendo variables de entorno"

Ejecuta primero el recolector:
```bash
eval $(python3 recolector_eks.py)
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
