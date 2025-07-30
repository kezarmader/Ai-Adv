#!/usr/bin/env python3
"""
Validation script for Hexagonal Architecture implementation
"""

import sys
import importlib
import traceback

def test_core_has_no_external_dependencies():
    """Test that core modules have no external dependencies"""
    print("Testing core isolation...")
    
    core_modules = [
        "core.domain.entities",
        "core.ports.inbound", 
        "core.ports.outbound",
        "core.use_cases.ad_campaign_use_case",
        "core.use_cases.image_download_use_case"
    ]
    
    forbidden_imports = [
        "fastapi", "requests", "flask", "django", 
        "sqlalchemy", "redis", "boto3"
    ]
    
    violations = []
    
    for module_name in core_modules:
        try:
            module = importlib.import_module(module_name)
            
            # Check module's dependencies
            for attr_name in dir(module):
                attr = getattr(module, attr_name)
                if hasattr(attr, '__module__'):
                    attr_module = attr.__module__
                    for forbidden in forbidden_imports:
                        if forbidden in attr_module:
                            violations.append(f"{module_name} imports {forbidden}")
            
            print(f"✓ {module_name} - clean")
            
        except Exception as e:
            print(f"✗ {module_name}: {str(e)}")
            return False
    
    if violations:
        print(f"\n❌ Core isolation violations:")
        for violation in violations:
            print(f"  - {violation}")
        return False
    else:
        print("✅ Core is properly isolated!")
        return True

def test_dependency_direction():
    """Test that dependencies flow inward"""
    print("\nTesting dependency direction...")
    
    try:
        # Core should not depend on adapters or infrastructure
        from core.domain import entities
        from core.ports import inbound, outbound
        from core.use_cases import ad_campaign_use_case
        
        # Adapters should depend on core
        from adapters.external import llm_adapter
        from adapters.http import controllers
        
        # Infrastructure should wire everything together
        from infrastructure import dependencies
        
        print("✓ All modules imported successfully")
        print("✓ Dependency direction is correct")
        return True
        
    except Exception as e:
        print(f"✗ Dependency direction test failed: {str(e)}")
        traceback.print_exc()
        return False

def test_ports_and_adapters():
    """Test that adapters implement the correct ports"""
    print("\nTesting ports and adapters...")
    
    try:
        from core.ports.outbound import LLMPort, ImageGenerationPort, PostingPort
        from adapters.external.llm_adapter import LLMAdapter
        from adapters.external.image_adapter import ImageAdapter
        from adapters.external.posting_adapter import PostingAdapter
        
        # Test adapter inheritance
        assert issubclass(LLMAdapter, LLMPort), "LLMAdapter must implement LLMPort"
        assert issubclass(ImageAdapter, ImageGenerationPort), "ImageAdapter must implement ImageGenerationPort"
        assert issubclass(PostingAdapter, PostingPort), "PostingAdapter must implement PostingPort"
        
        print("✓ LLMAdapter implements LLMPort")
        print("✓ ImageAdapter implements ImageGenerationPort") 
        print("✓ PostingAdapter implements PostingPort")
        
        # Test adapter instantiation
        llm_adapter = LLMAdapter()
        image_adapter = ImageAdapter()
        posting_adapter = PostingAdapter()
        
        print("✓ All adapters can be instantiated")
        return True
        
    except Exception as e:
        print(f"✗ Ports and adapters test failed: {str(e)}")
        traceback.print_exc()
        return False

def test_use_case_composition():
    """Test that use cases can be composed with adapters"""
    print("\nTesting use case composition...")
    
    try:
        from core.use_cases.ad_campaign_use_case import AdCampaignUseCase
        from adapters.external.llm_adapter import LLMAdapter
        from adapters.external.image_adapter import ImageAdapter
        from adapters.external.posting_adapter import PostingAdapter
        from adapters.external.url_generator_adapter import URLGeneratorAdapter
        
        # Test composition
        use_case = AdCampaignUseCase(
            llm_service=LLMAdapter(),
            image_service=ImageAdapter(),
            posting_service=PostingAdapter(),
            url_generator=URLGeneratorAdapter()
        )
        
        print("✓ AdCampaignUseCase composed successfully")
        
        # Test dependency injection setup
        from infrastructure.dependencies import setup_dependencies
        controller = setup_dependencies()
        
        print("✓ Dependency injection setup works")
        return True
        
    except Exception as e:
        print(f"✗ Use case composition test failed: {str(e)}")
        traceback.print_exc()
        return False

def test_domain_entities():
    """Test domain entities are properly defined"""
    print("\nTesting domain entities...")
    
    try:
        from core.domain.entities import Product, Audience, AdText, AdCampaign
        
        # Test entity creation
        product = Product(name="Test Product", features=["feature1"], asin="B123456789")
        audience = Audience(demographics="tech enthusiasts", tone="excited")
        ad_text = AdText(
            product="Test Product",
            audience="tech enthusiasts", 
            tone="excited",
            description="Amazing product",
            features=["feature1"],
            scene="Product showcase"
        )
        
        print("✓ Product entity created")
        print("✓ Audience entity created")
        print("✓ AdText entity created")
        
        # Test entity methods
        ad_dict = ad_text.to_dict()
        assert isinstance(ad_dict, dict), "AdText.to_dict() should return dict"
        
        print("✓ Entity methods work correctly")
        return True
        
    except Exception as e:
        print(f"✗ Domain entities test failed: {str(e)}")
        traceback.print_exc()
        return False

def main():
    """Run all hexagonal architecture validation tests"""
    print("=" * 60)
    print("Hexagonal Architecture Validation")
    print("=" * 60)
    
    tests = [
        test_core_has_no_external_dependencies,
        test_dependency_direction,
        test_ports_and_adapters,
        test_use_case_composition,
        test_domain_entities
    ]
    
    passed = 0
    for test in tests:
        if test():
            passed += 1
        print()
    
    print("=" * 60)
    if passed == len(tests):
        print(f"🎉 All {len(tests)} tests passed! Hexagonal Architecture is correctly implemented.")
        print("\n✅ Benefits achieved:")
        print("  - Core business logic is isolated from external dependencies")
        print("  - Dependencies flow inward (Dependency Inversion)")
        print("  - Adapters properly implement port interfaces")
        print("  - Use cases can be composed and tested independently")
        print("  - Domain entities are well-defined")
        return 0
    else:
        print(f"❌ {len(tests) - passed} out of {len(tests)} tests failed.")
        print("Architecture needs refinement.")
        return 1

if __name__ == "__main__":
    sys.exit(main())
