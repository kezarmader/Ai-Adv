from core.ports.outbound import URLGeneratorPort

class URLGeneratorAdapter(URLGeneratorPort):
    """Adapter for generating URLs"""
    
    def generate_image_url(self, filename: str, host: str) -> str:
        """Generate external image URL"""
        return f"http://{host}/download/{filename}"
