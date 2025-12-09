#!/usr/bin/env python3
import subprocess
import sys
import os

def print_header():
    print("\n" + "="*60)
    print("📊 CALCULADORA DE MIGRACIÓN A EKS AUTO MODE")
    print("="*60 + "\n")

def get_cluster_info():
    """Solicita información del cluster al usuario"""
    cluster_name = input("Nombre del cluster EKS: ").strip()
    if not cluster_name:
        print("❌ Nombre de cluster requerido")
        sys.exit(1)
    
    region = input("Región AWS (default: us-east-1): ").strip() or "us-east-1"
    
    print("\n¿Tienes acceso directo al cluster con kubectl?")
    print("  1) Sí - Usar kubectl (más preciso)")
    print("  2) No - Usar AWS APIs solamente")
    
    choice = input("\nSelecciona opción [1/2]: ").strip()
    
    return cluster_name, region, choice == "1"

def run_kubectl_collector(cluster_name, region):
    """Ejecuta el recolector basado en kubectl"""
    print("\n⏳ Recolectando datos con kubectl...")
    try:
        result = subprocess.run(
            ["python3", "recolector_eks.py"],
            capture_output=True,
            text=True,
            check=True,
            timeout=30
        )
        # Mostrar mensajes de progreso de stderr
        if result.stderr:
            print(result.stderr, end='')
        return result.stdout
    except subprocess.TimeoutExpired:
        print("❌ Timeout: El recolector tardó más de 30 segundos")
        return None
    except subprocess.CalledProcessError as e:
        print(f"❌ Error ejecutando recolector kubectl: {e.stderr}")
        return None

def run_aws_collector(cluster_name, region):
    """Ejecuta el recolector basado en AWS APIs"""
    print("\n⏳ Recolectando datos con AWS APIs...")
    try:
        result = subprocess.run(
            ["python3", "recolector_eks_aws.py"],
            input=f"{cluster_name}\n{region}\n",
            capture_output=True,
            text=True,
            check=True
        )
        # Mostrar mensajes de progreso
        for line in result.stderr.split('\n'):
            if line.strip() and not 'DeprecationWarning' in line and not 'datetime.utcnow' in line:
                print(line)
        return result.stdout
    except subprocess.CalledProcessError as e:
        print(f"❌ Error ejecutando recolector AWS: {e.stderr}")
        return None

def run_calculator(env_vars):
    """Ejecuta la calculadora de costos con las variables de entorno"""
    print("\n" + "="*60)
    print("💰 CALCULANDO COSTOS")
    print("="*60 + "\n")
    try:
        # Crear un nuevo entorno limpiando variables EKS previas
        env = os.environ.copy()
        
        # Limpiar variables EKS previas
        for key in list(env.keys()):
            if key.startswith('EKS_'):
                del env[key]
        
        # Agregar las nuevas variables
        env.update(env_vars)
        
        subprocess.run(["python3", "calculadora_eks.py"], env=env, check=True)
    except subprocess.CalledProcessError as e:
        print(f"❌ Error ejecutando calculadora: {e}")
        sys.exit(1)

def main():
    print_header()
    
    cluster_name, region, has_kubectl_access = get_cluster_info()
    
    # Recolectar datos según el método disponible
    if has_kubectl_access:
        env_output = run_kubectl_collector(cluster_name, region)
    else:
        env_output = run_aws_collector(cluster_name, region)
    
    if not env_output:
        print("❌ No se pudieron recolectar datos del cluster")
        sys.exit(1)
    
    # Parsear variables de entorno
    env_vars = {}
    for line in env_output.strip().split('\n'):
        if line.startswith('export '):
            var_def = line.replace('export ', '')
            key, value = var_def.split('=', 1)
            env_vars[key] = value.strip("'\"")
    
    # Ejecutar calculadora con las variables
    run_calculator(env_vars)

if __name__ == "__main__":
    main()
