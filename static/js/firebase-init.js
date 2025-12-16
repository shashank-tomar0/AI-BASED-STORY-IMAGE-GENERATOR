// ========== FIREBASE CONFIGURATION & INITIALIZATION ==========
const firebaseConfig = {
  apiKey: "AIzaSyAMa2R1mfJMygVtdMeoizDYdIA3b3MSj68",
  authDomain: "story-generator-1418f.firebaseapp.com",
  projectId: "story-generator-1418f",
  storageBucket: "story-generator-1418f.firebasestorage.app",
  messagingSenderId: "27125244334",
  appId: "1:27125244334:web:6808d1599dca7eafbc283f",
  measurementId: "G-YB6RZ9HE7P"
};

// Initialize Firebase
console.log('🔥 Initializing Firebase...');
firebase.initializeApp(firebaseConfig);
const auth = firebase.auth();

// Set persistence to LOCAL (survives browser restarts)
auth.setPersistence(firebase.auth.Auth.Persistence.LOCAL)
  .then(() => {
    console.log('✓ Auth persistence set to LOCAL');
  })
  .catch((error) => {
    console.error('❌ Failed to set persistence:', error.code, error.message);
  });

// Google Auth Provider with account selection
const googleProvider = new firebase.auth.GoogleAuthProvider();
googleProvider.setCustomParameters({
  prompt: 'select_account' // Force account picker every time
});

// Current user state
let currentUser = null;

// Messaging helpers that gracefully fall back if app-level modals aren't loaded yet
function notifySuccess(message) {
  if (typeof showSuccess === 'function') {
    showSuccess(message);
  } else if (typeof console !== 'undefined') {
    console.log('SUCCESS:', message);
  }
}

function notifyError(message) {
  if (typeof showModal === 'function') {
    showModal('error-modal', message);
  } else if (typeof console !== 'undefined') {
    console.error('ERROR:', message);
  }
}

// Status banner for auth flow
function showAuthStatusBanner(message) {
  let banner = document.getElementById('auth-status-banner');
  if (!banner) {
    banner = document.createElement('div');
    banner.id = 'auth-status-banner';
    banner.style.cssText = `
      position: fixed; top: 0; left: 0; right: 0; z-index: 999;
      background: linear-gradient(135deg, rgba(0,255,136,0.2), rgba(0,255,136,0.1));
      border-bottom: 2px solid rgba(0,255,136,0.5);
      padding: 1rem;
      text-align: center;
      color: var(--primary);
      font-family: 'JetBrains Mono', monospace;
      font-size: 0.875rem;
      backdrop-filter: blur(10px);
    `;
    document.body.prepend(banner);
  }
  banner.textContent = message;
  banner.style.display = 'block';
}

function hideAuthStatusBanner() {
  const banner = document.getElementById('auth-status-banner');
  if (banner) banner.style.display = 'none';
}

// ========== THEME TOGGLE ==========
const THEME_KEY = 'story-canvas-theme';
let currentTheme = localStorage.getItem(THEME_KEY) || 'dark';

function initTheme() {
  document.documentElement.setAttribute('data-theme', currentTheme);
  updateThemeToggle();
}

function toggleTheme() {
  currentTheme = currentTheme === 'dark' ? 'light' : 'dark';
  localStorage.setItem(THEME_KEY, currentTheme);
  document.documentElement.setAttribute('data-theme', currentTheme);
  updateThemeToggle();
  
  notifySuccess(`Switched to ${currentTheme} mode`);
}

function updateThemeToggle() {
  const toggleBtn = document.getElementById('theme-toggle');
  if (toggleBtn) {
    const icon = currentTheme === 'dark' ? '☀️' : '🌙';
    const label = currentTheme === 'dark' ? 'Light' : 'Dark';
    toggleBtn.innerHTML = `${icon} ${label}`;
  }
}

