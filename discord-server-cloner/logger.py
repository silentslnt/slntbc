import json
from datetime import datetime
from pathlib import Path

class CloneLogger:
    def __init__(self, source_name: str, dest_name: str):
        self.source = source_name
        self.dest = dest_name
        self.start_time = None
        self.end_time = None
        self.steps = []
        self.actions = []
        self.errors = []
        
        # Create logs directory
        Path("logs").mkdir(exist_ok=True)
    
    def log_start(self):
        self.start_time = datetime.utcnow()
        self.steps.append({
            'event': 'Clone Started',
            'timestamp': self.start_time.isoformat(),
            'source': self.source,
            'destination': self.dest
        })
    
    def log_step(self, step_name: str):
        self.steps.append({
            'event': step_name,
            'timestamp': datetime.utcnow().isoformat()
        })
    
    def log_action(self, action: str):
        self.actions.append({
            'action': action,
            'timestamp': datetime.utcnow().isoformat()
        })
    
    def log_error(self, error: str):
        self.errors.append({
            'error': error,
            'timestamp': datetime.utcnow().isoformat()
        })
        print(f"❌ {error}")
    
    def log_complete(self):
        self.end_time = datetime.utcnow()
        duration = (self.end_time - self.start_time).total_seconds()
        self.steps.append({
            'event': 'Clone Completed',
            'timestamp': self.end_time.isoformat(),
            'duration_seconds': duration
        })
    
    def save(self):
        """Save audit log to JSON file"""
        timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        filename = f"logs/clone_{self.source}_{timestamp}.json"
        
        log_data = {
            'source_server': self.source,
            'destination_server': self.dest,
            'start_time': self.start_time.isoformat() if self.start_time else None,
            'end_time': self.end_time.isoformat() if self.end_time else None,
            'duration_seconds': (self.end_time - self.start_time).total_seconds() if self.end_time and self.start_time else None,
            'steps': self.steps,
            'actions': self.actions,
            'errors': self.errors,
            'total_errors': len(self.errors)
        }
        
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(log_data, f, indent=2)
        
        print(f"📝 Audit log saved: {filename}")
        return filename