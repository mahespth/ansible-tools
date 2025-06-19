#!/usr/bin/env python3
"""
exercise_get_group_dns.py  –  reproduce AAP’s group-lookup step
----------------------------------------------------------------
• binds with your service account
• finds <username>'s DN
• calls _LDAPUserGroups.get_group_dns()
• shows the list of group DNs (or why it failed)

Requires:
  * python3-django-auth-ldap-4.0.0-2 (Red Hat RPM)
  * python3-django
"""
import os, sys, ldap, django
from django.conf import settings
from django_auth_ldap.config import LDAPSearch, GroupOfNamesType
from django_auth_ldap.backend import LDAPBackend

###############################################################################
#  ▶▶  FILL IN YOUR OWN VALUES  ◀◀
###############################################################################
LDAP_URI          = "ldap://ad.example.com"
BIND_DN           = "CN=svc_ldap,OU=Service Accounts,DC=example,DC=com"
BIND_PASSWORD     = "svc_password"

BASE_DN           = "DC=example,DC=com"
GROUP_BASE_DN     = BASE_DN                     # keep it simple
USERNAME_ATTR     = "sAMAccountName"            # or userPrincipalName

###############################################################################
#  ───  DJANGO BOOTSTRAP (no settings.py on disk required)  ───
###############################################################################
settings.configure(
    SECRET_KEY="dummy",
    INSTALLED_APPS=[
        "django.contrib.auth",
        "django.contrib.contenttypes",
    ],
    # 1️⃣ LDAP connection & search settings
    AUTH_LDAP_SERVER_URI = LDAP_URI,
    AUTH_LDAP_BIND_DN    = BIND_DN,
    AUTH_LDAP_BIND_PASSWORD = BIND_PASSWORD,
    AUTH_LDAP_CONNECTION_OPTIONS = {
        ldap.OPT_PROTOCOL_VERSION: 3,
        ldap.OPT_REFERRALS: 0,            # the fix you found earlier
    },
    AUTH_LDAP_USER_SEARCH = LDAPSearch(
        BASE_DN,
        ldap.SCOPE_SUBTREE,
        f"({USERNAME_ATTR}=%(user)s)"
    ),
    # 2️⃣ Group discovery
    AUTH_LDAP_GROUP_SEARCH = LDAPSearch(
        GROUP_BASE_DN,
        ldap.SCOPE_SUBTREE,
        "(objectClass=group)"
    ),
    AUTH_LDAP_GROUP_TYPE = GroupOfNamesType(),   # AD behaves like groupOfNames
    AUTH_LDAP_FIND_GROUP_PERMS = False,          # we only need the list, not perms
)
django.setup()

###############################################################################
#  ───  DRIVE THE SAME CALL AAP USES  ───
###############################################################################
def get_user_group_dns(username: str, password: str):
    backend = LDAPBackend()                      # stock backend from the RPM
    user = backend.authenticate(
        request=None,
        username=username,
        password=password
    )
    if user is None:
        raise RuntimeError("Invalid credentials or user not found")

    # django-auth-ldap attaches an _LDAPUser proxy to the Django user object.
    # group_dns property → _LDAPUserGroups → get_group_dns()
    return user.ldap_user.group_dns              # ‼ calls get_group_dns inside

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: exercise_get_group_dns.py <username>")
        sys.exit(1)

    uname = sys.argv[1]
    pword = os.environ.get("AD_TEST_PASSWORD") or input("Password: ")

    try:
        groups = get_user_group_dns(uname, pword)
        print(f"\n✅  {uname} is a member of {len(groups)} groups:")
        for dn in groups:
            print("   -", dn)
    except Exception as e:
        print("\n❌  get_group_dns blew up:")
        raise