// ========== BACKEND EXCHANGE ==========
async function exchangeFirebaseToken(idToken, userMeta) {
  showAuthStatusBanner('⏳ Finalizing session…');
  console.log('🔄 Exchanging Firebase token with backend...');
  
  try {
    const response = await fetch('/api/auth/firebase', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ 
        idToken,
        // Provide non-sensitive user hints to help dev backends without Firebase Admin
        user: userMeta ? {
          email: userMeta.email || null,
          display_name: userMeta.displayName || null,
          picture: userMeta.photoURL || null,
          uid: userMeta.uid || null
        } : undefined
      })
    });

    console.log('📡 Backend response status:', response.status);
    const data = await response.json().catch(() => ({}));
    console.log('📦 Backend response data:', data);

    if (!response.ok || data.error) {
      const errMsg = data.error || `Firebase session exchange failed (HTTP ${response.status})`;
      console.error('❌ Exchange error:', errMsg);
      throw new Error(errMsg);
    }

    const user = data.user || {};
    const username = data.username || user.username || user.email || user.display_name || (user.email || 'google_user');
    const displayName = user.display_name || data.display_name || user.name || username;
    const avatar = user.avatar || data.avatar || user.picture || null;
    const userId = data.user_id || user.id || null;

    console.log('✓ Token exchange successful:', { username, displayName, userId });

    // Persist for the main app to consume
    if (data.token) localStorage.setItem('authToken', data.token);
    if (username) localStorage.setItem('username', username);
    if (userId) localStorage.setItem('userId', userId);
    if (displayName) localStorage.setItem('displayName', displayName);
    if (avatar) localStorage.setItem('avatar', avatar);

    hideAuthStatusBanner();
    return { token: data.token, username, displayName, avatar, userId };
  } catch (error) {
    console.error('💥 Token exchange failed:', error.message);
    hideAuthStatusBanner();
    throw error;
  }
}

// ========== AUTH STATE MANAGEMENT ==========
auth.onAuthStateChanged(async (user) => {
  if (user) {
    currentUser = user;
    console.log('✓ Firebase Auth state changed - user signed in:', user.email);
    console.log('  Display Name:', user.displayName);
    console.log('  Photo URL:', user.photoURL);
    
    try {
      const idToken = await user.getIdToken();
      console.log('🔐 Got ID token, exchanging with backend...');
      const session = await exchangeFirebaseToken(idToken, user);
      console.log('📢 Dispatching firebase-auth-success event...');
      try { window.dispatchEvent(new CustomEvent('firebase-auth-success', { detail: session })); } catch (_) {}
      updateUserUI(user);
      showMainApp();
      console.log('✓ Auth UI updated and main app shown');
    } catch (error) {
      console.error('❌ Auth error:', error.message);
      hideAuthStatusBanner();
      updateUserUI(user);
      showAuthScreen();
      notifyError('Sign-in failed: ' + (error.message || 'Backend session exchange error'));
    }
  } else {
    currentUser = null;
    console.log('✗ Firebase Auth state changed - user signed out or not authenticated');
    updateUserUI(null);
    showAuthScreen();
    localStorage.removeItem('firebaseToken');
  }
});

