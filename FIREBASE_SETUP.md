# Firebase Authentication Setup Guide

Firebase makes Google sign-in incredibly simple and production-ready. Follow this guide to enable real Firebase Authentication.

## Why Firebase?

✅ **Easier than raw OAuth** - No redirect URIs to configure  
✅ **More secure** - Token verification handled by Firebase  
✅ **Better UX** - Popup or redirect, email/password, phone auth  
✅ **Production-ready** - Scales automatically, free tier generous  
✅ **Multiple providers** - Google, Facebook, Twitter, GitHub, etc.

## Setup Steps (10 minutes)

### Step 1: Create Firebase Project

1. Go to [Firebase Console](https://console.firebase.google.com/)
2. Click "Add project"
3. Enter project name: `story-generator` (or your choice)
4. Disable Google Analytics (optional, not needed)
5. Click "Create project"
6. Wait for project creation, then click "Continue"

### Step 2: Enable Google Sign-In

1. In Firebase Console, click **Authentication** in the left menu
2. Click **Get started**
3. Go to **Sign-in method** tab
4. Click on **Google**
5. Toggle **Enable**
6. Enter project support email (your email)
7. Click **Save**

✅ **That's it for Google sign-in setup!** No OAuth redirect URIs needed.

### Step 3: Get Web App Configuration

1. In Firebase Console, click the **gear icon** ⚙️ → **Project settings**
2. Scroll down to **Your apps**
3. Click the **Web** icon `</>`
4. Enter app nickname: `story-generator-web`
5. **Don't** check Firebase Hosting
6. Click **Register app**
7. You'll see the Firebase config object - **copy these values**:

```javascript
const firebaseConfig = {
  apiKey: "AIza...",              // ← Copy this
  authDomain: "your-project.firebaseapp.com",  // ← And this
  projectId: "your-project-id",   // ← And this
  // ... other fields (not needed for auth)
};
```

8. Click **Continue to console**

### Step 4: Generate Service Account Key (Backend)

1. Still in Project settings, go to **Service accounts** tab
2. Click **Generate new private key**
3. Click **Generate key**
4. A JSON file will download - **keep it safe!**
5. Rename it to `firebase-service-account.json`
6. Move it to your project root: `C:\story-generator\`

**Important**: Never commit this file to Git! It's already in `.gitignore`.

### Step 5: Configure Your Application

Update your `.env` file with the Firebase configuration:

```env
# ===== Firebase Authentication =====
# From step 3 (Web app config)
FIREBASE_WEB_API_KEY=AIza...your-api-key-here
FIREBASE_PROJECT_ID=your-project-id
FIREBASE_AUTH_DOMAIN=your-project.firebaseapp.com

# From step 4 (Service account)
FIREBASE_SERVICE_ACCOUNT_PATH=firebase-service-account.json

# Alternative: Use JSON string instead of file (for deployment)
# FIREBASE_SERVICE_ACCOUNT_JSON='{"type":"service_account","project_id":"..."}'
```

**Example `.env` file:**
```env
SECRET_KEY=your-secret-key-here
GEMINI_API_KEY=your-gemini-key
IMAGE_PROVIDER=stability
STABILITY_API_KEY=your-stability-key

# Firebase
FIREBASE_WEB_API_KEY=AIzaSyC1234567890abcdefghijk
FIREBASE_PROJECT_ID=story-generator-12345
FIREBASE_AUTH_DOMAIN=story-generator-12345.firebaseapp.com
FIREBASE_SERVICE_ACCOUNT_PATH=firebase-service-account.json
```

### Step 6: Update Frontend Configuration

The frontend needs the Firebase config to initialize the SDK. Create a file `static/js/firebase-config.js`:

```javascript
// Firebase configuration
// Get these values from Firebase Console → Project Settings → Web app
const firebaseConfig = {
  apiKey: "YOUR_FIREBASE_WEB_API_KEY",
  authDomain: "YOUR_PROJECT_ID.firebaseapp.com",
  projectId: "YOUR_PROJECT_ID"
};

// Initialize Firebase (this will be used by main.js)
if (typeof firebase !== 'undefined') {
  firebase.initializeApp(firebaseConfig);
}
```

Or better yet, load from environment (the app will do this automatically).

### Step 7: Restart Your Server

```bash
# Stop the current server (Ctrl+C or PowerShell)
Stop-Job -Id 3; Remove-Job -Id 3

# Start it again
python app.py
```

You should see in the logs:
```
✓ Firebase Admin SDK initialized successfully
```

### Step 8: Test It!

1. Open http://127.0.0.1:5000
2. Click **"Sign in with Google"**
3. You should see the Firebase/Google sign-in popup
4. Sign in with your Google account
5. You'll be redirected back, signed in with your real Google profile!

## Verification

Run the test script:
```bash
python tools\test_firebase_config.py
```

Expected output:
```
✓ Firebase is ENABLED and configured
✓ Backend can verify tokens
✓ Frontend config is present
```

## Troubleshooting

### "Firebase not configured"

**Problem**: Server logs show Firebase not initialized

**Solutions**:
- Check `.env` file has all Firebase variables
- Verify `firebase-service-account.json` exists in project root
- Check file path is correct (relative to project root)
- Restart the server after changing `.env`

### "Invalid API key"

**Problem**: Frontend can't initialize Firebase

**Solutions**:
- Verify `FIREBASE_WEB_API_KEY` matches what's in Firebase Console
- Check for typos or extra spaces
- Make sure you copied the API key, not the project ID

### "Permission denied" error

**Problem**: Firebase blocks sign-in attempt

**Solutions**:
- In Firebase Console → Authentication → Sign-in method
- Verify Google provider is **Enabled**
- Check that your email is authorized (for development)
- Add authorized domains in Firebase Console if needed

### "Service account initialization failed"

**Problem**: Backend can't load service account

**Solutions**:
- Verify JSON file path is correct
- Check file permissions (should be readable)
- Try using `FIREBASE_SERVICE_ACCOUNT_JSON` with the full JSON string instead
- Make sure the JSON file is valid (not corrupted)

## Deployment Notes

### For Production:

**Option 1: Use JSON file**
- Upload `firebase-service-account.json` to your server
- Set `FIREBASE_SERVICE_ACCOUNT_PATH` to the full path
- Secure the file (chmod 600)

**Option 2: Use environment variable (recommended)**
- Copy entire JSON file content
- Set as `FIREBASE_SERVICE_ACCOUNT_JSON` environment variable
- More secure (no file on disk)
- Example:
  ```bash
  export FIREBASE_SERVICE_ACCOUNT_JSON='{"type":"service_account",...}'
  ```

### Authorized Domains

For production, add your domain:
1. Firebase Console → Authentication → Settings
2. Scroll to **Authorized domains**
3. Click **Add domain**
4. Enter your production domain (e.g., `yourdomain.com`)

## Features You Get with Firebase

✅ **Google Sign-In** - Already working!  
✅ **Email/Password** - Easy to add  
✅ **Phone Auth** - SMS verification  
✅ **Facebook, Twitter, GitHub** - Multiple providers  
✅ **Anonymous Auth** - Let users try before signing up  
✅ **Email Verification** - Built-in  
✅ **Password Reset** - Automatic emails  
✅ **User Management** - Firebase Console UI  

## Next Steps

Want to add more auth methods?

### Add Email/Password Sign-In:
1. Firebase Console → Authentication → Sign-in method
2. Enable **Email/Password**
3. Update frontend to show email/password form
4. Call Firebase `createUserWithEmailAndPassword()`

### Add Phone Authentication:
1. Enable **Phone** provider in Firebase Console
2. Add phone verification UI to frontend
3. Call Firebase `signInWithPhoneNumber()`

## Comparison: Firebase vs Raw OAuth

| Feature | Firebase | Raw OAuth |
|---------|----------|-----------|
| Setup Time | 10 minutes | 30+ minutes |
| Redirect URIs | Not needed | Must configure |
| Token Verification | Automatic | Manual implementation |
| Multiple Providers | Built-in | Code each separately |
| Email Verification | Built-in | Must implement |
| Password Reset | Built-in | Must implement |
| User Management | Firebase Console | Build your own |
| Security | Google-maintained | You maintain |
| Free Tier | 50K MAU | N/A |
| Cost | Free or cheap | Free (DIY) |

**Recommendation**: Use Firebase for production apps. It's simpler, more secure, and more feature-rich.

## Security Best Practices

✅ **Never commit service account JSON** - Already in `.gitignore`  
✅ **Rotate keys regularly** - Generate new service accounts periodically  
✅ **Use environment variables** - Don't hardcode credentials  
✅ **Restrict API keys** - In Firebase Console, set API restrictions  
✅ **Enable email verification** - Verify users' email addresses  
✅ **Monitor auth logs** - Check Firebase Console → Authentication → Users  

## Support

- [Firebase Auth Documentation](https://firebase.google.com/docs/auth)
- [Firebase Console](https://console.firebase.google.com/)
- [Stack Overflow - firebase-authentication](https://stackoverflow.com/questions/tagged/firebase-authentication)

---

**Your Firebase setup is complete! Enjoy production-ready authentication!** 🎉
