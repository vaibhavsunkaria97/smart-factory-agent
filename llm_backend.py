import urllib.request
import json
import os

class Reasoner:
    def __init__(self, prefer=None):
        self.backend = self._detect_backend()

    def _detect_backend(self):
        try:
            urllib.request.urlopen('http://localhost:11434')
            return 'ollama'
        except Exception:
            if 'GROQ_API_KEY' in os.environ:
                return 'groq'
            return 'offline'

    def explain(self, detection):
        try:
            if self.backend == 'ollama':
                return self._explain_ollama(detection)
            elif self.backend == 'groq':
                return self._explain_groq(detection)
        except Exception:
            pass
        return self._explain_offline(detection)

    def _explain_ollama(self, detection):
        prompt = {
            'prompt': 'Explain the detection with diagnosis and action',
            'detection': detection.__dict__
        }
        req = urllib.request.Request('http://localhost:11434', data=json.dumps(prompt).encode())
        with urllib.request.urlopen(req) as f:
            response = json.loads(f.read())
            return response

    def _explain_groq(self, detection):
        # implement groq api call
        pass

    def _explain_offline(self, detection):
        knowledge_base = {
            ('temp', 'high'): {'diagnosis': 'coolant flow restriction / fan degradation', 'action': 'check coolant flow and fan'},
            ('pressure', 'high'): {'diagnosis': 'blocked outlet / stuck relief valve', 'action': 'check outlet and relief valve'},
            ('vibration', 'high'): {'diagnosis': 'bearing wear / shaft misalignment', 'action': 'check bearing and shaft alignment'},
            ('none', 'none'): {'diagnosis': 'anomaly detected', 'action': 'investigate further'}
        }
        breaches = detection.breached
        if breaches:
            key = (breaches[0][0], breaches[0][1])
            return knowledge_base.get(key, knowledge_base[('none', 'none')])
        return knowledge_base[('none', 'none')]
