
import base64

"""
    Steve Maher: url safe b64 encoding due to the ansible builtin not correctly doing this.
"""

def urlsafe_b64encode(value):
    if isinstance(value, str):
        value = value.encode('utf-8')
    return base64.urlsafe_b64encode(value).decode('utf-8')

def urlsafe_b64decode(value):
    if isinstance(value, str):
        value = value.encode('ascii')

    value += b"=" * (-len(value) % 4)

    return base64.b64decode(value)

class FilterModule(object):
    def filters(self):
        return {
            'urlsafe_b64encode': urlsafe_b64encode,
            'urlsafe_b64decode': urlsafe_b64decode
        }
