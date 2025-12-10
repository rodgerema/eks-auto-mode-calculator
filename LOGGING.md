# Sistema de Logging - EKS Auto Mode Calculator

## Descripción

Se ha agregado un sistema de logging completo que registra todas las operaciones, comandos ejecutados y llamadas a APIs de AWS para facilitar el debugging y monitoreo de la aplicación.

## Archivos de Log Generados

| Archivo | Descripción | Contenido |
|---------|-------------|-----------|
| `eks_analysis.log` | Log principal del script `analizar_eks.py` | Flujo completo de análisis, decisiones de usuario, ejecución de subprocesos |
| `eks_collector_aws.log` | Log del recolector AWS `recolector_eks_aws.py` | Llamadas a APIs de AWS (EKS, EC2, CloudWatch, Cost Explorer) |
| `eks_calculator.log` | Log de la calculadora `calculadora_eks.py` | Cálculos de costos, consultas al Pricing API |
| `test.log` | Log de pruebas | Usado por `test_logging.py` para verificar funcionamiento |

## Información Registrada

### 1. Comandos Ejecutados
```
2025-12-09 22:22:57 - analizar_eks - INFO - Ejecutando recolector AWS: python3 recolector_eks_aws.py
2025-12-09 22:22:57 - analizar_eks - INFO - Input: cluster=mi-cluster, region=us-east-1
```

### 2. Llamadas a AWS APIs
```
2025-12-09 22:22:57 - recolector_aws - INFO - AWS API: EKS.describe_cluster
2025-12-09 22:22:57 - recolector_aws - INFO - API exitosa: describe_cluster
2025-12-09 22:22:57 - recolector_aws - INFO - AWS API: EC2.describe_instances
```

### 3. Resultados y Errores
```
2025-12-09 22:22:57 - calculadora_eks - INFO - Precio obtenido de AWS: $0.1920/hora para m5.xlarge
2025-12-09 22:22:57 - recolector_aws - ERROR - Error API EC2.describe_instances: Access denied
```

### 4. Variables y Parámetros
```
2025-12-09 22:22:57 - calculadora_eks - INFO - Variables leídas: instance_type=m5.xlarge, node_count=8, cpu=42.50%, mem=58.30%, region=us-east-1
2025-12-09 22:22:57 - recolector_aws - INFO - Variables generadas: {'EKS_PRIMARY_INSTANCE': 'm5.xlarge', 'EKS_NODE_COUNT': '8'}
```

## Configuración del Logging

### Módulo `logger_utils.py`

Proporciona funciones estandarizadas para logging:

- `setup_logger(name, log_file, level)`: Configura un logger con formato consistente
- `log_command_execution(logger, command, result, error)`: Log para comandos del sistema
- `log_aws_api_call(logger, service, operation, params, result, error)`: Log para APIs de AWS

### Formato de Logs

```
YYYY-MM-DD HH:MM:SS - nombre_logger - NIVEL - mensaje
```

Ejemplo:
```
2025-12-09 22:22:57 - analizar_eks - INFO - Cluster: mi-cluster, Región: us-east-1
```

## Uso

### Ejecución Normal
Los logs se generan automáticamente al ejecutar cualquier script:

```bash
python3 analizar_eks.py
# Genera: eks_analysis.log, eks_collector_aws.log, eks_calculator.log
```

### Verificar Logging
```bash
python3 test_logging.py
# Genera: test.log y muestra confirmación en pantalla
```

### Revisar Logs
```bash
# Ver logs en tiempo real
tail -f eks_analysis.log

# Ver todos los logs
cat eks_*.log

# Buscar errores
grep ERROR eks_*.log

# Buscar llamadas específicas a AWS
grep "AWS API" eks_collector_aws.log
```

## Niveles de Log

| Nivel | Uso | Ejemplo |
|-------|-----|---------|
| `INFO` | Operaciones normales | Inicio de procesos, resultados exitosos |
| `WARNING` | Situaciones no críticas | CloudWatch no disponible, usando defaults |
| `ERROR` | Errores que impiden continuar | Fallos de API, credenciales inválidas |
| `DEBUG` | Información detallada | Parámetros de APIs, respuestas completas |

## Troubleshooting con Logs

### Error de Credenciales AWS
```bash
grep -A2 -B2 "credentials\|Access denied" eks_*.log
```

### Problemas de Red/Conectividad
```bash
grep -A2 -B2 "timeout\|connection\|network" eks_*.log
```

### Verificar Llamadas a APIs
```bash
grep "AWS API:" eks_collector_aws.log | sort | uniq -c
```

### Ver Flujo Completo de Ejecución
```bash
grep "===" eks_analysis.log
```

## Rotación de Logs

Los archivos de log se sobrescriben en cada ejecución. Para mantener historial:

```bash
# Crear backup antes de ejecutar
cp eks_analysis.log eks_analysis_$(date +%Y%m%d_%H%M%S).log.bak

# O usar logrotate (configuración avanzada)
```

## Configuración Avanzada

### Cambiar Nivel de Log
Editar `logger_utils.py`:
```python
logger.setLevel(logging.DEBUG)  # Para más detalle
logger.setLevel(logging.WARNING)  # Para menos detalle
```

### Agregar Timestamp a Archivos
```python
log_file = f"eks_analysis_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
logger = setup_logger('analizar_eks', log_file)
```

### Log Solo a Archivo (Sin Consola)
Modificar `setup_logger()` para remover `console_handler`.

## Ejemplos de Análisis

### Verificar Tiempo de Ejecución
```bash
head -1 eks_analysis.log && tail -1 eks_analysis.log
```

### Contar Llamadas por Servicio AWS
```bash
grep "AWS API:" eks_collector_aws.log | cut -d: -f4 | cut -d. -f1 | sort | uniq -c
```

### Ver Solo Errores
```bash
grep ERROR eks_*.log | cut -d- -f4-
```

Este sistema de logging te permitirá identificar rápidamente problemas, optimizar el rendimiento y entender el flujo completo de ejecución de la aplicación.
