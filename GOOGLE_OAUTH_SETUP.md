# Google OAuth Setup Guide

This guide will help you set up real Google OAuth2 authentication for the "Sign in with Google" feature.

## Step 1: Create a Google Cloud Project

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Click "Select a project" → "New Project"
3. Enter a project name (e.g., "Story Generator")
4. Click "Create"

## Step 2: Enable Google+ API

1. In your project, go to "APIs & Services" → "Library"
2. Search for "Google+ API" or "People API"
3. Click on it and press "Enable"

## Step 3: Configure OAuth Consent Screen

1. Go to "APIs & Services" → "OAuth consent screen"
2. Select "External" (unless you have a Google Workspace)
3. Click "Create"
4. Fill in the required fields:
   - **App name**: Story Generator (or your app name)
   - **User support email**: Your email
   - **Developer contact email**: Your email
5. Click "Save and Continue"
6. On "Scopes" page, click "Add or Remove Scopes"
7. Add these scopes:
   - `openid`
   - `email`
   - `profile`
8. Click "Save and Continue"
9. On "Test users" page (for development):
   - Click "Add Users"
   - Add your Gmail address and any other test accounts
10. Click "Save and Continue"

## Step 4: Create OAuth 2.0 Credentials

1. Go to "APIs & Services" → "Credentials"
2. Click "Create Credentials" → "OAuth client ID"
3. Select "Web application"
4. Enter a name (e.g., "Story Generator Web Client")
5. Under "Authorized redirect URIs", add:
   ```
   http://localhost:5000/api/auth/google/callback
   http://127.0.0.1:5000/api/auth/google/callback
   ```
   
   **Note**: For production, add your production domain:
   ```
   https://yourdomain.com/api/auth/google/callback
   ```

6. Click "Create"
7. **Save the Client ID and Client Secret** that appear

## Step 5: Configure Your Application

Create or update your `.env` file in the project root with the credentials:

```env
# Google OAuth2 Configuration
GOOGLE_CLIENT_ID=your-client-id-here.apps.googleusercontent.com
GOOGLE_CLIENT_SECRET=your-client-secret-here
GOOGLE_OAUTH_REDIRECT=http://127.0.0.1:5000/api/auth/google/callback

# Other required configuration
GEMINI_API_KEY=your-gemini-key-here
SECRET_KEY=your-secret-key-here
```

**Important**: 
- Never commit your `.env` file to git
- Make sure `.env` is in your `.gitignore`

## Step 6: Test the OAuth Flow

1. Start your server:
   ```bash
   python app.py
   ```

2. Open http://127.0.0.1:5000 in your browser

3. Click "Sign in with Google"

4. You should see the Google sign-in page:
   - If you added test users in Step 3, only those accounts can sign in during development
   - Select your Google account
   - Grant permissions when asked

5. You'll be redirected back to your app and signed in with:
   - Your Google email as username
   - Your Google profile name
   - Your Google profile picture

## Troubleshooting

### "Access blocked: This app's request is invalid"
- Make sure your redirect URI in Google Console exactly matches `GOOGLE_OAUTH_REDIRECT` in `.env`
- Check that you've enabled the required APIs

### "Error 400: redirect_uri_mismatch"
- The redirect URI doesn't match what's configured in Google Console
- Update either your `.env` file or Google Console to match

### "This app hasn't been verified"
- This is normal during development
- Click "Advanced" → "Go to [App Name] (unsafe)" to continue
- For production, you'll need to verify your app with Google

### Dev Shortcut Still Appears
- Make sure `GOOGLE_CLIENT_ID` and `GOOGLE_CLIENT_SECRET` are properly set in `.env`
- Restart your Flask server after updating `.env`
- Check the server logs to confirm the variables are loaded

## Production Deployment

For production:

1. Update OAuth consent screen to "In production" status
2. Add your production domain to authorized redirect URIs
3. Update `GOOGLE_OAUTH_REDIRECT` to use your production URL:
   ```env
   GOOGLE_OAUTH_REDIRECT=https://yourdomain.com/api/auth/google/callback
   ```
4. Consider implementing PKCE for enhanced security
5. Add state parameter verification to prevent CSRF attacks

## Security Best Practices

1. **Never hardcode credentials** - Always use environment variables
2. **Use HTTPS in production** - OAuth should only run over secure connections
3. **Validate redirect URIs** - Ensure they match your configured values
4. **Keep secrets secure** - Don't commit `.env` files or expose secrets in logs
5. **Implement CSRF protection** - Use state parameter in OAuth flow
6. **Regular credential rotation** - Periodically regenerate client secrets
