import logging
import sys
import os

def setup_logger():
    logger = logging.getLogger("swingmaster")
    logger.setLevel(logging.INFO)
    
    # Hapus handlers yang sudah ada biar tidak duplikat saat reload
    if logger.handlers:
        logger.handlers.clear()
        
    # Format output log
    formatter = logging.Formatter(
        '%(asctime)s | %(levelname)-8s | %(message)s', 
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    
    # Simpan ke file backend.log di root folder
    log_path = os.path.join(os.getcwd(), 'backend.log')
    file_handler = logging.FileHandler(log_path, encoding='utf-8')
    file_handler.setFormatter(formatter)
    
    # Tampilkan juga di console/terminal
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)
    
    logger.addHandler(file_handler)
    logger.addHandler(console_handler)
        
    return logger

logger = setup_logger()