// ========== UI UPDATE FUNCTIONS ==========
function updateUserUI(user) {
  const authInfo = document.getElementById('auth-info');
  if (!authInfo) return;
  
  if (user) {
    const initial = (user.displayName || user.email || 'U').charAt(0).toUpperCase();
    const fallbackAvatar = `data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='40' height='40'%3E%3Ccircle cx='20' cy='20' r='20' fill='%2300ff88'/%3E%3Ctext x='50%25' y='50%25' dominant-baseline='middle' text-anchor='middle' fill='%230a0e1a' font-size='18' font-weight='bold' font-family='JetBrains Mono'%3E${initial}%3C/text%3E%3C/svg%3E`;
    
    authInfo.innerHTML = `
      <div class="user-profile-container" style="display: flex; align-items: center; gap: 1rem;">
        <img src="${user.photoURL || fallbackAvatar}" 
             alt="${user.displayName || 'User'}" 
             class="user-avatar"
             style="width: 40px; height: 40px; border-radius: 50%; border: 2px solid var(--primary); box-shadow: 0 0 16px rgba(0,255,136,0.5); transition: transform 0.3s; cursor: pointer;"
             onmouseover="this.style.transform='scale(1.1) rotate(5deg)'"
             onmouseout="this.style.transform='scale(1) rotate(0deg)'"
             onerror="this.src='${fallbackAvatar}'">
        <div class="user-details" style="display: flex; flex-direction: column;">
          <span class="user-name" style="font-size: var(--text-sm); font-weight: 600; color: var(--text-primary);">${user.displayName || 'User'}</span>
          <span class="user-email" style="font-size: var(--text-xs); color: var(--text-tertiary);">${user.email}</span>
        </div>
        <button onclick="handleSignOut()" class="terminal-button-secondary" style="font-size: var(--text-xs); padding: 0.4rem 0.75rem; margin-left: 0.5rem;">
          <svg style="width: 14px; height: 14px; fill: currentColor; margin-right: 0.25rem;" viewBox="0 0 24 24">
            <path d="M17 7l-1.41 1.41L18.17 11H8v2h10.17l-2.58 2.58L17 17l5-5zM4 5h8V3H4c-1.1 0-2 .9-2 2v14c0 1.1.9 2 2 2h8v-2H4V5z"/>
          </svg>
          Sign Out
        </button>
      </div>
    `;
  } else {
    authInfo.innerHTML = '';
  }
}

function showMainApp() {
  console.log('🎯 showMainApp() called - hiding auth screen, showing story controls');
  const authScreen = document.getElementById('auth-screen');
  const storyControls = document.getElementById('story-controls');
  
  if (authScreen) {
    authScreen.classList.add('hidden');
    console.log('  ✓ auth-screen hidden');
  } else {
    console.warn('  ⚠️ auth-screen element not found!');
  }
  
  if (storyControls) {
    storyControls.classList.remove('hidden');
    console.log('  ✓ story-controls shown');
  } else {
    console.warn('  ⚠️ story-controls element not found!');
  }
}

function showAuthScreen() {
  document.getElementById('auth-screen')?.classList.remove('hidden');
  document.getElementById('story-controls')?.classList.add('hidden');
}

// ========== GOOGLE SIGN-IN ==========
async function startGoogleSignIn() {
  try {
    console.log('🔐 Starting Google Sign-In with popup (better for cookie restrictions)...');
    
    // Use POPUP mode - works better with modern browser cookie policies
    const result = await auth.signInWithPopup(googleProvider);
    const user = result.user;
    
    console.log('✓ Popup sign-in successful!');
    console.log('  Email:', user?.email);
    console.log('  Name:', user?.displayName);
    console.log('  Avatar:', user?.photoURL);
    
    // Do NOT show success yet — wait for backend token exchange
    // onAuthStateChanged will perform the exchange and then update UI.
    
  } catch (error) {
    console.error('✗ Sign-in error:', error);
    console.error('  Code:', error.code);
    console.error('  Message:', error.message);
    
    if (error.code === 'auth/popup-closed-by-user') {
      console.log('ℹ️ Sign-in cancelled by user');
    } else if (error.code === 'auth/popup-blocked') {
      console.error('⚠️ Popup was blocked by browser');
      notifyError('Pop-up blocked! Please allow pop-ups for this site and try again.');
    } else if (error.code === 'auth/cancelled-popup-request') {
      console.log('ℹ️ Multiple pop-up requests cancelled');
    } else if (error.code === 'auth/unauthorized-domain') {
      notifyError('Domain not authorized. Check Firebase Console settings.');
    } else {
      notifyError('Sign-in failed: ' + (error.message || 'Unknown error'));
    }
  }
}

