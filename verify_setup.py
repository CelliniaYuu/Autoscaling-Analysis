#!/usr/bin/env python
"""
Quick verification script - check project setup
"""
import sys
import os
from pathlib import Path
from dotenv import load_dotenv

def check_item(name, path_or_module, is_file=True):
    """Check if file exists or module imports"""
    try:
        if is_file:
            exists = Path(path_or_module).exists()
            print(f"  {'✓' if exists else '✗'} {name}")
            return exists
        else:
            __import__(path_or_module)
            print(f"  ✓ {name}")
            return True
    except ImportError:
        print(f"  ✗ {name}")
        return False

def verify():
    """Run all verifications"""
    print("\n" + "="*60)
    print("PROJECT VERIFICATION")
    print("="*60)
    
    # 1. Environment
    print("\n1. Environment:")
    load_dotenv()
    env_ok = Path('.env').exists()
    print(f"  {'✓' if env_ok else '✗'} .env file")
    
    # 2. Directories
    print("\n2. Directory Structure:")
    dirs = ['src', 'DATA', 'models', 'outputs', 'configs']
    dir_ok = all(check_item(d, d) for d in dirs)
    
    # 3. Source files
    print("\n3. Source Files:")
    files = [
        ('data_loader.py', 'src/data_loader.py'),
        ('forecasters.py', 'src/forecasters.py'),
        ('autoscaling.py', 'src/autoscaling.py'),
        ('train.py', 'train.py'),
        ('clean_data.py', 'clean_data.py'),
    ]
    files_ok = all(check_item(name, path) for name, path in files)
    
    # 4. Dependencies
    print("\n4. Dependencies:")
    modules = [
        ('pandas', 'pandas'),
        ('numpy', 'numpy'),
        ('sklearn', 'sklearn'),
        ('xgboost', 'xgboost'),
        ('fastapi', 'fastapi'),
        ('streamlit', 'streamlit'),
    ]
    deps_ok = all(check_item(name, module, is_file=False) for name, module in modules)
    
    # 5. Data
    print("\n5. Data Files:")
    data_ok = check_item('train.txt', 'DATA/train.txt') or \
              check_item('test.txt', 'DATA/test.txt') or \
              check_item('combined.txt', 'DATA/combined.txt')
    
    # 6. Imports
    print("\n6. Project Imports:")
    sys.path.insert(0, '.')
    try:
        from src.data_loader import HTTPLogParser
        from src.forecasters import create_forecaster
        from src.autoscaling import ThresholdScalingPolicy
        imports_ok = True
        print("  ✓ All modules imported successfully")
    except Exception as e:
        imports_ok = False
        print(f"  ✗ Import error: {e}")
    
    # Summary
    print("\n" + "="*60)
    all_ok = env_ok and dir_ok and files_ok and deps_ok and imports_ok
    
    if all_ok:
        print("✅ ALL CHECKS PASSED - READY TO RUN!")
        print("\nQuick start:")
        print("  python clean_data.py     # Clean data first")
        print("  python train.py          # Run training pipeline")
        print("  streamlit run dashboard.py  # View dashboard")
    else:
        print("⚠️  SOME CHECKS FAILED")
        print("\nFix with:")
        print("  pip install -r requirements.txt")
    print("="*60 + "\n")
    
    return 0 if all_ok else 1

if __name__ == "__main__":
    sys.exit(verify())
