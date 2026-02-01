#!/usr/bin/env python3
"""
Simple RMM Agent - Linux Prerequisites Installer
Supports Debian/Ubuntu, RHEL/CentOS/Fedora, and Arch Linux
"""

import subprocess
import sys
import os
import platform
import shutil

def detect_distro():
    """Detect Linux distribution"""
    if os.path.exists('/etc/os-release'):
        with open('/etc/os-release') as f:
            lines = f.readlines()
            info = {}
            for line in lines:
                if '=' in line:
                    key, value = line.strip().split('=', 1)
                    info[key] = value.strip('"')
            return info.get('ID', 'unknown'), info.get('ID_LIKE', '')
    return 'unknown', ''

def install_system_deps():
    """Install system-level dependencies based on distribution"""
    distro, distro_like = detect_distro()
    
    print(f"Detected distribution: {distro}")
    
    # Check if we need sudo
    sudo = 'sudo' if os.geteuid() != 0 else ''
    
    try:
        if distro in ['debian', 'ubuntu'] or 'debian' in distro_like:
            print("Installing dependencies for Debian/Ubuntu...")
            deps = ['python3-pip', 'python3-venv', 'python3-dev', 'gcc', 'libjpeg-dev', 'zlib1g-dev']
            cmd = f"{sudo} apt update && {sudo} apt install -y {' '.join(deps)}"
            subprocess.run(cmd, shell=True, check=True)
            
        elif distro in ['rhel', 'centos', 'fedora', 'rocky', 'almalinux'] or 'rhel' in distro_like or 'fedora' in distro_like:
            print("Installing dependencies for RHEL/CentOS/Fedora...")
            
            # Check if dnf or yum
            if shutil.which('dnf'):
                pkg_manager = 'dnf'
            else:
                pkg_manager = 'yum'
            
            deps = ['python3-pip', 'python3-devel', 'gcc', 'libjpeg-devel', 'zlib-devel']
            
            # Enable EPEL for RHEL/CentOS if needed
            if distro in ['rhel', 'centos', 'rocky', 'almalinux']:
                subprocess.run(f"{sudo} {pkg_manager} install -y epel-release", shell=True, check=False)
            
            cmd = f"{sudo} {pkg_manager} install -y {' '.join(deps)}"
            subprocess.run(cmd, shell=True, check=True)
            
        elif distro in ['arch', 'manjaro', 'endeavouros'] or 'arch' in distro_like:
            print("Installing dependencies for Arch Linux...")
            deps = ['python-pip', 'python-virtualenv', 'gcc', 'libjpeg-turbo', 'zlib']
            cmd = f"{sudo} pacman -Sy --noconfirm {' '.join(deps)}"
            subprocess.run(cmd, shell=True, check=True)
            
        else:
            print(f"⚠️  Unknown distribution: {distro}")
            print("Please manually install: python3-pip, gcc, and development headers")
            return False
            
        print("✅ System dependencies installed")
        return True
        
    except subprocess.CalledProcessError as e:
        print(f"❌ Error installing system dependencies: {e}")
        return False
    except Exception as e:
        print(f"❌ Error: {e}")
        return False

def install_python_deps():
    """Install Python packages"""
    print("\nInstalling Python dependencies...")
    
    # Check if requirements.txt exists
    req_file = os.path.join(os.path.dirname(__file__), 'requirements.txt')
    
    if os.path.exists(req_file):
        print(f"Using {req_file}")
        cmd = [sys.executable, '-m', 'pip', 'install', '-r', req_file]
    else:
        print("Installing core packages...")
        packages = ['websockets', 'psutil', 'Pillow']
        cmd = [sys.executable, '-m', 'pip', 'install'] + packages
    
    try:
        subprocess.run(cmd, check=True)
        print("✅ Python dependencies installed")
        return True
    except subprocess.CalledProcessError as e:
        print(f"❌ Error installing Python dependencies: {e}")
        return False

def main():
    print("="*60)
    print("Simple RMM Agent - Prerequisites Installer")
    print("="*60)
    print()
    
    if platform.system() != 'Linux':
        print("This installer is for Linux only.")
        print("On Windows, run: pip install websockets psutil Pillow pyautogui")
        sys.exit(1)
    
    print("This script will install:")
    print("  - System dependencies (pip, gcc, development headers)")
    print("  - Python packages (websockets, psutil, Pillow)")
    print()
    
    response = input("Continue? (y/n): ")
    if response.lower() != 'y':
        print("Installation cancelled.")
        sys.exit(0)
    
    print()
    
    # Install system dependencies
    if install_system_deps():
        # Install Python dependencies
        if install_python_deps():
            print()
            print("="*60)
            print("✅ Installation complete!")
            print("="*60)
            print()
            print("You can now run the agent:")
            print("  python3 agent.py")
            print()
            print("Or with environment variables:")
            print("  RMM_SERVER=ws://your-server:3000 RMM_CUSTOMER=YourCompany python3 agent.py")
        else:
            print("\n❌ Failed to install Python dependencies")
            sys.exit(1)
    else:
        print("\n⚠️  Failed to install system dependencies")
        print("You may need to install them manually:")
        distro, _ = detect_distro()
        if 'arch' in distro:
            print("  sudo pacman -S python-pip python-virtualenv gcc")
        else:
            print("  sudo apt install python3-pip python3-venv gcc  # Debian/Ubuntu")
            print("  sudo dnf install python3-pip gcc  # Fedora")
            print("  sudo yum install python3-pip gcc  # RHEL/CentOS")
        sys.exit(1)

if __name__ == '__main__':
    main()
