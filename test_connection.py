"""
Test script to validate SharePoint connection before running the full app.
"""

from sharepoint_client import SharePointClient
import sys


def test_connection():
    """Test SharePoint connection with user credentials."""

    print("=" * 60)
    print("SharePoint Connection Test")
    print("=" * 60)

    # Get connection details
    site_url = input("\nEnter SharePoint Site URL: ").strip()

    print("\nAuthentication Methods:")
    print("1. Windows Authentication (NTLM)")
    print("2. Basic Authentication")
    print("3. OAuth (Client Credentials)")
    print("4. Access Token")

    auth_choice = input("\nSelect method (1-4): ").strip()

    try:
        if auth_choice in ["1", "2"]:
            # Windows or Basic auth
            username = input("Username (DOMAIN\\user or user@domain.com): ").strip()
            password = input("Password: ").strip()

            auth_method = "ntlm" if auth_choice == "1" else "basic"

            print(f"\n🔐 Testing {auth_method.upper()} authentication...")

            client = SharePointClient(
                site_url=site_url,
                username=username,
                password=password,
                auth_method=auth_method
            )

        elif auth_choice == "3":
            # OAuth
            client_id = input("Client ID: ").strip()
            client_secret = input("Client Secret: ").strip()
            tenant_id = input("Tenant ID: ").strip()

            print("\n🔐 Testing OAuth authentication...")

            client = SharePointClient(
                site_url=site_url,
                client_id=client_id,
                client_secret=client_secret,
                tenant_id=tenant_id,
                auth_method="oauth"
            )

        elif auth_choice == "4":
            # Access Token
            access_token = input("Access Token: ").strip()

            print("\n🔐 Testing token authentication...")

            client = SharePointClient(
                site_url=site_url,
                access_token=access_token,
                auth_method="token"
            )

        else:
            print("❌ Invalid choice")
            return

        # Authenticate
        client.authenticate()
        print("✅ Authentication successful!")

        # Get site info
        print("\n📍 Getting site information...")
        site_info = client.get_site_info()

        print("\n" + "=" * 60)
        print("Site Information:")
        print("=" * 60)
        print(f"Title: {site_info.get('title', 'N/A')}")
        print(f"URL: {site_info.get('url', 'N/A')}")
        print(f"Server Relative URL: {site_info.get('server_relative_url', 'N/A')}")
        print(f"Description: {site_info.get('description', 'N/A')}")

        # Test folder access
        test_folder = input("\n\nEnter folder path to test (or press Enter to skip): ").strip()

        if test_folder:
            print(f"\n📂 Testing folder access: {test_folder}")
            try:
                files = client.get_files_in_folder(test_folder)
                print(f"✅ Successfully accessed folder!")
                print(f"   Found {len(files)} file(s)")

                # Show first 5 files
                if files:
                    print("\n   First 5 files:")
                    for i, file in enumerate(files[:5], 1):
                        print(f"   {i}. {file['name']} ({file['size']} bytes)")

                # Count Excel files
                excel_files = [f for f in files if f['name'].endswith(('.xlsx', '.xls'))]
                print(f"\n   📊 Excel files: {len(excel_files)}")

            except Exception as e:
                print(f"❌ Folder access failed: {str(e)}")
                print("\n💡 Tips:")
                print("   - Try using full server-relative path: /sites/project/Document Library/Folder")
                print(f"   - Or relative from site: Document Library/Folder")
                print(f"   - Your site path is: {site_info.get('server_relative_url', '')}")

        print("\n" + "=" * 60)
        print("✅ Connection test completed successfully!")
        print("=" * 60)

    except Exception as e:
        print("\n" + "=" * 60)
        print("❌ Connection test failed!")
        print("=" * 60)
        print(f"Error: {str(e)}")
        print("\n💡 Troubleshooting tips:")
        print("   1. Verify your SharePoint URL is correct")
        print("   2. Check your credentials")
        print("   3. Ensure you have access permissions")
        print("   4. For NTLM: Try format DOMAIN\\username")
        print("   5. For internal sites: Use Windows Authentication (NTLM)")
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(test_connection())
