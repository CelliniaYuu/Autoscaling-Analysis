"""
Verification script to test all components
Run this to ensure project is set up correctly
"""
import sys
import os
from pathlib import Path

def print_header(text):
    print(f"\n{'='*60}")
    print(f"  {text}")
    print(f"{'='*60}")

def check_file_exists(path, description):
    if Path(path).exists():
        print(f"✓ {description}: {path}")
        return True
    else:
        print(f"✗ {description}: {path} (NOT FOUND)")
        return False

def check_module_import(module_name):
    try:
        __import__(module_name)
        print(f"✓ {module_name} imported successfully")
        return True
    except ImportError as e:
        print(f"✗ {module_name} import failed: {e}")
        return False

def check_environment():
    """Check .env file"""
    print_header("1. ENVIRONMENT CHECK")
    
    checks = []
    checks.append(check_file_exists("d:\\AAA_Model\\.env", ".env file"))
    
    # Load and verify .env content
    from dotenv import load_dotenv
    load_dotenv("d:\\AAA_Model\\.env")
    
    env_vars = [
        'DATA_FOLDER',
        'TRAIN_DATA_PATH',
        'TEST_DATA_PATH',
        'OUTPUT_FOLDER'
    ]
    
    for var in env_vars:
        value = os.getenv(var)
        if value:
            print(f"✓ {var} = {value}")
        else:
            print(f"✗ {var} not set in .env")
            checks.append(False)
    
    return all(checks)

def check_project_structure():
    """Check directory structure"""
    print_header("2. PROJECT STRUCTURE CHECK")
    
    required_dirs = [
        "d:\\AAA_Model\\src",
        "d:\\AAA_Model\\models",
        "d:\\AAA_Model\\configs",
        "d:\\AAA_Model\\outputs",
        "d:\\AAA_Model\\notebooks",
        "d:\\AAA_Model\\DATA"
    ]
    
    checks = []
    for dir_path in required_dirs:
        if Path(dir_path).exists():
            print(f"✓ {dir_path}")
            checks.append(True)
        else:
            print(f"✗ {dir_path} (NOT FOUND)")
            checks.append(False)
    
    return all(checks)

def check_source_files():
    """Check Python source files"""
    print_header("3. SOURCE FILES CHECK")
    
    required_files = [
        ("d:\\AAA_Model\\src\\data_loader.py", "Data loader module"),
        ("d:\\AAA_Model\\src\\forecasters.py", "Forecasters module"),
        ("d:\\AAA_Model\\src\\autoscaling.py", "Autoscaling module"),
        ("d:\\AAA_Model\\src\\__init__.py", "Package init"),
        ("d:\\AAA_Model\\train.py", "Training script"),
        ("d:\\AAA_Model\\app.py", "API application"),
        ("d:\\AAA_Model\\dashboard.py", "Dashboard"),
    ]
    
    checks = []
    for file_path, description in required_files:
        checks.append(check_file_exists(file_path, description))
    
    return all(checks)

def check_dependencies():
    """Check Python dependencies"""
    print_header("4. DEPENDENCIES CHECK")
    
    essential_modules = [
        'pandas',
        'numpy',
        'sklearn',
        'xgboost',
        'tensorflow',
        'fastapi',
        'streamlit',
    ]
    
    optional_modules = [
        'prophet',
    ]
    
    print("\nEssential Dependencies:")
    essential_ok = all(
        check_module_import(m) for m in essential_modules
    )
    
    print("\nOptional Dependencies:")
    optional_ok = all(
        check_module_import(m) for m in optional_modules
    )
    
    return essential_ok

def check_data_files():
    """Check data files"""
    print_header("5. DATA FILES CHECK")
    
    data_files = [
        ("d:\\AAA_Model\\DATA\\train.txt", "Training data"),
        ("d:\\AAA_Model\\DATA\\test.txt", "Test data"),
    ]
    
    checks = []
    for file_path, description in data_files:
        exists = Path(file_path).exists()
        if exists:
            file_size = Path(file_path).stat().st_size / (1024*1024)  # MB
            print(f"✓ {description}: {file_path} ({file_size:.1f} MB)")
            checks.append(True)
        else:
            print(f"⚠ {description}: {file_path} (optional, can be generated)")
            checks.append(False)
    
    return True  # Data files are optional for demo

