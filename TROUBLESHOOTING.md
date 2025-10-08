# SharePoint Authentication Troubleshooting Guide

## 401 Authentication Error

If you're getting a 401 error with NTLM authentication, try these solutions:

### 1. Username Format

Try different username formats:

```
DOMAIN\username      (e.g., CONTOSO\john.doe)
username@domain.com  (e.g., john.doe@contoso.com)
username             (just username, if on same domain)
```

### 2. Check Your Credentials

**Test if credentials work in browser:**
1. Open an Incognito/Private browser window
2. Navigate to your SharePoint URL
3. Enter the same credentials
4. If it works in browser but not in script, continue to step 3

### 3. Domain Authentication Issues

**For internal SharePoint with Windows Authentication:**

Some internal SharePoint sites require different authentication approaches:

#### Option A: Try requests-negotiate-sspi (Windows only)
```bash
pip install requests-negotiate-sspi
```

This uses your current Windows login automatically (no username/password needed).

#### Option B: Use requests-kerberos (Linux/Mac)
```bash
pip install requests-kerberos
```

For domain-joined machines.

### 4. Common Issues & Solutions

| Issue | Solution |
|-------|----------|
| "Cannot connect" | Check VPN connection if required |
| SSL certificate error | Uncheck "Verify SSL Certificate" |
| 401 with correct credentials | May need Kerberos/SSPI instead of NTLM |
| Domain not recognized | Use full UPN format: user@domain.com |
| Works in browser, not script | Browser may be using Kerberos/Negotiate |

### 5. Alternative Authentication Methods

If NTLM doesn't work, try:

**A. Basic Authentication**
- Select "Basic Authentication" in the app
- Use same credentials
- Less secure but may work if NTLM is disabled

**B. Session-based Auth (Browser cookies)**
- Not yet implemented, but can be added if needed

**C. App Registration (OAuth)**
- Requires admin to create app registration in Azure AD
- Most secure and reliable for automation

### 6. Testing Authentication

Use the test script to isolate the issue:

```bash
python test_connection.py
```

Try different combinations:
1. Different username formats
2. With/without SSL verification
3. Different auth methods (NTLM vs Basic)

### 7. Check SharePoint Configuration

**Questions to ask your SharePoint admin:**

1. What authentication method is enabled on the site?
   - NTLM
   - Kerberos
   - Basic Auth
   - Forms-based authentication
   - Claims-based authentication

2. Is the REST API enabled?
   - Test URL: `https://yoursite/_api/web`

3. Are there any IP restrictions or additional security policies?

4. What permissions does your account need?
   - Minimum: Read access to the site and libraries

### 8. Debugging Tips

**Enable verbose logging:**

Add this to the top of your script to see HTTP details:

```python
import logging
import http.client as http_client

http_client.HTTPConnection.debuglevel = 1
logging.basicConfig()
logging.getLogger().setLevel(logging.DEBUG)
requests_log = logging.getLogger("requests.packages.urllib3")
requests_log.setLevel(logging.DEBUG)
requests_log.propagate = True
```

This will show you exactly what's being sent and received.

### 9. Network/VPN Issues

**If you're getting connection errors:**

1. Verify you can reach the SharePoint URL:
   ```bash
   curl -I https://teamsites.xx.orgname.net/sites/project
   ```

2. Check if VPN is required and connected

3. Verify DNS resolution:
   ```bash
   nslookup teamsites.xx.orgname.net
   ```

### 10. When All Else Fails

**Manual REST API Testing:**

Test the REST API directly with curl:

```bash
# For NTLM
curl -u "DOMAIN\\username:password" --ntlm \
  https://yoursite/_api/web

# For Basic Auth
curl -u "username:password" \
  https://yoursite/_api/web
```

If curl works but Python doesn't, there may be a Python-specific configuration issue.

---

## Need More Help?

If none of these solutions work, gather this information:

1. SharePoint version (on-premises or Online?)
2. Authentication method that works in browser
3. Output from `python test_connection.py` with different options
4. Any error messages from SharePoint admin
5. Whether you're connecting from inside or outside the corporate network

This will help identify the specific authentication configuration needed.