// Provides a structured session object for the main app
async function signInWithGoogle() {
  const result = await auth.signInWithPopup(googleProvider);
  const user = result.user;

  console.log('✓ Sign-in successful!');
  console.log('  Email:', user.email);
  console.log('  Name:', user.displayName);
  console.log('  Avatar:', user.photoURL);

  const idToken = await user.getIdToken();
  const session = await exchangeFirebaseToken(idToken);

  const username = session.username || user.email || 'google_user';
  const displayName = session.displayName || user.displayName || username;
  const avatar = session.avatar || user.photoURL || null;
  const userId = session.userId || null;

  return { token: session.token, username, displayName, avatar, userId };
}

// ========== SIGN OUT ==========
async function handleSignOut() {
  if (!confirm('Are you sure you want to sign out?')) return;
    
  try {
    await auth.signOut();
    console.log('✓ Signed out successfully');
    notifySuccess('Signed out successfully');
  } catch (error) {
    console.error('✗ Sign-out error:', error);
    notifyError('Sign-out failed: ' + error.message);
  }
}

// ========== AUTH HEADERS FOR API CALLS ==========
async function getAuthHeaders() {
  if (!currentUser) {
    throw new Error('User not authenticated');
  }
  
  const token = await currentUser.getIdToken();
  return {
    'Authorization': `Bearer ${token}`,
    'Content-Type': 'application/json'
  };
}

// ========== INITIALIZE ON LOAD ==========
document.addEventListener('DOMContentLoaded', () => {
  initTheme();
  console.log('🔥 Firebase Auth ready');
  console.log('📧 Email selection enabled');
  console.log('🎨 Theme system ready');
  console.log('🔍 Checking for redirect sign-in result...');
  
  // Handle redirect sign-in completions
  auth.getRedirectResult()
    .then(async (result) => {
      console.log('🔍 Redirect result object:', result);
      console.log('🔍 Redirect result user:', result?.user);
      console.log('🔍 Redirect credential:', result?.credential);
      
      if (result && result.user) {
        console.log('👤 User from redirect:', result.user.email);
        const idToken = await result.user.getIdToken();
        const session = await exchangeFirebaseToken(idToken);
        try { window.dispatchEvent(new CustomEvent('firebase-auth-success', { detail: session })); } catch (_) {}
        updateUserUI(result.user);
        showMainApp();
        notifySuccess(`Welcome back, ${result.user.displayName || result.user.email.split('@')[0]}!`);
      } else {
        console.log('ℹ️ No user in redirect result');
        console.log('🔍 Current auth state:', auth.currentUser ? 'signed in' : 'signed out');
        // Check if there's a pending redirect
        const pendingRedirect = await auth.getRedirectResult().catch(() => null);
        console.log('🔍 Pending redirect check:', pendingRedirect);
      }
    })
    .catch(err => {
      console.error('❌ Redirect result error:', err);
      console.error('   Error code:', err.code);
      console.error('   Error message:', err.message);
      console.error('   Full error:', JSON.stringify(err, null, 2));
      hideAuthStatusBanner();
      
      // Common Firebase auth errors
      if (err.code === 'auth/unauthorized-domain') {
        notifyError('Domain not authorized. Add 127.0.0.1 to Firebase Console → Authentication → Settings → Authorized domains');
      } else if (err.code === 'auth/operation-not-allowed') {
        notifyError('Google sign-in not enabled in Firebase Console');
      } else {
        notifyError('Sign-in failed: ' + (err.message || err.code || 'Unknown redirect error'));
      }
    });
});

// Make functions globally available
window.startGoogleSignIn = startGoogleSignIn;
window.handleSignOut = handleSignOut;
window.toggleTheme = toggleTheme;
window.getAuthHeaders = getAuthHeaders;
window.signInWithGoogle = signInWithGoogle;
