import os, sys
_PORT = int(os.environ.get('PORT', 9100))
# Force Flask to bind to our assigned port
try:
    import flask as _flask
    _orig_run = _flask.Flask.run
    def _patched_run(self, host=None, port=None, debug=None, **kw):
        print(f"[MC] Running on http://localhost:{_PORT}", flush=True)
        _orig_run(self, host=host or '0.0.0.0', port=_PORT, debug=False, **kw)
    _flask.Flask.run = _patched_run
except ImportError:
    pass
# Run the actual entry point
import runpy
sys.argv[0] = r'C:\\Users\\Echo\\masterchief\\data\\uploads\\extracted\\module-system-v4\\app.py'
runpy.run_path(r'C:\\Users\\Echo\\masterchief\\data\\uploads\\extracted\\module-system-v4\\app.py', run_name='__main__')
