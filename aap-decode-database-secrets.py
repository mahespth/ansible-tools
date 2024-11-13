"""
  Steve Maher, Decode database secrets, this is for a backup / validation, do not deploy this to prod.

"""

import psycopg2
import configparser
from cryptography.fernet import Fernet
import json
import os

# Define the paths to the necessary files
INVENTORY_PATH = '/etc/tower/inventory'
SECRET_KEY_PATH = '/etc/tower/SECRET_KEY'

def load_db_config(inventory_path):
    """Load database configuration from Ansible inventory file."""
    config = configparser.ConfigParser()
    config.read(inventory_path)

    # Ensure the [database] section is present
    if 'database' not in config:
        raise ValueError("The inventory file does not contain a [database] section.")

    # Extract database connection details
    db_config = {
        'host': config.get('database', 'pg_host'),
        'port': config.get('database', 'p_port'),
        'database': config.get('database', 'pg_database'),
        'user': config.get('database', 'pg_username'),
        'password': config.get('database', 'pg_password')
    }
    return db_config

def get_secret_key(secret_key_path):
    """Read the secret key from the file."""
    with open(secret_key_path, 'r') as f:
        return f.read().strip()

def decrypt_data(encrypted_data, secret_key):
    """Decrypt the given encrypted data using the secret key."""
    fernet = Fernet(secret_key)
    return fernet.decrypt(encrypted_data.encode()).decode()

def fetch_encrypted_credentials(db_config, secret_key):
    """Fetch and decrypt credentials from the PostgreSQL database."""
    try:
        # Connect to the PostgreSQL database using the loaded config
        conn = psycopg2.connect(
            host=db_config['host'],
            database=db_config['database'],
            user=db_config['user'],
            password=db_config['password'],
            port=db_config['port']
        )
        cursor = conn.cursor()

        # Query to select encrypted credentials
        cursor.execute("SELECT id, name, inputs FROM main_credential;")
        rows = cursor.fetchall()

        # Decrypt and print the credentials
        for row in rows:
            credential_id, name, inputs = row
            try:
                inputs_json = json.loads(inputs)

                # Decrypt fields if they are encrypted
                if 'password' in inputs_json and inputs_json['password'].startswith('$encrypted$'):
                    encrypted_password = inputs_json['password'].replace('$encrypted$', '')
                    decrypted_password = decrypt_data(encrypted_password, secret_key)
                    inputs_json['password'] = decrypted_password

                print(f"ID: {credential_id}, Name: {name}, Decrypted Inputs: {inputs_json}")
            except Exception as e:
                print(f"Failed to decrypt credential {name}: {e}")

        cursor.close()
        conn.close()
    except Exception as e:
        print(f"Database connection failed: {e}")

if __name__ == "__main__":
    try:
        # Load database configuration from the inventory file
        db_config = load_db_config(INVENTORY_PATH)

        # Get the encryption secret key
        secret_key = get_secret_key(SECRET_KEY_PATH)

        # Fetch and decrypt credentials
        fetch_encrypted_credentials(db_config, secret_key)
    except Exception as e:
        print(f"Error: {e}")
