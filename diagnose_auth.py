"""
Diagnostic script to test SharePoint authentication methods.
"""

import requests
from requests_ntlm import HttpNtlmAuth
import sys


def test_auth_methods(site_url, username, password, verify_ssl=True):
    """Test different authentication approaches."""

    print("=" * 70)
    print("SharePoint Authentication Diagnostics")
    print("=" * 70)
    print(f"\nSite URL: {site_url}")
    print(f"Username: {username}")
    print(f"SSL Verification: {verify_ssl}")

    if not verify_ssl:
        import urllib3
        urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

    api_url = f"{site_url}/_api/web"

    results = {}

    # Test 1: NTLM Authentication
    print("\n" + "=" * 70)
    print("Test 1: NTLM Authentication")
    print("=" * 70)
    try:
        session = requests.Session()
        session.auth = HttpNtlmAuth(username, password)
        session.headers.update({
            'Accept': 'application/json;odata=verbose'
        })

        response = session.get(api_url, verify=verify_ssl)

        print(f"Status Code: {response.status_code}")
        print(f"Headers: {dict(response.headers)}")

        if response.status_code == 200:
            print("✅ NTLM Authentication: SUCCESS")
            results['ntlm'] = 'SUCCESS'
            try:
                data = response.json()
                if 'd' in data:
                    print(f"Site Title: {data['d'].get('Title', 'N/A')}")
            except:
                pass
        else:
            print(f"❌ NTLM Authentication: FAILED ({response.status_code})")
            print(f"Response: {response.text[:200]}")
            results['ntlm'] = f'FAILED ({response.status_code})'

    except Exception as e:
        print(f"❌ NTLM Authentication: ERROR - {str(e)}")
        results['ntlm'] = f'ERROR: {str(e)}'

    # Test 2: Basic Authentication
    print("\n" + "=" * 70)
    print("Test 2: Basic Authentication")
    print("=" * 70)
    try:
        session = requests.Session()
        session.auth = (username, password)
        session.headers.update({
            'Accept': 'application/json;odata=verbose'
        })

        response = session.get(api_url, verify=verify_ssl)

        print(f"Status Code: {response.status_code}")

        if response.status_code == 200:
            print("✅ Basic Authentication: SUCCESS")
            results['basic'] = 'SUCCESS'
        else:
            print(f"❌ Basic Authentication: FAILED ({response.status_code})")
            print(f"Response: {response.text[:200]}")
            results['basic'] = f'FAILED ({response.status_code})'

    except Exception as e:
        print(f"❌ Basic Authentication: ERROR - {str(e)}")
        results['basic'] = f'ERROR: {str(e)}'

    # Test 3: No Authentication (test if site allows anonymous)
    print("\n" + "=" * 70)
    print("Test 3: Anonymous Access")
    print("=" * 70)
    try:
        response = requests.get(api_url, verify=verify_ssl)
        print(f"Status Code: {response.status_code}")

        if response.status_code == 200:
            print("✅ Anonymous Access: ALLOWED")
            results['anonymous'] = 'ALLOWED'
        else:
            print(f"❌ Anonymous Access: DENIED ({response.status_code})")
            results['anonymous'] = 'DENIED'

    except Exception as e:
        print(f"❌ Anonymous Access: ERROR - {str(e)}")
        results['anonymous'] = f'ERROR: {str(e)}'

    # Test 4: Check if SSPI/Negotiate is available (Windows only)
    print("\n" + "=" * 70)
    print("Test 4: Windows SSPI (Current User)")
    print("=" * 70)
    try:
        from requests_negotiate_sspi import HttpNegotiateAuth

        session = requests.Session()
        session.auth = HttpNegotiateAuth()
        session.headers.update({
            'Accept': 'application/json;odata=verbose'
        })

        response = session.get(api_url, verify=verify_ssl)

        print(f"Status Code: {response.status_code}")

        if response.status_code == 200:
            print("✅ Windows SSPI: SUCCESS")
            results['sspi'] = 'SUCCESS'
        else:
            print(f"❌ Windows SSPI: FAILED ({response.status_code})")
            results['sspi'] = f'FAILED ({response.status_code})'

    except ImportError:
        print("⚠️  requests-negotiate-sspi not installed (Windows only)")
        print("   Install with: pip install requests-negotiate-sspi")
        results['sspi'] = 'NOT AVAILABLE'
    except Exception as e:
        print(f"❌ Windows SSPI: ERROR - {str(e)}")
        results['sspi'] = f'ERROR: {str(e)}'

    # Summary
    print("\n" + "=" * 70)
    print("SUMMARY")
    print("=" * 70)

    for method, result in results.items():
        status_icon = "✅" if "SUCCESS" in result else "❌"
        print(f"{status_icon} {method.upper()}: {result}")

    # Recommendations
    print("\n" + "=" * 70)
    print("RECOMMENDATIONS")
    print("=" * 70)

    if any("SUCCESS" in r for r in results.values()):
        successful_methods = [m for m, r in results.items() if "SUCCESS" in r]
        print(f"\n✅ Working authentication methods: {', '.join(successful_methods)}")
        print(f"\nUse one of these methods in the application:")
        for method in successful_methods:
            if method == 'sspi':
                print(f"  - Windows SSPI (uses current Windows login)")
            else:
                print(f"  - {method.upper()}")
    else:
        print("\n❌ No authentication methods succeeded. Possible issues:")
        print("  1. Incorrect username/password")
        print("  2. Username format incorrect (try: DOMAIN\\user or user@domain.com)")
        print("  3. Account doesn't have access to SharePoint site")
        print("  4. REST API is disabled on the SharePoint site")
        print("  5. Additional authentication configuration required")
        print("\n💡 Try different username formats:")
        print(f"  - {username.split('@')[0] if '@' in username else username}")
        print(f"  - DOMAIN\\{username.split('@')[0] if '@' in username else username}")
        print(f"  - {username}@yourdomain.com")

    return results


if __name__ == "__main__":
    print("SharePoint Authentication Diagnostics Tool")
    print()

    site_url = input("SharePoint Site URL: ").strip()
    username = input("Username: ").strip()

    # Hide password input
    import getpass
    password = getpass.getpass("Password: ")

    verify_ssl_input = input("Verify SSL? (y/n) [y]: ").strip().lower()
    verify_ssl = verify_ssl_input != 'n'

    test_auth_methods(site_url, username, password, verify_ssl)
