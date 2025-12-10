#!/usr/bin/env python3
"""
Script de prueba para verificar que el logging funciona correctamente
"""
from logger_utils import setup_logger, log_command_execution, log_aws_api_call

def test_logging():
    # Configurar logger
    logger = setup_logger('test_logging', 'test.log')
    
    # Probar diferentes tipos de logs
    logger.info("Iniciando prueba de logging")
    
    # Simular ejecución de comando
    log_command_execution(logger, "kubectl get nodes", result="3 nodes found")
    log_command_execution(logger, "aws eks describe-cluster", error="Access denied")
    
    # Simular llamadas AWS API
    log_aws_api_call(logger, 'EKS', 'describe_cluster', 
                     params={'name': 'test-cluster'}, 
                     result="Cluster found")
    
    log_aws_api_call(logger, 'EC2', 'describe_instances', 
                     error="Invalid region")
    
    logger.info("Prueba de logging completada")
    print("✅ Logging configurado correctamente")
    print("📄 Revisa los archivos de log generados:")
    print("   - test.log")
    print("   - eks_analysis.log (cuando ejecutes analizar_eks.py)")
    print("   - eks_collector_aws.log (cuando ejecutes recolector_eks_aws.py)")
    print("   - eks_calculator.log (cuando ejecutes calculadora_eks.py)")

if __name__ == "__main__":
    test_logging()
