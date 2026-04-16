import json
from pathlib import Path
from datetime import datetime
from typing import Optional

class TemplateManager:
    def __init__(self):
        self.template_dir = Path("templates")
        self.template_dir.mkdir(exist_ok=True)
    
    def save_template(self, template_data: dict, name: Optional[str] = None) -> str:
        """Save server template to JSON file"""
        if name is None:
            name = template_data['name']
        
        # Sanitize filename
        safe_name = "".join(c for c in name if c.isalnum() or c in (' ', '-', '_')).strip()
        timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        filename = f"{safe_name}_{timestamp}.json"
        filepath = self.template_dir / filename
        
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(template_data, f, indent=2)
        
        return str(filepath)
    
    def load_template(self, filename: str) -> dict:
        """Load template from JSON file"""
        filepath = self.template_dir / filename
        
        if not filepath.exists():
            raise FileNotFoundError(f"Template not found: {filename}")
        
        with open(filepath, 'r', encoding='utf-8') as f:
            return json.load(f)
    
    def list_templates(self) -> list:
        """List all available templates"""
        return [f.name for f in self.template_dir.glob("*.json")]