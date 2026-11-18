import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import app  # expose l'app Flask pour Vercel

# Handler requis par le runtime Python de Vercel
def handler(request):
    return app(request.environ, lambda *args: None)
