#!/usr/bin/env python3
import logging
import sys
from datetime import datetime

def setup_logger(name, log_file=None, level=logging.INFO):
    """Configura un logger con formato consistente"""
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
        file_handler = logging.FileHandler(log_file)
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
