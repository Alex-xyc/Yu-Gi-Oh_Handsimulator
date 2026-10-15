"""Start the web version of the Yu-Gi-Oh! Hand Simulator (API + built front end).

    python src/web.py                     http://127.0.0.1:8000
    HOST=0.0.0.0 PORT=80 python src/web.py

Build the front end first (cd web && npm install && npm run build); without it only
the API under /api is served.

Copyright (c) 2026 Alex-xyc
"""

import os

import uvicorn

if __name__ == "__main__":
    # Behind a proxy, YGO_PROXY_HOPS says how many X-Forwarded-For entries to trust (see web/security.py)
    uvicorn.run("ygo_calc.web.server:app", host=os.environ.get("HOST", "127.0.0.1"),
                port=int(os.environ.get("PORT", "8000")), app_dir=os.path.dirname(os.path.abspath(__file__)),
                server_header=False)
