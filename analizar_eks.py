#!/usr/bin/env python3
import subprocess
import sys
import os
from logger_utils import setup_logger

# Configurar logging
logger = setup_logger('analizar_eks', 'eks_analysis.log')

def print_header():
    print("\n" + "="*60)
    print("📊 CALCULADORA DE MIGRACIÓN A EKS AUTO MODE")
    print("="*60 + "\n")

def get_cluster_info():
    """Solicita información del cluster al usuario"""
    logger.info("Iniciando recolección de información del cluster")
    cluster_name = input("Nombre del cluster EKS: ").strip()
    if not cluster_name:
        logger.error("Nombre de cluster no proporcionado")
        print("❌ Nombre de cluster requerido")
        sys.exit(1)
    
    region = input("Región AWS (default: us-east-1): ").strip() or "us-east-1"
    logger.info(f"Cluster: {cluster_name}, Región: {region}")
    
    return cluster_name, region

def run_aws_collector(cluster_name, region):
    """Ejecuta el recolector basado en AWS APIs"""
    print("\n⏳ Recolectando datos con AWS APIs...")
    command = ["python3", "recolector_eks_aws.py"]
    input_data = f"{cluster_name}\n{region}\n"
    logger.info(f"Ejecutando recolector AWS: {' '.join(command)}")
    logger.info(f"Input: cluster={cluster_name}, region={region}")
    
    try:
        result = subprocess.run(
            command,
            input=input_data,
            capture_output=True,
            text=True,
            check=True
        )
        logger.info("Recolector AWS completado exitosamente")
        logger.debug(f"Salida del recolector: {result.stdout}")
        
        # Mostrar mensajes de progreso
        for line in result.stderr.split('\n'):
            if line.strip() and not 'DeprecationWarning' in line and not 'datetime.utcnow' in line:
                logger.info(f"Mensaje del recolector: {line}")
                print(line)
        return result.stdout
    except subprocess.CalledProcessError as e:
        logger.error(f"Error ejecutando recolector AWS: {e.stderr}")
        print(f"❌ Error ejecutando recolector AWS: {e.stderr}")
        return None

def run_calculator(env_vars):
    """Ejecuta la calculadora de costos con las variables de entorno"""
    print("\n" + "="*60)
    print("💰 CALCULANDO COSTOS")
    print("="*60 + "\n")
    
    logger.info("Iniciando calculadora de costos")
    logger.info(f"Variables de entorno: {env_vars}")
    
    try:
        # Crear un nuevo entorno limpiando variables EKS previas
        env = os.environ.copy()
        
        # Limpiar variables EKS previas
        for key in list(env.keys()):
            if key.startswith('EKS_'):
                del env[key]
        
        # Agregar las nuevas variables
        env.update(env_vars)
        
        command = ["python3", "calculadora_eks.py"]
        logger.info(f"Ejecutando calculadora: {' '.join(command)}")
        
        subprocess.run(command, env=env, check=True)
        logger.info("Calculadora completada exitosamente")
    except subprocess.CalledProcessError as e:
        logger.error(f"Error ejecutando calculadora: {e}")
        print(f"❌ Error ejecutando calculadora: {e}")
        sys.exit(1)

def main():
    logger.info("=== INICIANDO ANÁLISIS EKS AUTO MODE ===")
    print_header()
    
    cluster_name, region = get_cluster_info()
    
    # Recolectar datos usando AWS APIs
    env_output = run_aws_collector(cluster_name, region)
    
    if not env_output:
        logger.error("No se pudieron recolectar datos del cluster")
        print("❌ No se pudieron recolectar datos del cluster")
        sys.exit(1)
    
    # Parsear variables de entorno
    env_vars = {}
    for line in env_output.strip().split('\n'):
        if line.startswith('export '):
            var_def = line.replace('export ', '')
            key, value = var_def.split('=', 1)
            env_vars[key] = value.strip("'\"")
    
    logger.info(f"Variables parseadas: {env_vars}")
    
    # Ejecutar calculadora con las variables
    run_calculator(env_vars)
    logger.info("=== ANÁLISIS COMPLETADO ===")

if __name__ == "__main__":
    main()
