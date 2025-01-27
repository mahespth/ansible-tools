Overview of Network Communication Requirements
Here’s a breakdown of the required communication between the components:

Source Component	Destination Component	Port	Protocol	Description
Automation Controller	Automation Hub	443	TCP	Access to collections and content
Automation Controller	EDA	8052	TCP	Event-Driven Ansible API communication
Automation Controller	Platform Gateway	443	TCP	HTTPS access to gateway
Automation Hub	Automation Controller	5432	TCP	Database communication (PostgreSQL)
Automation Hub	Platform Gateway	443	TCP	HTTPS access to gateway
EDA	Automation Controller	8053	TCP	WebSocket communication for event-driven updates
EDA	Redis (internal)	6379	TCP	Redis message queue
Platform Gateway	Automation Controller	8052	TCP	Proxy API communication


Debug: Edit settings.py and restart ` systemctl restart automation-gateway.target`

/usr/lib/python3.11/site-packages/aap_gateway_api/settings.py

```
# User our own user model
AUTH_USER_MODEL = 'aap_gateway_api.User'

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = False

LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'filters': {
        'request_id_filter': {
            '()': 'ansible_base.lib.logging.filters.RequestIdFilter',
        },
    },
    .......
    'loggers': {
        'django': {
            'handlers': ['console', 'file'],
            'level': 'WARNING',
        },
        'django.request': {
            'handlers': ['console', 'file'],
            'level': 'WARNING',
        },
        "django_auth_ldap": {
            'handlers': ['console', 'file'],
            'level': 'DEBUG',
            'propagate': True,
        },
      .......
```




