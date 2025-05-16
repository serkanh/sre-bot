import json
from datetime import datetime
import functools
import logging


# Custom JSON encoder to handle datetime objects
class DateTimeEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, datetime):
            return obj.isoformat()
        return super().default(obj)


# Monkey patch json.dumps to use our custom encoder
original_dumps = json.dumps
json.dumps = functools.partial(original_dumps, cls=DateTimeEncoder)

# Log the patch
logging.info("Applied custom JSON encoder for datetime serialization")
