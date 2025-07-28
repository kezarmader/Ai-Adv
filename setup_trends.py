#!/usr/bin/env python3
"""
Setup script for Secure Trends Integration
Checks dependencies, creates configuration files, and validates setup
"""
import os
import sys
import subprocess
import shutil
from pathlib import Path

def check_python_version():
    """Check if Python version is compatible"""
    print("🐍 Checking Python version...")
    version = sys.version_info
    if version.major < 3 or (version.major == 3 and version.minor < 8):
        print("❌ Python 3.8+ required")
        return False
    print(f"✅ Python {version.major}.{version.minor}.{version.micro}")
    return True

def check_dependencies():
    """Check if required dependencies are available"""
    print("\n📦 Checking dependencies...")
    
    required_packages = {
        'requests': 'requests',
        'beautifulsoup4': 'bs4',
        'aiohttp': 'aiohttp',
        'fastapi': 'fastapi',
        'pytrends': 'pytrends'
    }
    
    missing_packages = []
    
    for package_name, import_name in required_packages.items():
        try:
            __import__(import_name)
            print(f"✅ {package_name}")
        except ImportError:
            print(f"❌ {package_name} - Missing")
            missing_packages.append(package_name)
    
    if missing_packages:
        print(f"\n📥 Install missing packages with:")
        print(f"pip install {' '.join(missing_packages)}")
        return False
    
    return True

def create_config_files():
    """Create configuration files"""
    print("\n📄 Creating configuration files...")
    
    # Create .env.example
    env_example_content = """# Secure Trends Integration Environment Variables

## Optional API Keys (system works without these):

# Google Trends API (if you have official access)
GOOGLE_TRENDS_API_KEY=your_google_trends_api_key_here

# Twitter API v2 (for Twitter trends)
TWITTER_BEARER_TOKEN=your_twitter_bearer_token_here

# Reddit API (for Reddit trending topics)
REDDIT_CLIENT_ID=your_reddit_client_id_here
REDDIT_CLIENT_SECRET=your_reddit_client_secret_here

## Configuration (optional, uses defaults):

# Rate limiting
TRENDS_MIN_REQUEST_INTERVAL=60  # seconds between requests
TRENDS_CACHE_DURATION=900       # cache duration in seconds (15 minutes)
TRENDS_MAX_RETRIES=3            # max retries per source
TRENDS_REQUEST_TIMEOUT=15       # request timeout in seconds

# Content filtering
TRENDS_MAX_LENGTH=150           # maximum trend title length
TRENDS_MAX_PER_SOURCE=10        # maximum trends per source

## Security Notes:
# - Never commit .env files to version control
# - Use secure methods to deploy environment variables in production
# - API keys should have minimal required permissions
# - Monitor API usage to stay within rate limits
"""
    
    try:
        with open('.env.example', 'w') as f:
            f.write(env_example_content)
        print("✅ Created .env.example")
    except Exception as e:
        print(f"❌ Failed to create .env.example: {e}")
        return False
    
    # Create trends_config.py if it doesn't exist
    if not os.path.exists('orchestrator/trends_config.py'):
        print("❌ trends_config.py not found in orchestrator/")
        return False
    else:
        print("✅ trends_config.py exists")
    
    return True

def test_basic_functionality():
    """Test basic functionality without external dependencies"""
    print("\n🧪 Testing basic functionality...")
    
    try:
        # Test configuration loading
        sys.path.append('orchestrator')
        from trends_config import config
        print(f"✅ Configuration loaded")
        print(f"   Min interval: {config.min_request_interval}s")
        print(f"   Cache duration: {config.cache_duration//60}min")
        
        # Test trends processor
        from trends_integration import SecureTrendsProcessor
        processor = SecureTrendsProcessor()
        print("✅ Trends processor initialized")
        
        # Test fallback topics
        fallback_trends = processor._get_fallback_trends()
        print(f"✅ Fallback trends: {len(fallback_trends)} topics")
        
        # Test story creation
        story = processor.create_spiced_story(fallback_trends)
        print(f"✅ Story generation: {len(story['spiced_story'])} chars")
        
        return True
        
    except Exception as e:
        print(f"❌ Basic functionality test failed: {e}")
        return False

def check_docker_setup():
    """Check Docker setup for deployment"""
    print("\n🐳 Checking Docker setup...")
    
    try:
        # Check if Docker is available
        result = subprocess.run(['docker', '--version'], 
                              capture_output=True, text=True, timeout=10)
        if result.returncode == 0:
            print("✅ Docker available")
        else:
            print("❌ Docker not available")
            return False
        
        # Check if docker-compose is available
        result = subprocess.run(['docker-compose', '--version'], 
                              capture_output=True, text=True, timeout=10)
        if result.returncode == 0:
            print("✅ Docker Compose available")
        else:
            print("❌ Docker Compose not available")
            return False
        
        # Check if docker-compose.yml exists
        if os.path.exists('docker-compose.yml'):
            print("✅ docker-compose.yml found")
        else:
            print("❌ docker-compose.yml not found")
            return False
        
        return True
        
    except Exception as e:
        print(f"❌ Docker check failed: {e}")
        return False

def show_next_steps(all_checks_passed):
    """Show next steps based on setup results"""
    print("\n" + "=" * 60)
    print("📋 SETUP SUMMARY")
    print("=" * 60)
    
    if all_checks_passed:
        print("🎉 Setup completed successfully!")
        print("\n📝 Next steps:")
        print("1. 🚀 Start services: docker-compose up --build")
        print("2. 🧪 Run tests: python test_trending_feature.py")
        print("3. 🔍 Check trends: curl http://localhost:8000/trends")
        print("4. 📊 Debug info: curl http://localhost:8000/trends/debug")
        
        print("\n💡 Optional enhancements:")
        print("• Copy .env.example to .env and add API keys for better reliability")
        print("• Monitor logs with: docker-compose logs -f orchestrator")
        print("• Test trending ads with: POST http://localhost:8000/run/trending")
        
    else:
        print("⚠️  Setup completed with issues")
        print("\n🔧 Required actions:")
        print("• Install missing dependencies")
        print("• Fix configuration issues")
        print("• Ensure Docker is properly installed")
        
    print(f"\n📚 Documentation:")
    print("• TRENDING_FEATURE.md - Feature documentation")
    print("• test_trending_feature.py - Comprehensive tests")
    print("• .env.example - Configuration template")

def main():
    """Main setup function"""
    print("🎯 AI Advertisement Generator - Secure Trends Setup")
    print("📅 Setting up secure multi-source trends integration")
    print("=" * 60)
    
    checks = []
    
    # Run all checks
    checks.append(check_python_version())
    checks.append(check_dependencies())
    checks.append(create_config_files())
    checks.append(test_basic_functionality())
    checks.append(check_docker_setup())
    
    all_passed = all(checks)
    
    # Show results
    show_next_steps(all_passed)
    
    return 0 if all_passed else 1

if __name__ == "__main__":
    sys.exit(main())
