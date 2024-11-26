import hvac

def get_vault_password():
    # Connect to Vault
    client = hvac.Client(url='https://vault-server.aixtreme.org:8200', token='{{ vault_token }}')
    
    # Retrieve the database password
    secret = client.secrets.kv.v2.read_secret_version(path='database/awx')
    return secret['data']['data']['password']

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': 'awx',
        'USER': 'awx_user',
        'PASSWORD': get_vault_password(),
        'HOST': 'pgsql.aixtreme.org',
        'PORT': '5432',
    }
}
