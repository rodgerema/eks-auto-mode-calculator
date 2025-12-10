# Changelog - Integración con Cost Explorer

## [v2.1.0] - 2025-12-10

### ✨ Nuevas Funcionalidades
- **Precio EKS Auto Mode desde API**: Nueva función `obtener_precio_eks_automode_aws()` que obtiene el precio real del fee de EKS Auto Mode directamente desde AWS Pricing API
- **Consulta optimizada de Cost Explorer**: Ajustada para terminar 2 días antes de hoy para evitar datos no consolidados

### 🔧 Mejoras
- **Precios más precisos**: El fee de Auto Mode ahora se obtiene de la API oficial en lugar de calcular un 12% fijo
- **Fallback robusto**: Si no se puede obtener el precio de Auto Mode, mantiene el 12% como respaldo
- **Datos más confiables**: Cost Explorer evita consultar datos de los últimos 2 días que pueden estar incompletos

### 📊 Cambios en el Reporte
- Muestra el precio real por hora del Auto Mode fee cuando está disponible
- Indica claramente si usa precio de API o fallback
- Formato mejorado: `@$0.0168/h por nodo` en lugar de `(12% de EC2)`

### 🛠️ Cambios Técnicos
- Removido el sistema de logging para simplificar el código
- Función `get_region_name_for_pricing()` centralizada
- Consulta específica para `operation: 'EKSAutoUsage'` en EKS Pricing API
- Búsqueda de productos con `eksproducttype` que contenga "AutoMode"

## [v2.0.0] - 2025-12-09

## Cambios Realizados

### ✅ Problema Resuelto

**Antes**: El script solo consultaba precios On-Demand, lo que sobreestimaba los costos reales cuando las cuentas tenían Savings Plans o Reserved Instances activos.

**Ahora**: El script consulta el **costo real** de los últimos 30 días desde Cost Explorer, reflejando automáticamente cualquier descuento aplicado.

---

## Modificaciones en los Scripts

### 1. `recolector_eks_aws.py`

**Nueva función agregada:**
```python
def get_real_cost_from_cost_explorer(cluster_name, region, days=30)
```

**Qué hace:**
- Consulta Cost Explorer API para obtener el costo real de EC2 del cluster
- Filtra por servicio: `Amazon Elastic Compute Cloud - Compute`
- Filtra por tag: `eks:cluster-name`
- Obtiene costos de los últimos 30 días
- Normaliza el resultado a un mes completo (30 días)

**Nueva variable de entorno exportada:**
- `EKS_MONTHLY_COST`: Costo real mensual de EC2 (incluye Savings/RI)

---

### 2. `calculadora_eks.py`

**Cambios en la lógica de cálculo:**

1. **Detección de descuentos:**
   - Calcula el precio efectivo por hora: `costo_real / (nodos × 730 horas)`
   - Compara con precio On-Demand para detectar % de descuento
   - Muestra el descuento aplicado en el reporte

2. **Cálculo de Auto Mode:**
   - Usa el **precio efectivo** (con descuentos) para estimar el costo en Auto Mode
   - Mantiene los mismos descuentos de Savings Plans/RI
   - Aplica el fee del 12% sobre el costo con descuento

3. **Reporte mejorado:**
   - Muestra precio On-Demand vs precio efectivo
   - Indica % de descuento detectado
   - Aclara que los descuentos se mantienen en Auto Mode

---

## Permisos AWS Adicionales Requeridos

Agregar a tu política IAM:

```json
{
  "Effect": "Allow",
  "Action": [
    "ce:GetCostAndUsage"
  ],
  "Resource": "*"
}
```

---

## Ejemplo de Salida

### Sin Cost Explorer (antes):
```
📊 ANÁLISIS DE CLUSTER ACTUAL
  Nodos:                 8 x m5.xlarge
  Región:                us-east-1
  Precio EC2/hora:       $0.1920
  ...
```

### Con Cost Explorer (ahora):
```
📊 ANÁLISIS DE CLUSTER ACTUAL
  Nodos:                 8 x m5.xlarge
  Región:                us-east-1
  Precio On-Demand:      $0.1920/hora
  Precio Efectivo:       $0.1152/hora
  Descuento aplicado:    40.0% (Savings/RI)
  Costo Real (30 días):  $672.38
  ...
```

---

## Ventajas de Este Cambio

1. **Precisión**: Refleja el costo real que estás pagando actualmente
2. **Transparencia**: Muestra claramente los descuentos aplicados
3. **Realismo**: Las estimaciones de Auto Mode son más precisas
4. **Decisiones informadas**: Comparas manzanas con manzanas

---

## Comportamiento de Fallback

Si Cost Explorer no está disponible (sin permisos o error):
- ✅ El script continúa funcionando
- ⚠️ Usa precios On-Demand como antes
- 📝 Muestra advertencia en el reporte

---

## Notas Importantes

### ¿Los Savings Plans funcionan con EKS Auto Mode?

**SÍ**. Los Savings Plans de Compute se aplican automáticamente a:
- EC2 en Managed Node Groups (actual)
- EC2 en EKS Auto Mode (futuro)
- Fargate
- Lambda

**Por lo tanto**: Si tienes un 40% de descuento ahora, lo mantendrás en Auto Mode.

### ¿Qué pasa con Reserved Instances?

Las Reserved Instances también se aplican automáticamente a las instancias EC2 que coincidan con:
- Tipo de instancia
- Región
- Plataforma (Linux)

El script detecta estos descuentos en el costo real de Cost Explorer.

---

## Testing

Para probar los cambios:

```bash
# 1. Verificar permisos
aws ce get-cost-and-usage \
  --time-period Start=2025-11-01,End=2025-12-01 \
  --granularity MONTHLY \
  --metrics UnblendedCost

# 2. Ejecutar el script
python3 analizar_eks.py

# 3. Verificar que aparezca:
# ✅ Consultando costo real en Cost Explorer...
# ✅ Costo real EC2 (últimos 30 días): $XXX.XX/mes
```

---

## Troubleshooting

### Error: "AccessDeniedException"
```
⚠️  No se pudo obtener costo de Cost Explorer: AccessDeniedException
```

**Solución**: Agregar permiso `ce:GetCostAndUsage` a tu usuario/rol IAM.

### No se detectan descuentos
```
Precio On-Demand:      $0.1920/hora
Precio Efectivo:       $0.1920/hora
```

**Posibles causas**:
1. No tienes Savings Plans ni Reserved Instances activos
2. El tag `eks:cluster-name` no está en las instancias EC2
3. Cost Explorer no tiene datos suficientes (cluster muy nuevo)

### Costo real es $0
```
⚠️  No se pudo obtener costo de Cost Explorer
```

**Solución**: El script usará precios On-Demand como fallback. Verifica:
- Permisos IAM
- Tags en las instancias EC2
- Que Cost Explorer esté habilitado en la cuenta
