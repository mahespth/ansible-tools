#!/usr/bin/env python3
"""
ldap_login_test.py – verify an AD username/password using django-auth-ldap 4.0.0-2
"""
import getpass, sys, ldap
from django_auth_ldap.config import LDAPSearch

# ─── Site-specific knobs ──────────────────────────────────────────────────────
LDAP_URI             = "ldap://ad.example.com"
BIND_DN              = "CN=svc_ldap,OU=Service Accounts,DC=example,DC=com"
BIND_PASSWORD        = "svc_password"               # or read from vault/env
BASE_DN              = "DC=example,DC=com"
AD_USERNAME_ATTR     = "sAMAccountName"             # or "userPrincipalName"
# ───────────────────────────────────────────────────────────────────────────────

user_search = LDAPSearch(
    BASE_DN,
    ldap.SCOPE_SUBTREE,
    f"({AD_USERNAME_ATTR}=%(user)s)"
)

def test_login(username: str, password: str) -> bool:
    """Return True if (username,password) are valid AD creds, else False."""
    # 1️⃣ Bind as service account
    svc = ldap.initialize(LDAP_URI)
    svc.set_option(ldap.OPT_PROTOCOL_VERSION, 3)
    svc.set_option(ldap.OPT_REFERRALS, 0)
    svc.simple_bind_s(BIND_DN, BIND_PASSWORD)

    # 2️⃣ Find the user’s DN
    results = user_search.execute(svc, {"user": username})
    svc.unbind()                         # done with the service bind

    if not results:
        print(f"❌  User {username!r} not found under {BASE_DN}")
        return False

    user_dn = results[0][0]              # DN of first match
    # 3️⃣ Attempt to bind as that user
    try:
        user_conn = ldap.initialize(LDAP_URI)
        user_conn.set_option(ldap.OPT_PROTOCOL_VERSION, 3)
        user_conn.set_option(ldap.OPT_REFERRALS, 0)
        user_conn.simple_bind_s(user_dn, password)
        user_conn.unbind()
        print(f"✅  Credentials for {username} are valid.")
        return True
    except ldap.INVALID_CREDENTIALS:
        print(f"❌  Invalid password for {username}.")
        return False
    except ldap.LDAPError as e:
        print(f"⚠️  LDAP error while binding as {username}: {e}")
        return False

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: ldap_login_test.py <username>")
        sys.exit(1)

    user = sys.argv[1]
    pw = getpass.getpass(f"Password for {user}: ")
    ok = test_login(user, pw)
    sys.exit(0 if ok else 2)
git