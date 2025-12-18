#!/usr/bin/env python3
import logging
import sys
import os
from datetime import datetime
from pathlib import Path

# Directorio de logs configurable mediante variable de entorno
LOG_DIR = os.environ.get('EKS_CALCULATOR_LOG_DIR', 'logs')

def ensure_log_dir(log_dir=None):
    """Crea el directorio de logs si no existe"""
    target_dir = log_dir or LOG_DIR
    Path(target_dir).mkdir(parents=True, exist_ok=True)
    return target_dir

def setup_logger(name, log_file=None, level=logging.INFO, log_dir=None):
    """
    Configura un logger con formato consistente

    Args:
        name: Nombre del logger
        log_file: Nombre del archivo de log (sin ruta)
        level: Nivel de logging (default: INFO)
        log_dir: Directorio donde guardar los logs (default: 'logs' o variable EKS_CALCULATOR_LOG_DIR)
    """
    logger = logging.getLogger(name)
    logger.setLevel(level)

    # Evitar duplicar handlers
    if logger.handlers:
        return logger

    # Formato del log
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )

    # Solo log a archivo, no a consola para mantener salida limpia

    # Handler para archivo si se especifica
    if log_file:
        # Asegurar que el directorio existe
        target_dir = ensure_log_dir(log_dir)
        log_path = os.path.join(target_dir, log_file)

        file_handler = logging.FileHandler(log_path)
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)

    return logger

def log_command_execution(logger, command, result=None, error=None):
    """Log estandarizado para ejecución de comandos"""
    logger.info(f"Ejecutando comando: {command}")
    if result:
        logger.info(f"Resultado exitoso: {result}")
    if error:
        logger.error(f"Error en comando: {error}")

def log_aws_api_call(logger, service, operation, params=None, result=None, error=None):
    """Log estandarizado para llamadas AWS API"""
    logger.info(f"AWS API: {service}.{operation}")
    if params:
        logger.debug(f"Parámetros: {params}")
    if result:
        logger.info(f"API exitosa: {operation}")
    if error:
        logger.error(f"Error API {service}.{operation}: {error}")
