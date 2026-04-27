from tools.db import get_engine
from sqlalchemy import text
engine = get_engine()
with engine.connect() as conn:
    try:
        res = conn.execute(text("SELECT ST_AsText(ST_LineFromEncodedPolyline('_p~iH_c}hA_n`@_d|@', 5))")).fetchone()
        print("Success:", res)
    except Exception as e:
        print("Error:", e)
