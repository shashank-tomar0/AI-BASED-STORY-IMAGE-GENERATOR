# Firebase OAuth - Quick Setup Guide

## ✅ What's Configured

Your StoryCanvas app now has **real Firebase OAuth authentication** with:

- ✅ **Google Sign-In** with account selection
- ✅ **User Profiles** with avatar and display name
- ✅ **Dark/Light Theme** toggle
- ✅ **Professional UI** with user menu

## 🚀 How to Test

### 1. Refresh Your Browser
Hard refresh to load new code:
- **Windows**: `Ctrl + Shift + R`
- **Mac**: `Cmd + Shift + R`

### 2. Click "Sign in with Google"
You'll see:
1. **Google Account Picker** - Select which email to use
2. **Permission Screen** - Allow StoryCanvas to access your basic info
3. **Success!** - You're signed in with your real Google account

### 3. See Your Profile
After signing in, you'll see in the header:
- Your **Google avatar** (profile picture)
- Your **display name**
- Your **email address**
- **Sign Out** button

### 4. Try Theme Toggle
Click the **🌙 Dark** button in the header to switch between:
- **Dark Mode** (cyberpunk aesthetic)
- **Light Mode** (clean, professional)

## 📋 What You Need (One-Time Setup)

### Enable Firebase Auth (5 minutes)

1. **Go to Firebase Console**
   - Visit: https://console.firebase.google.com/
   - Select project: `story-generator-1418f`

2. **Enable Google Sign-In**
   - Click **Authentication** in left menu
   - Click **Get started** (if first time)
   - Go to **Sign-in method** tab
   - Click **Google** provider
   - Toggle **Enable**
   - Set support email (your email)
   - Click **Save**

3. **Done!** Firebase is ready to use

## 🔑 How It Works

### Frontend (Browser)
```javascript
// When user clicks "Sign in with Google"
1. Firebase SDK shows Google account picker
2. User selects account and grants permission
3. Firebase returns ID token
4. Token sent to your backend for verification
```

### Backend (Server)
```python
# /auth/firebase-verify endpoint
1. Receives ID token from frontend
2. Verifies with Firebase Admin SDK
3. Extracts user info (email, name, avatar)
4. Creates session for user
5. Returns success with user profile
```

## 🎨 Theme System

### How Theme Toggle Works
```javascript
// Click theme toggle button
1. Switches data-theme attribute on <html>
2. CSS automatically updates colors
3. Preference saved in localStorage
4. Persists across browser sessions
```

### Customizing Themes

**Dark Theme Colors:**
- Primary: `#00ff88` (electric cyan)
- Accent: `#ff6b9d` (pink)
- Background: `#0a0e1a` (deep navy)

**Light Theme Colors:**
- Primary: `#00cc70` (green)
- Accent: `#e63980` (magenta)
- Background: `#f8f9fa` (light gray)

Edit in `templates/index.html` under `[data-theme="light"]`

## 🔒 Security Features

✅ **Token Verification** - Backend verifies every Firebase token
✅ **Secure Sessions** - Server-side session management
✅ **HTTPS Ready** - Works with SSL in production
✅ **CSRF Protection** - Firebase handles state tokens
✅ **Email Verification** - Can enable in Firebase Console

## 📊 User Profile Data

When a user signs in, you get:
```json
{
  "email": "user@gmail.com",
  "display_name": "John Doe",
  "avatar": "https://lh3.googleusercontent.com/...",
  "email_verified": true,
  "firebase_uid": "abc123..."
}
```

This data is:
- Stored in `USERS` dictionary (in-memory for dev)
- Displayed in the header with avatar
- Used for personalization

## 🎯 Next Steps

### Production Deployment

1. **Get Service Account Key**
   - Firebase Console → Project Settings → Service Accounts
   - Click "Generate new private key"
   - Download JSON file
   - Add to `.env`: `FIREBASE_SERVICE_ACCOUNT_PATH=firebase-service-account.json`

2. **Add to Authorized Domains**
   - Firebase Console → Authentication → Settings
   - Add your production domain to authorized domains

3. **Environment Variables**
   ```env
   FIREBASE_WEB_API_KEY=AIzaSyAMa2R1mfJMygVtdMeoizDYdIA3b3MSj68
   FIREBASE_PROJECT_ID=story-generator-1418f
   FIREBASE_AUTH_DOMAIN=story-generator-1418f.firebaseapp.com
   FIREBASE_SERVICE_ACCOUNT_PATH=path/to/service-account.json
   ```

### Add More Auth Providers

Firebase supports many providers out of the box:

**Email/Password:**
1. Enable in Firebase Console
2. Add email/password form to frontend
3. Call `firebase.auth().createUserWithEmailAndPassword()`

**Facebook/Twitter/GitHub:**
1. Enable provider in Firebase Console
2. Add app credentials from provider
3. Use same popup flow as Google

**Phone Authentication:**
1. Enable Phone provider
2. Add phone input UI
3. Call `firebase.auth().signInWithPhoneNumber()`

## 🐛 Troubleshooting

### "Firebase not initialized"
- Check browser console for errors
- Verify Firebase SDK loaded (see Network tab)
- Hard refresh browser cache

### "Pop-up blocked"
- Allow pop-ups for `localhost:5000`
- Or use redirect flow instead:
  ```javascript
  await auth.signInWithRedirect(googleProvider);
  ```

### "Invalid API key"
- Verify `apiKey` in `firebase-init.js` matches Firebase Console
- Check for typos or extra spaces

### "Backend verification failed"
- Ensure server is running
- Check server logs for errors
- Verify service account key is valid

## 📚 Resources

- [Firebase Auth Docs](https://firebase.google.com/docs/auth)
- [Firebase Console](https://console.firebase.google.com/)
- [Your Project](https://console.firebase.google.com/project/story-generator-1418f)

## ✨ Features You Have Now

### Authentication
- ✅ Google OAuth with account picker
- ✅ User profile with avatar
- ✅ Session management
- ✅ Secure token verification

### UI/UX
- ✅ Dark/Light theme toggle
- ✅ Modern glassmorphism design
- ✅ JetBrains Mono font
- ✅ Smooth animations
- ✅ Responsive layout

### User Experience
- ✅ Profile display in header
- ✅ Avatar with hover effect
- ✅ Sign-out confirmation
- ✅ Success/error messages
- ✅ Theme persistence

---

**Everything is configured and ready to test!**  
Just refresh your browser and click "Sign in with Google" 🚀
