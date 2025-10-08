"""
Test different SharePoint URL formats to find the correct site URL.
"""

from sharepoint_client import SharePointClient
import sys


def test_url_variations(base_url, auth_method="integrated", username=None, password=None, verify_ssl=False):
    """
    Test different URL formats to find the correct SharePoint site endpoint.
    """

    print("=" * 70)
    print("SharePoint URL Format Tester")
    print("=" * 70)

    if not verify_ssl:
        import urllib3
        urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

    # Parse the URL to extract parts
    parts = base_url.rstrip('/').split('/')

    # Generate variations
    variations = [base_url]

    # Try to identify site collection URL
    if '/sites/' in base_url:
        # Find the site collection (first part after /sites/)
        sites_index = None
        for i, part in enumerate(parts):
            if part == 'sites':
                sites_index = i
                break

        if sites_index and len(parts) > sites_index + 1:
            # Try site collection URL
            site_collection = '/'.join(parts[:sites_index + 2])
            variations.append(site_collection)

            # Try with additional subsite levels
            for i in range(sites_index + 2, len(parts)):
                subsite = '/'.join(parts[:i + 1])
                variations.append(subsite)

    # Remove duplicates while preserving order
    seen = set()
    unique_variations = []
    for v in variations:
        if v not in seen:
            seen.add(v)
            unique_variations.append(v)

    print(f"\nTesting {len(unique_variations)} URL variation(s):\n")

    results = []

    for idx, url in enumerate(unique_variations, 1):
        print(f"{idx}. Testing: {url}")
        print(f"   Endpoint: {url}/_api/web")

        try:
            if auth_method == "integrated":
                client = SharePointClient(
                    site_url=url,
                    auth_method="integrated",
                    verify_ssl=verify_ssl
                )
            elif auth_method == "ntlm":
                client = SharePointClient(
                    site_url=url,
                    username=username,
                    password=password,
                    auth_method="ntlm",
                    verify_ssl=verify_ssl
                )
            elif auth_method == "basic":
                client = SharePointClient(
                    site_url=url,
                    username=username,
                    password=password,
                    auth_method="basic",
                    verify_ssl=verify_ssl
                )

            # Test connection
            client.authenticate()
            site_info = client.get_site_info()

            print(f"   ✅ SUCCESS!")
            print(f"   Site Title: {site_info.get('title', 'N/A')}")
            print(f"   Server Relative URL: {site_info.get('server_relative_url', 'N/A')}")

            results.append({
                'url': url,
                'status': 'SUCCESS',
                'title': site_info.get('title', 'N/A'),
                'server_relative_url': site_info.get('server_relative_url', 'N/A')
            })

        except Exception as e:
            error_str = str(e)
            if '401' in error_str:
                print(f"   ❌ FAILED: Authentication error (401)")
                results.append({'url': url, 'status': 'AUTH_FAILED'})
            elif '404' in error_str:
                print(f"   ❌ FAILED: Not found (404)")
                results.append({'url': url, 'status': 'NOT_FOUND'})
            else:
                print(f"   ❌ FAILED: {error_str[:100]}")
                results.append({'url': url, 'status': 'ERROR', 'error': error_str[:100]})

        print()

    # Summary
    print("=" * 70)
    print("SUMMARY")
    print("=" * 70)

    successful = [r for r in results if r['status'] == 'SUCCESS']

    if successful:
        print(f"\n✅ Found {len(successful)} working URL(s):\n")
        for result in successful:
            print(f"✓ {result['url']}")
            print(f"  Title: {result['title']}")
            print(f"  Server Path: {result['server_relative_url']}")
            print()

        print("\n" + "=" * 70)
        print("RECOMMENDATION")
        print("=" * 70)
        print(f"\nUse this URL in your application:")
        print(f"  {successful[0]['url']}")

        return successful[0]['url']
    else:
        print("\n❌ No working URLs found.\n")
        print("Troubleshooting steps:")
        print("  1. Verify the base URL is correct")
        print("  2. Try accessing the URL in a browser")
        print("  3. Check if REST API is enabled")
        print("  4. Verify authentication method is correct")
        print("  5. Ensure you have permissions to access the site")

        return None


def main():
    print("SharePoint URL Format Tester")
    print()

    url = input("Enter your full SharePoint URL: ").strip()

    verify_ssl_input = input("Verify SSL? (y/n) [n]: ").strip().lower()
    verify_ssl = verify_ssl_input == 'y'

    print("\nAuthentication Methods:")
    print("1. Windows Integrated (Current User)")
    print("2. NTLM (username/password)")
    print("3. Basic Auth (username/password)")

    auth_choice = input("\nSelect method (1-3) [1]: ").strip() or "1"

    username = None
    password = None
    auth_method = "integrated"

    if auth_choice == "2":
        username = input("Username: ").strip()
        import getpass
        password = getpass.getpass("Password: ")
        auth_method = "ntlm"
    elif auth_choice == "3":
        username = input("Username: ").strip()
        import getpass
        password = getpass.getpass("Password: ")
        auth_method = "basic"

    print()
    working_url = test_url_variations(url, auth_method, username, password, verify_ssl)

    return 0 if working_url else 1


if __name__ == "__main__":
    sys.exit(main())
