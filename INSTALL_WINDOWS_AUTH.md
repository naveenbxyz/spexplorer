# Windows Integrated Authentication Setup

This is the **RECOMMENDED** authentication method for internal SharePoint sites. It's the Python equivalent of C#'s `UseDefaultCredentials = true`.

## What is Windows Integrated Authentication?

It automatically uses your current Windows login credentials - **no username or password needed!** This is exactly what happens when you access SharePoint in your browser while logged into your Windows machine.

## Installation

### For Windows:
```bash
pip install requests-negotiate-sspi
```

### For Linux/Mac (domain-joined machines):
```bash
pip install requests-kerberos
```

## Usage

### 1. In the Streamlit App:

1. Run the app:
   ```bash
   streamlit run app.py
   ```

2. In the sidebar:
   - **Authentication Method**: Select "Windows Integrated (Current User)"
   - **Site URL**: Enter your SharePoint URL
   - **Verify SSL Certificate**: Uncheck if you have self-signed certificates
   - Click **Connect to SharePoint**

3. That's it! No username or password needed.

### 2. In Test Script:

```bash
python test_connection.py
```

When prompted:
- **Select method**: Choose `1` (Windows Integrated)
- **Site URL**: Enter your SharePoint URL
- **Verify SSL**: Enter `n` if you have self-signed certificates

### 3. Programmatically:

```python
from sharepoint_client import SharePointClient

# Create client with integrated auth
client = SharePointClient(
    site_url="https://teamsites.company.net/sites/project",
    auth_method="integrated",
    verify_ssl=False  # Set to True if you have valid SSL certificates
)

# Authenticate (uses current Windows user)
client.authenticate()

# Get site info
site_info = client.get_site_info()
print(f"Connected to: {site_info['title']}")

# Get files
files = client.get_files_in_folder("Document Library/Secure Area")
print(f"Found {len(files)} files")
```

## How It Works

**Windows (SSPI):**
- Uses Windows SSPI (Security Support Provider Interface)
- Automatically negotiates with the server (Kerberos or NTLM)
- Same mechanism Internet Explorer/Edge uses
- No credentials stored in code

**Linux/Mac (Kerberos):**
- Uses Kerberos tickets from domain-joined machines
- Requires valid Kerberos ticket (kinit)

## Troubleshooting

### Error: "Windows Integrated Authentication requires additional package"

**Solution:** Install the required package:
```bash
# Windows
pip install requests-negotiate-sspi

# Linux/Mac
pip install requests-kerberos
```

### Error: "401 Unauthorized"

**Possible causes:**
1. Not logged into Windows domain
2. Not on VPN (if required)
3. Account doesn't have SharePoint access
4. SharePoint doesn't support Negotiate/Kerberos auth

**Solutions:**
- Ensure you're logged into your Windows domain
- Connect to VPN if required
- Verify you can access SharePoint in browser
- Ask admin if Negotiate authentication is enabled

### Works in browser but not in script

**This is common!** Browsers use Windows Integrated Auth automatically.

**Solution:** Use the "Windows Integrated (Current User)" option - it does the same thing.

## Comparison of Authentication Methods

| Method | Pros | Cons | Use Case |
|--------|------|------|----------|
| **Windows Integrated** | ✅ No credentials needed<br>✅ Most secure<br>✅ Works like browser | ❌ Requires package install<br>❌ Windows/domain only | **RECOMMENDED for internal SharePoint** |
| NTLM with credentials | ✅ Works without extra packages<br>✅ Cross-platform | ❌ Must enter password<br>❌ Credentials in memory | When Integrated Auth fails |
| Basic Auth | ✅ Simple | ❌ Least secure<br>❌ Often disabled | Testing/debugging only |
| OAuth | ✅ Most secure for automation<br>✅ Token-based | ❌ Requires admin setup | Production automation |

## Why This Method?

Your internal SharePoint blog mentioned `UseDefaultCredentials = true` from C#. This is the **exact Python equivalent**:

**C# (HttpClient):**
```csharp
var handler = new HttpClientHandler {
    UseDefaultCredentials = true
};
var client = new HttpClient(handler);
```

**Python (our implementation):**
```python
client = SharePointClient(
    site_url="...",
    auth_method="integrated"
)
```

Both use the same underlying Windows authentication mechanism!

## Next Steps

1. Install the package:
   ```bash
   pip install requests-negotiate-sspi
   ```

2. Test the connection:
   ```bash
   python test_connection.py
   ```
   Select option `1` (Windows Integrated)

3. If successful, use it in the main app!

This should solve your 401 authentication error! 🎉