def check_imports():
    """Test importing project modules"""
    print_header("6. PROJECT IMPORTS CHECK")
    
    sys.path.insert(0, "d:\\AAA_Model")
    
    checks = []
    
    try:
        from src.data_loader import HTTPLogParser, TimeSeriesAggregator
        print("✓ Data loader imported successfully")
        checks.append(True)
    except Exception as e:
        print(f"✗ Data loader import failed: {e}")
        checks.append(False)
    
    try:
        from src.forecasters import create_forecaster
        print("✓ Forecasters imported successfully")
        checks.append(True)
    except Exception as e:
        print(f"✗ Forecasters import failed: {e}")
        checks.append(False)
    
    try:
        from src.autoscaling import ThresholdScalingPolicy
        print("✓ Autoscaling imported successfully")
        checks.append(True)
    except Exception as e:
        print(f"✗ Autoscaling import failed: {e}")
        checks.append(False)
    
    return all(checks)

def check_configuration():
    """Check configuration files"""
    print_header("7. CONFIGURATION CHECK")
    
    config_files = [
        ("d:\\AAA_Model\\configs\\default_config.yaml", "Default config"),
    ]
    
    checks = []
    for file_path, description in config_files:
        checks.append(check_file_exists(file_path, description))
    
    return all(checks)

def check_documentation():
    """Check documentation files"""
    print_header("8. DOCUMENTATION CHECK")
    
    doc_files = [
        ("d:\\AAA_Model\\README.md", "README"),
        ("d:\\AAA_Model\\QUICKSTART.md", "Quick Start Guide"),
        ("d:\\AAA_Model\\PROJECT_SUMMARY.md", "Project Summary"),
        ("d:\\AAA_Model\\requirements.txt", "Requirements"),
    ]
    
    checks = []
    for file_path, description in doc_files:
        checks.append(check_file_exists(file_path, description))
    
    return all(checks)

def print_summary(results):
    """Print final summary"""
    print_header("VERIFICATION SUMMARY")
    
    status_map = {
        'Environment': results.get('environment', False),
        'Project Structure': results.get('structure', False),
        'Source Files': results.get('sources', False),
        'Dependencies': results.get('dependencies', False),
        'Data Files': results.get('data', False),
        'Project Imports': results.get('imports', False),
        'Configuration': results.get('config', False),
        'Documentation': results.get('docs', False),
    }
    
    for check_name, status in status_map.items():
        symbol = "✓" if status else "✗"
        print(f"{symbol} {check_name}")
    
    all_passed = all(status_map.values())
    
    print("\n" + "="*60)
    if all_passed:
        print("✅ ALL CHECKS PASSED - PROJECT IS READY!")
        print("\nNext steps:")
        print("1. python train.py              (Run full pipeline)")
        print("2. streamlit run dashboard.py   (Start dashboard)")
        print("3. python -m uvicorn app:app    (Start API)")
    else:
        print("⚠️  SOME CHECKS FAILED - REVIEW ABOVE")
        print("\nFix:")
        print("1. Check .env configuration")
        print("2. Ensure data files exist in DATA/")
        print("3. Install missing dependencies: pip install -r requirements.txt")
    print("="*60 + "\n")
    
    return all_passed

def main():
    """Run all checks"""
    print("\n" + "="*60)
    print("  AUTOSCALING ANALYSIS PROJECT - VERIFICATION")
    print("="*60)
    
    results = {
        'environment': check_environment(),
        'structure': check_project_structure(),
        'sources': check_source_files(),
        'dependencies': check_dependencies(),
        'data': check_data_files(),
        'imports': check_imports(),
        'config': check_configuration(),
        'docs': check_documentation(),
    }
    
    all_ok = print_summary(results)
    
    return 0 if all_ok else 1

if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)
