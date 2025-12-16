# Setting Up Real Google OAuth

Your "Sign in with Google" feature is currently using a **development shortcut**. Follow this guide to enable real Google OAuth authentication.

## Current Status

✓ Server is running  
✓ OAuth endpoints are working  
⚠ Using dev shortcut (GOOGLE_CLIENT_ID not configured)

## Quick Setup (5 minutes)

### Step 1: Get Google OAuth Credentials

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Create a new project or select an existing one
3. Go to **APIs & Services** → **Credentials**
4. Click **Create Credentials** → **OAuth client ID**
5. If prompted, configure the OAuth consent screen first:
   - Choose "External" for testing
   - Fill in app name and your email
   - Add scopes: `openid`, `email`, `profile`
   - Add your Gmail as a test user
6. Back in Credentials, create OAuth client ID:
   - Application type: **Web application**
   - Name: Story Generator (or any name)
   - Authorized redirect URIs: Add this exact URL:
     ```
     http://127.0.0.1:5000/api/auth/google/callback
     ```
7. Click **Create**
8. **Copy the Client ID and Client Secret** that appear

### Step 2: Configure Your Application

1. Open your `.env` file (or create it from `.env.example`)

2. Add these lines with your credentials:
   ```env
   GOOGLE_CLIENT_ID=your-client-id-here.apps.googleusercontent.com
   GOOGLE_CLIENT_SECRET=your-client-secret-here
   GOOGLE_OAUTH_REDIRECT=http://127.0.0.1:5000/api/auth/google/callback
   ```

3. Save the file

### Step 3: Restart the Server

```bash
# Stop the current server (Ctrl+C in the terminal where it's running)
# Or in PowerShell:
Stop-Job -Id 3; Remove-Job -Id 3

# Start it again
python app.py
```

### Step 4: Test It!

1. Run the test script to verify:
   ```bash
   python tools\test_oauth_config.py
   ```
   
   You should see:
   ```
   ✓ Google OAuth is ENABLED and configured
   Redirects to Google
   ```

2. Open your browser to http://127.0.0.1:5000

3. Click **"Sign in with Google"**

4. You should see the **real Google sign-in page**

5. Sign in with your Google account (must be one of the test users you added)

6. You'll be redirected back and signed in with your Google profile!

## Troubleshooting

### "OAuth NOT configured" after adding credentials

**Problem**: Test still shows dev shortcut is being used

**Solutions**:
- Make sure you saved the `.env` file
- Verify the Client ID doesn't have quotes or extra spaces
- Restart the Flask server completely
- Run: `python -c "from config import Config; print(Config.GOOGLE_CLIENT_ID)"`
  - Should show your Client ID, not `None`

### "redirect_uri_mismatch" error

**Problem**: Google says the redirect URI doesn't match

**Solutions**:
- The redirect URI in Google Console must be **exactly**:
  ```
  http://127.0.0.1:5000/api/auth/google/callback
  ```
- No trailing slash
- Use `127.0.0.1` not `localhost`
- Match what's in your `GOOGLE_OAUTH_REDIRECT` environment variable

### "Access blocked: This app's request is invalid"

**Problem**: Google blocks the sign-in

**Solutions**:
- Make sure you added yourself as a test user in the OAuth consent screen
- Verify the OAuth consent screen is configured
- Check that you added the scopes: `openid`, `email`, `profile`

### "This app hasn't been verified"

**Problem**: Warning screen appears

**Solution**: This is normal during development
- Click **"Advanced"**
- Click **"Go to [App Name] (unsafe)"**
- For production, you'll need to submit for Google verification

### Still seeing the dev form with email input

**Problem**: Dev shortcut still appears instead of Google sign-in

**Solutions**:
1. Check your `.env` file has the correct values
2. Restart the server
3. Clear your browser cache
4. Run the test script: `python tools\test_oauth_config.py`

## Security Notes

⚠️ **IMPORTANT**:
- Never commit your `.env` file with real credentials
- Make sure `.env` is in your `.gitignore`
- The dev shortcut automatically disables when you add credentials
- For production deployment, use HTTPS and proper redirect URIs

## What Changes When OAuth is Enabled?

**Before** (Dev Shortcut):
- Click "Sign in with Google"
- See a simple form to enter email/name
- Sign in with test data

**After** (Real OAuth):
- Click "Sign in with Google"  
- Redirected to Google's real sign-in page
- Choose your Google account
- Grant permissions
- Redirected back to your app
- Signed in with real Google profile (name, email, picture)

## Need More Help?

See the detailed guide: [GOOGLE_OAUTH_SETUP.md](GOOGLE_OAUTH_SETUP.md)

Or run the diagnostic test:
```bash
python tools\test_oauth_config.py
```
