#!/usr/bin/env python3
# run.py — CLI entry point. Run by systemd and manually.

import os
import sys
import argparse
import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path

def setup_logging(log_level: str):
    """V5 Enhancement: Set up rotating file logs so disk doesn't fill up."""
    Path("logs").mkdir(exist_ok=True)
    
    level = getattr(logging, log_level.upper())
    formatter = logging.Formatter('%(asctime)s %(name)s %(levelname)s %(message)s', datefmt='%Y-%m-%dT%H:%M:%SZ')
    
    # Console output
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)
    
    # Rotating file output (Max 5MB per file, keep last 3 backups)
    file_handler = RotatingFileHandler('logs/gridpulse.log', maxBytes=5*1024*1024, backupCount=3)
    file_handler.setFormatter(formatter)
    
    logging.basicConfig(level=level, handlers=[console_handler, file_handler])

def main():
    parser = argparse.ArgumentParser(description='GridPulse newsletter pipeline')
    parser.add_argument(
        '--edition',
        choices=['daily', 'weekly', 'monthly'],
        required=True,
        help='Which newsletter edition to generate and send'
    )
    parser.add_argument('--dry-run', action='store_true',
                        help='Generate but do not send email')
    parser.add_argument('--log-level', default=os.getenv('LOG_LEVEL', 'INFO'),
                        choices=['DEBUG', 'INFO', 'WARNING', 'ERROR'])
    args = parser.parse_args()

    setup_logging(args.log_level)

    # Late import: ensures logging is configured first
    from src.main import run_pipeline
    run_pipeline(edition=args.edition, dry_run=args.dry_run)

if __name__ == '__main__':
    main()
