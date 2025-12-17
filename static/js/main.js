/* --- 3. Authentication and Setup Logic --- */

// --- CONSTANTS ---
const API_BASE_URL = 'http://127.0.0.1:5000/api';
const MAX_RETRIES = 3;
const INITIAL_RETRY_DELAY = 1000; // 1 second
// AUTO-GENERATE IMAGE toggle persisted in localStorage
// Default changed to false so images are generated only when the user explicitly requests it.

// Image generation is manual: user edits the visual prompt and clicks GENERATE IMAGE.

// --- GLOBAL STATE ---
let state = {
    token: localStorage.getItem('authToken') || null,
    userId: localStorage.getItem('userId') || null,
    username: localStorage.getItem('username') || null,
    displayName: localStorage.getItem('displayName') || null,
    avatar: localStorage.getItem('avatar') || null,
    storyHistory: [],
    sceneCounter: 0,
    scenes: [],
    summaryBullets: [],
    initialPrompt: '',
    artStyle: 'photorealistic cinematic',
    currentSceneData: null, // Holds LLM output while user edits prompt
    pendingSceneId: null,   // If a narration is posted before image generation
    isGenerating: false
};

// --- DOM ELEMENTS ---
const authScreen = document.getElementById('auth-screen');
const storyControls = document.getElementById('story-controls');
const stagingArea = document.getElementById('staging-area');
const authInfo = document.getElementById('auth-info');
const storyboard = document.getElementById('storyboard');
const summaryList = document.getElementById('summary-list');
const startPromptInput = document.getElementById('start-prompt');
const artStyleSelect = document.getElementById('art-style');
const promptEditor = document.getElementById('image-prompt-editor');
const generatePromptBtn = document.getElementById('generate-prompt-btn'); // Note: This button ID doesn't exist in HTML, using 'start-btn'/'continue-btn' instead.
const generateImageBtn = document.getElementById('generate-image-btn');
const continueBtn = document.getElementById('continue-btn');
const loadingIndicator = document.getElementById('loading-indicator');
const loadingMessage = document.getElementById('loading-message');
const modalContainer = document.getElementById('modal-container');
const errorModal = document.getElementById('error-modal');
const errorMessageDisplay = document.getElementById('error-message');
const progressContainer = document.getElementById('progress-steps');
const progressLabel = document.getElementById('progress-step-label');
const progressMessage = document.getElementById('progress-message');

// --- UI UTILITIES ---

function showModal(id, message) {
    errorMessageDisplay.textContent = message;
    document.getElementById(id).classList.remove('hidden');
    modalContainer.classList.remove('hidden');
}

function hideModal(id) {
    document.getElementById(id).classList.add('hidden');
    if (id === 'error-modal') {
        modalContainer.classList.add('hidden');
    }
}

// Success modal helpers
function showSuccess(message) {
    const successModal = document.getElementById('success-modal');
    const successMessage = document.getElementById('success-message');
    if (!successModal || !successMessage) return;
    successMessage.textContent = message;
    successModal.classList.remove('hidden');
    modalContainer.classList.remove('hidden');
}

function hideSuccess() {
    const successModal = document.getElementById('success-modal');
    if (!successModal) return;
    successModal.classList.add('hidden');
    modalContainer.classList.add('hidden');
}

function setLoading(isLoading, message = 'Processing...') {
    state.isGenerating = isLoading;
    // Target specific buttons from the HTML structure
    const buttons = [
        document.getElementById('start-btn'), 
        generateImageBtn, 
        continueBtn, 
        document.getElementById('login-btn'), 
        document.getElementById('register-btn')
    ];
    
    buttons.forEach(btn => {
        if (btn) btn.disabled = isLoading;
    });
    
    if (isLoading) {
        loadingMessage.textContent = message;
        loadingIndicator.classList.remove('hidden');
    } else {
        loadingIndicator.classList.add('hidden');
        loadingMessage.textContent = '';
    }
}

function showProgress(step, total, message){
    if(!progressContainer) return;
    progressLabel.textContent = `${step}/${total}`;
    progressMessage.textContent = message || '';
    progressContainer.classList.remove('hidden');
}

function hideProgress(){
    if(!progressContainer) return;
    progressContainer.classList.add('hidden');
    progressLabel.textContent = '';
    progressMessage.textContent = '';
}

// --- CORE FETCH UTILITY (Handles all API communication with exponential backoff) ---

async function fetchWithRetry(url, options = {}, retries = MAX_RETRIES) {
    // Support a custom flag `silentAuth` on options to suppress the
    // interactive "Session expired" modal when a 401 happens during
    // automatic background checks (for example, loading a session on
    // page startup). Default is false (show modal).
    const silentAuth = options.silentAuth === true;
    // remove our custom flag so it doesn't get passed to fetch
    if ('silentAuth' in options) delete options.silentAuth;

    const token = state.token;
    if (token) {
        options.headers = {
            ...options.headers,
            'Authorization': `Bearer ${token}`,
        };
    }

    for (let i = 0; i < retries; i++) {
        try {
            // Add client-side timeout: 12 seconds for story generation, 20 for images
            const isStoryEndpoint = url.includes('/ai/generate-prompt');
            const timeoutMs = isStoryEndpoint ? 12000 : 20000;
            const controller = new AbortController();
            const timeoutId = setTimeout(() => controller.abort(), timeoutMs);
            
            const response = await fetch(url, { ...options, signal: controller.signal });
            clearTimeout(timeoutId);
            
            if (response.status === 401) {
                // Unauthorized: force logout. If this was a background/silent
                // request (silentAuth=true) we do not show the modal to avoid
                // alarming the user on page load — instead we quietly log out.
                if (!silentAuth) {
                    showModal('error-modal', 'Session expired or unauthorized. Please log in again.');
                }
                handleLogout();
                return; // Stop processing after logout initiation
            }
            
            // Read response as text first to handle empty/truncated responses
            const text = await response.text();
            
            if (!response.ok) {
                // Attempt to parse text for error message, otherwise show status
                let errorMsg = `HTTP Error ${response.status}`;
                try {
                    const json = JSON.parse(text);
                    const candidate = json?.error || json?.message || json;
                    errorMsg = typeof candidate === 'string' ? candidate : JSON.stringify(candidate);
                } catch (e) {
                    errorMsg = text || errorMsg;
                }
                throw new Error(`API call failed: ${errorMsg}`);
            }

            // Handle empty response bodies gracefully (e.g., from some POSTs)
            if (!text) return {}; 
            
            return JSON.parse(text);

        } catch (error) {
            if (i === retries - 1) {
                throw new Error(`Max retries reached. Failed to fetch from ${url}. Original error: ${error.message}`);
            }
            const delay = INITIAL_RETRY_DELAY * Math.pow(2, i);
            await new Promise(resolve => setTimeout(resolve, delay));
        }
    }
}

// --- AUTHENTICATION LOGIC ---

async function handleRegister() {
    const username = document.getElementById('auth-username').value;
    const password = document.getElementById('auth-password').value;
    setLoading(true, 'Registering user...');
    try {
        // Basic client-side validation to reduce round trips
        if (!username || username.trim().length < 3) {
            showModal('error-modal', 'Username must be at least 3 characters long.');
            setLoading(false);
            return;
        }
        if (!password || password.length < 6) {
            showModal('error-modal', 'Password must be at least 6 characters long.');
            setLoading(false);
            return;
        }

        const response = await fetchWithRetry(`${API_BASE_URL}/auth/register`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ username, password })
        });
        // Registration succeeded. Auto-login without showing an "error" modal.
        // Previously we showed the response in the error modal which incorrectly
        // presented success messages as system errors. Instead, auto-login silently
        // and surface errors only on failure.
        await handleLogin(username, password); // Auto-login after successful registration
    } catch (error) {
        showModal('error-modal', error.message);
    } finally {
        setLoading(false);
    }
}

async function handleLogin(usernameOverride, passwordOverride) {
    const username = usernameOverride || document.getElementById('auth-username').value;
    const password = passwordOverride || document.getElementById('auth-password').value;
    
    if (!username || !password) {
        showModal('error-modal', 'Please enter both username and password.');
        return;
    }

    if (username.trim().length < 3) {
        showModal('error-modal', 'Please provide a valid username.');
        return;
    }

    setLoading(true, 'Logging in...');
    try {
        const response = await fetchWithRetry(`${API_BASE_URL}/auth/login`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ username, password })
        });

        state.token = response.token;
        state.userId = response.user_id;
        state.username = response.username;
        
        localStorage.setItem('authToken', state.token);
        localStorage.setItem('userId', state.userId);
        localStorage.setItem('username', state.username);
        
        initializeApp();
    // Show a non-error success confirmation
    showSuccess('Logged in successfully.');
    } catch (error) {
        showModal('error-modal', error.message);
    } finally {
        setLoading(false);
    }
}

async function handleLogout() {
    if (!state.token) return;
    setLoading(true, 'Logging out...');
    try {
            // Sign out from Firebase if available
            if (typeof signOutFirebase === 'function') {
                await signOutFirebase();
            }
        
        // The backend handles token invalidation
        await fetchWithRetry(`${API_BASE_URL}/auth/logout`, { method: 'POST' });
    } catch (error) {
        // Log the error but proceed with client-side cleanup
        console.error("Logout API failed, proceeding with client-side cleanup:", error.message);
    }
    
    // Client-side cleanup
    localStorage.removeItem('authToken');
    localStorage.removeItem('userId');
    localStorage.removeItem('username');
        localStorage.removeItem('displayName');
        localStorage.removeItem('avatar');
    state.token = null;
    state.userId = null;
    state.username = null;
        state.displayName = null;
        state.avatar = null;
    
    // Reset UI to login state
    authInfo.innerHTML = '';
    authScreen.classList.remove('hidden');
    storyControls.classList.add('hidden');
    stagingArea.classList.add('hidden');
    storyboard.innerHTML = `<h2 class="text-xl font-bold border-b border-green-500/50 pb-2 mb-4 text-green-500">Scene History</h2>`;
    summaryList.innerHTML = '';
    setLoading(false);
    renderStoryControls(); // Reset buttons
}

// --- INITIALIZATION AND STATE LOADING ---

function updateHeader() {
    if (state.token && state.username) {
        // Show avatar and display name when available
        const displayName = state.displayName || localStorage.getItem('displayName') || state.username;
        const avatar = state.avatar || localStorage.getItem('avatar');
        authInfo.innerHTML = `
            <div style="display:flex; align-items:center; gap:10px">
                ${avatar ? `<img src="${avatar}" alt="avatar" style="width:28px;height:28px;border-radius:999px;object-fit:cover;">` : ''}
                <span class="text-green-500 mr-4">${displayName}</span>
                <button onclick="handleLogout()" class="terminal-button-secondary py-1 px-2 text-sm">Sign Out</button>
            </div>
        `;
    } else {
        authInfo.innerHTML = '';
    }
}

// Fetch and display provider status in header
async function loadProviderBanner(){
    try{
        const resp = await fetch(`${API_BASE_URL}/ai/status`);
        if(!resp.ok) return;
        const j = await resp.json();
        const banner = document.getElementById('provider-banner');
        if(banner){
            banner.textContent = `LLM:${j.llm_provider || 'unknown'} | IMG:${j.image_provider || 'unknown'} | mockFallback:${j.use_mock_fallback}`;
        }
    }catch(e){ console.debug('Provider banner fetch failed', e); }
}

async function loadStorySession() {
    setLoading(true, 'Loading session data...');
    try {
        // Use silentAuth to avoid showing a modal if the stored token is
        // invalid during automatic page load. In that case we want to
        // quietly return to the login screen rather than alarm the user.
        const data = await fetchWithRetry(`${API_BASE_URL}/story/load-session`, { method: 'GET', silentAuth: true });
        
        // Merge loaded data with state, ensuring arrays are arrays
        state = { 
            ...state, 
            ...data, 
            storyHistory: Array.isArray(data.storyHistory) ? data.storyHistory : [],
            scenes: Array.isArray(data.scenes) ? data.scenes : [],
            summaryBullets: Array.isArray(data.summaryBullets) ? data.summaryBullets : [],
            username: state.username || data.username || 'User' 
        };
        
        renderUIFromState();
    } catch (error) {
        showModal('error-modal', `Error loading session: ${error.message}. Starting new session.`);
        // Fallback to initial state if loading fails
        state.storyHistory = [];
        state.scenes = [];
        state.sceneCounter = 0;
        state.summaryBullets = [];
        renderUIFromState();
    } finally {
        setLoading(false);
    }
}

function initializeApp() {
    console.log('🚀 initializeApp() called, token:', state.token ? 'present' : 'missing');
    updateHeader();
    if (state.token) {
        console.log('  → Hiding auth screen, showing story controls');
        authScreen.classList.add('hidden');
        storyControls.classList.remove('hidden');
        loadStorySession();
    } else {
        console.log('  → Showing auth screen, hiding story controls');
        authScreen.classList.remove('hidden');
        storyControls.classList.add('hidden');
    }
}

// Bridge: update state when Firebase completes auth
window.addEventListener('firebase-auth-success', (e) => {
    console.log('🔥 firebase-auth-success event received!', e.detail);
    const info = (e && e.detail) || {};
    state.token = info.token || localStorage.getItem('authToken') || 'firebase-token-' + Date.now();
    state.username = info.username || localStorage.getItem('username') || state.username || 'User';
    state.displayName = info.displayName || localStorage.getItem('displayName') || state.displayName;
    state.avatar = info.avatar || localStorage.getItem('avatar') || state.avatar;
    state.userId = info.userId || localStorage.getItem('userId') || state.userId || 'firebase-user';
    
    console.log('  → Updated state:', { token: state.token, username: state.username, displayName: state.displayName });
    
    localStorage.setItem('authToken', state.token);
    localStorage.setItem('username', state.username);
    localStorage.setItem('userId', state.userId);
    if (state.displayName) localStorage.setItem('displayName', state.displayName);
    if (state.avatar) localStorage.setItem('avatar', state.avatar);
    
    updateHeader();
    initializeApp();
    // Close any error modals first before showing success
    hideModal('error-modal');
    setTimeout(() => {
        showSuccess('✓ Signed in with Google!');
    }, 300);
});

// --- RUN INITIALIZATION ---
window.onload = initializeApp;


/* --- 4. Core Application Logic (AI Generation & UI Control) --- */

// --- DATA SAVING ---

async function saveStorySession() {
    if (!state.token) return;

    // Prepare a clean copy of state data for the backend save
    const dataToSave = {
        storyHistory: state.storyHistory.slice(-5).filter(s => typeof s === 'string'), // Only save the last 5 for context, ensuring strings
        sceneCounter: state.sceneCounter,
        scenes: state.scenes.map(scene => ({
            ...scene,
            // Ensure the object has only primitive types and clean arrays
            summaryBullets: Array.isArray(scene.summaryBullets) ? scene.summaryBullets.filter(s => typeof s === 'string') : [],
        })),
        summaryBullets: state.summaryBullets.filter(s => typeof s === 'string'),
        initialPrompt: state.initialPrompt,
        artStyle: state.artStyle,
    };

    try {
        // Use JSON.parse(JSON.stringify) for deep sanitization (safety measure)
        const payload = JSON.parse(JSON.stringify(dataToSave));
        
        await fetchWithRetry(`${API_BASE_URL}/story/save-session`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        });
        console.log('Session saved successfully.');
    } catch (error) {
        console.error('Error saving to backend:', error.message);
        // We show an error, but let the user continue
    }
}


// --- AI API CALLS VIA BACKEND ---

async function generateStoryData(prompt, artStyle) {
    console.log('generateStoryData called with prompt:', prompt);
    
    const systemPrompt = `You are an expert narrative and visual storyteller. When given a user's idea, first generate an immersive, cinematic story from that idea, then create a detailed image prompt from the story you generated. Output MUST be valid JSON with these fields:

1. 'narrative': Vivid 150-200 word story paragraph generated from the user's idea with:
   - Sensory details (sight, sound, touch, smell, taste)
   - Clear characters/robots with physical descriptions
   - Dynamic action showing tension and movement
   - Cinematic pacing and descriptive language
   - Meaningful plot advancement

2. 'image_prompt': Highly detailed visual instruction (100-150 words) generated from YOUR story narrative:
   - SPECIFIC visual elements from YOUR narrative (exact robot descriptions, clothing, features)
   - Camera angle, lighting, composition details
   - Environmental and atmospheric specifics
   - Art style: ${artStyle}
   - MUST perfectly match YOUR narrative characters and action
   - Use descriptive adjectives: dramatic, cinematic, photorealistic, detailed

3. 'summary_point': One concise sentence (max 20 words) of the scene's key event from YOUR story.`;

    const contents = [{ 
        role: "user", 
        parts: [{ 
            text: `Story context (last ${state.storyHistory.length} scenes): [${state.storyHistory.map(s => `"${s}"`).join(', ')}]\n\nContinue the story from this point, focusing on the next action or setting change. Prompt: ${prompt}`
        }] 
    }];

    const aiPayload = {
        contents: contents,
        systemInstruction: { parts: [{ text: systemPrompt }] },
        generationConfig: {
            responseMimeType: "application/json",
            temperature: 0.8,
            topP: 0.95,
            responseSchema: {
                type: "OBJECT",
                properties: {
                    "narrative": { "type": "STRING", "description": "Vivid story paragraph with sensory details and character actions" },
                    "image_prompt": { "type": "STRING", "description": "Detailed visual prompt matching narrative exactly" },
                    "summary_point": { "type": "STRING", "description": "Concise event summary" }
                },
                required: ["narrative", "image_prompt", "summary_point"]
            }
        }
    };
    
    console.log('Sending request to backend...');
    const response = await fetchWithRetry(`${API_BASE_URL}/ai/generate-prompt`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ payload: aiPayload })
    });
    console.log('Received response from backend:', response);

    // Update provider banner with whether a real LLM was used for this
    // response (backend sets `used_real_llm` true/false when available).
    try {
        const banner = document.getElementById('provider-banner');
        if (banner && typeof response?.used_real_llm !== 'undefined') {
            // Remove any existing realLLM segment and append the new one
            banner.textContent = banner.textContent.replace(/\s*\|\s*realLLM:\s*(yes|no)/i, '');
            banner.textContent = `${banner.textContent} | realLLM:${response.used_real_llm ? 'yes' : 'no'}`;
        }
    } catch (e) {
        console.debug('Failed to update provider-banner with used_real_llm:', e);
    }

    // Prefer a server-provided normalized object when available. This
    // avoids brittle client-side parsing when upstream LLMs wrap JSON in
    // markdown/code fences or add commentary.
    if (response?.normalized_candidate) {
        console.log('Using normalized_candidate from backend');
        return response.normalized_candidate;
    }

    // The backend may still return the older Gemini-shaped response; fall
    // back to parsing the candidates parts as before.
    console.log('Attempting to parse candidates structure');
    const jsonString = response?.candidates?.[0]?.content?.parts?.[0]?.text;
    if (!jsonString) {
        console.error('No valid content in response:', response);
        throw new Error("LLM returned an empty or invalid content part. Please check your connection and try again.");
    }
    return JSON.parse(jsonString);
}

async function generateImage(prompt, artStyle, count = 1) {
    // Request `count` images in a single backend call when supported.
    // Enhance the prompt with quality settings for better image generation
    const enhancedPrompt = `${prompt}, style: ${artStyle}, professional quality, cinematic lighting, high detail, award-winning, intricate details`;
    
    const aiPayload = {
        instances: [{ prompt: enhancedPrompt }],
        parameters: { 
            sampleCount: count,
            aspectRatio: "16:9",
            guidanceScale: 7.5,
            seed: Math.floor(Math.random() * 10000)
        }
    };

    const response = await fetchWithRetry(`${API_BASE_URL}/ai/generate-image`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ payload: aiPayload })
    });

    // Expect an array of predictions; normalize to an array of base64 strings.
    let base64List = [];
    try {
        if (Array.isArray(response?.predictions) && response.predictions.length > 0) {
            base64List = response.predictions
                .map(p => p?.bytesBase64Encoded)
                .filter(Boolean);
        } else if (response?.predictions?.[0]?.bytesBase64Encoded) {
            base64List = [response.predictions[0].bytesBase64Encoded];
        }
    } catch (e) {
        console.debug('Failed to normalize image response:', e);
    }

    // If no images returned, try a single fallback image request
    if (!base64List.length) {
        console.warn("Image model failed to return image data. Attempting fallback image generation.");
        const fallbackPrompt = "A serene, abstract landscape with geometric shapes and neon colors, digital art, 16:9 aspect ratio.";
        const fallbackPayload = {
            instances: [{ prompt: fallbackPrompt }],
            parameters: { sampleCount: 1, aspectRatio: "16:9" }
        };

        const fallbackResponse = await fetchWithRetry(`${API_BASE_URL}/ai/generate-image`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ payload: fallbackPayload })
        });

        const fallbackBase64 = fallbackResponse?.predictions?.[0]?.bytesBase64Encoded;
        if (!fallbackBase64) {
            throw new Error("Image generation failed and fallback also failed.");
        }
        return [fallbackBase64];
    }

    return base64List;
}

// --- SCENE RENDERING ---

function renderScene(scene) {
    const hasImage = !!scene.imageUrl;
    const imageBlock = hasImage ? `
                <div class="scene-image-wrapper">
                    <img id="scene-img-${scene.id}" src="${scene.imageUrl}" alt="Scene ${scene.id} Visual" class="w-full rounded-lg shadow-xl border border-cyan-500/50" style="height:220px; object-fit:cover;">
                    <button class="download-btn" title="Download image" onclick="downloadImage(${scene.id})">⇩</button>
                </div>
            ` : `
                <div id="scene-placeholder-${scene.id}" class="w-full h-[220px] rounded-lg border border-cyan-500/40 flex items-center justify-center text-green-200 bg-gray-900/50">
                    Image pending — generate when ready
                </div>
            `;

    const sceneHtml = `
        <div id="scene-${scene.id}" class="scene-card">
            <h3 class="text-xl font-bold text-cyan-400 mb-3">Scene ${scene.id}: ${scene.artStyle}</h3>
            
            <div class="mb-4">
                ${imageBlock}
            </div>

            <p class="text-green-200 mb-2">${scene.narrative}</p>
            <div class="text-sm mt-3 border-t border-green-500/30 pt-3">
                <p class="prompt-label">VISUAL PROMPT USED:</p>
                <code class="block text-xs bg-gray-700 p-2 rounded">${scene.imagePrompt}</code>
            </div>
        </div>
    `;
    // Prepend new scene to the top of the storyboard
    storyboard.insertAdjacentHTML('afterbegin', sceneHtml);
}

// Trigger a download of the rendered scene image by scene id
function downloadImage(sceneId) {
    try {
        const img = document.getElementById(`scene-img-${sceneId}`);
        if (!img) return showModal('error-modal', 'Image not available for download.');

        const src = img.src;
        // If the image is a data URL, download directly. Otherwise, fetch it and convert to blob.
        if (src.startsWith('data:')) {
            const a = document.createElement('a');
            a.href = src;
            a.download = `scene-${sceneId}.png`;
            document.body.appendChild(a);
            a.click();
            a.remove();
            return;
        }

        // For remote URLs (e.g., picsum), fetch as blob then download
        fetch(src)
            .then(res => res.blob())
            .then(blob => {
                const url = URL.createObjectURL(blob);
                const a = document.createElement('a');
                a.href = url;
                a.download = `scene-${sceneId}.png`;
                document.body.appendChild(a);
                a.click();
                a.remove();
                URL.revokeObjectURL(url);
            })
            .catch(err => showModal('error-modal', `Failed to download image: ${err.message}`));
    } catch (e) {
        showModal('error-modal', `Failed to download image: ${e.message}`);
    }
}

function renderSummary() {
    // Render full narratives (most recent first) followed by concise summary bullets
    const narrativesHtml = (Array.isArray(state.storyHistory) ? state.storyHistory.slice().reverse() : [])
        .map(n => `<div class="text-sm text-green-400 mb-2">${escapeHtml(n)}</div>`)
        .join('');

    const bulletsHtml = state.summaryBullets
        .map(point => `<li class="text-green-300 before:content-['>'] before:text-green-500 before:mr-2">${escapeHtml(point)}</li>`)
        .join('');

    summaryList.innerHTML = `${narrativesHtml}<ul style="list-style:none; padding-left:0;">${bulletsHtml}</ul>`;
}

// Update an existing scene's image in the DOM when it becomes available
function updateSceneImage(sceneId, imageUrl) {
    try {
        const imgId = `scene-img-${sceneId}`;
        let img = document.getElementById(imgId);
        const placeholder = document.getElementById(`scene-placeholder-${sceneId}`);
        if (!img) {
            img = document.createElement('img');
            img.id = imgId;
            img.className = 'w-full rounded-lg shadow-xl border border-cyan-500/50';
            img.style.height = '220px';
            img.style.objectFit = 'cover';
            if (placeholder && placeholder.parentElement) {
                placeholder.parentElement.replaceChild(img, placeholder);
            }
        }
        img.src = imageUrl;
    } catch (e) {
        console.debug('Failed to update scene image', e);
    }
}

// Small helper to escape HTML when injecting text into the DOM
function escapeHtml(str){
    if(!str && str!==0) return '';
    return String(str)
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;')
        .replace(/'/g, '&#039;');
}

function renderStoryControls() {
    // Show the story controls and hide the staging area initially
    storyControls.classList.remove('hidden');
    stagingArea.classList.add('hidden');

    // If a story is already in progress, show the 'Continue' button
    if (state.scenes.length > 0) {
        document.getElementById('new-story-inputs').classList.add('hidden');
        continueBtn.classList.remove('hidden');
    } else {
        // For a brand new story
        document.getElementById('new-story-inputs').classList.remove('hidden');
        continueBtn.classList.add('hidden');
    }
}

function renderUIFromState() {
    try {
        // Clear current content, except the main heading
        if (storyboard) {
            storyboard.innerHTML = `<h2 class="text-xl font-bold border-b border-green-500/50 pb-2 mb-4 text-green-500">Scene History</h2>`;
        }
        
        // Render all loaded scenes
        if (state.scenes && Array.isArray(state.scenes)) {
            state.scenes.forEach(renderScene);
        }
        
        renderSummary();
        renderStoryControls();
        
        // Set input values
        const promptInput = document.getElementById('start-prompt');
        const artStyleSelect = document.getElementById('art-style');
        if (promptInput) promptInput.value = state.initialPrompt || '';
        if (artStyleSelect) artStyleSelect.value = state.artStyle || 'photorealistic cinematic';
        
        console.log('✓ UI rendered from state');
    } catch (err) {
        console.error('Error in renderUIFromState:', err);
        // Don't fail the whole UI update if rendering fails
    }
}

// --- EVENT HANDLERS ---

async function handleInitialGeneration() {
    const initialPrompt = startPromptInput.value.trim();
    const artStyle = artStyleSelect.value;

    if (!initialPrompt) {
        showModal('error-modal', 'Please enter a starting idea for your story.');
        return;
    }

    // Reset state for a new story
    state.initialPrompt = initialPrompt;
    state.artStyle = artStyle;
    state.storyHistory = [];
    state.scenes = [];
    state.sceneCounter = 0;
    state.summaryBullets = [];
    
    // Start the LLM-driven continuation pipeline (show staging for user review)
    await handleStoryGeneration(`Generate a story from this idea: ${state.initialPrompt}`);
}


async function handleStoryGeneration(prompt = 'Continue the story.') {
    if (state.isGenerating) return;
    setLoading(true, 'Generating narrative...');
    showProgress(1,2,'Generating narrative...');
    
    try {
        console.log('Generating story data for prompt:', prompt);
        const result = await generateStoryData(prompt, state.artStyle);
        console.log('Received story data:', result);
        
        // Ensure we have valid data with fallbacks
        const narrative = result.narrative || 'No narrative generated. Please try again.';
        const imagePrompt = result.image_prompt || `${prompt} -- ${state.artStyle}`;
        const summaryPoint = result.summary_point || narrative.slice(0,140);

        // Store in staging area for user review - DON'T add to story history yet
        state.currentSceneData = { 
            narrative, 
            image_prompt: imagePrompt, 
            summary_point: summaryPoint 
        };
        
        // Show in staging area for review and editing
        const narrativeDisplay = document.getElementById('staging-narrative');
        const promptEditor = document.getElementById('image-prompt-editor');
        
        if (narrativeDisplay) narrativeDisplay.textContent = narrative;
        if (promptEditor) promptEditor.value = imagePrompt;
        
        // Show staging area, hide story controls
        stagingArea.classList.remove('hidden');
        storyControls.classList.add('hidden');
        
        console.log('✓ Narration ready in staging area. User can now review and edit visual prompt.');
        
    } catch (error) {
        console.error('Story generation error:', error);
    } finally {
        setLoading(false);
        hideProgress();
    }
}

// Post the generated narration to the storyboard before generating the image.
// This lets the user see the story text immediately while keeping image generation optional.
async function handlePostNarration() {
    if (!state.currentSceneData) {
        showModal('error-modal', 'No narration to post yet. Generate a story first.');
        return;
    }

    const narrative = state.currentSceneData.narrative || 'Narrative pending.';
    const imagePrompt = state.currentSceneData.image_prompt || (promptEditor ? promptEditor.value : '');
    const summaryPoint = state.currentSceneData.summary_point || narrative.slice(0, 120);

    state.sceneCounter++;
    const newScene = {
        id: state.sceneCounter,
        narrative,
        imagePrompt,
        imageUrl: null,
        summaryPoint,
        artStyle: state.artStyle,
    };

    // Track this scene so we can attach the image once generated.
    state.pendingSceneId = newScene.id;

    // Update state collections
    state.storyHistory.push(newScene.narrative);
    state.summaryBullets.push(newScene.summaryPoint);
    state.scenes.unshift(newScene);

    // Render immediately
    renderScene(newScene);
    renderSummary();

    try {
        await saveStorySession();
    } catch (e) {
        console.debug('Post narration save failed:', e);
    }

    // Keep staging area visible so user can still generate the image
    const genBtn = document.getElementById('generate-image-btn');
    if (genBtn) genBtn.disabled = false;
}


async function handleImageGeneration() {
    if (state.isGenerating || !state.currentSceneData) return;
    // Use async background job to reduce perceived latency: enqueue a job,
    // show the preview (already present), then poll for the full-res result.
    setLoading(true, 'Enqueuing image generation job...');
    const customPrompt = promptEditor.value.trim();
    const artStyle = artStyleSelect.value;

    if (!customPrompt) {
        showModal('error-modal', 'The Visual Prompt cannot be empty. Please edit it or go back.');
        setLoading(false);
        return;
    }

    // Helper: enqueue async job
    async function enqueueAsyncJob(payload) {
        const resp = await fetchWithRetry(`${API_BASE_URL}/ai/generate-image-async`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ payload })
        });
        return resp && resp.job_id;
    }

    // Helper: poll job status until done/error or timeout
    async function pollJob(jobId, interval = 2000, timeout = 120000) {
        const start = Date.now();
        while (Date.now() - start < timeout) {
            try {
                const j = await fetchWithRetry(`${API_BASE_URL}/ai/generate-image-job/${jobId}`, { method: 'GET' });
                if (!j) {
                    await new Promise(r => setTimeout(r, interval));
                    continue;
                }
                if (j.status === 'done') return j.result;
                if (j.status === 'error') throw new Error(j.result?.error || 'Async job failed');
            } catch (e) {
                // Continue polling unless timeout reached; break on unauthorized
                if (e.message && e.message.toLowerCase().includes('unauthorized')) throw e;
            }
            await new Promise(r => setTimeout(r, interval));
        }
        throw new Error('Image generation timed out. Try again or generate fewer images.');
    }

    try {
        // Build payload similar to synchronous call. If we have a pending scene
        // (narration already posted), request just 1 image to attach to it.
        const desiredCount = state.pendingSceneId ? 1 : 3;
        const aiPayload = {
            instances: [{ prompt: `${customPrompt}, in the style of ${artStyle}` }],
            parameters: { sampleCount: desiredCount, aspectRatio: '16:9' }
        };

        // Enqueue background job
        const jobId = await enqueueAsyncJob(aiPayload);
        if (!jobId) throw new Error('Failed to enqueue image job');

        showProgress(0, 1, 'Image job queued — awaiting full-resolution result...');

        // Poll for completion. If it succeeds, job.result should include file_urls
        let result = null;
        try {
            result = await pollJob(jobId, 2000, 120000);
        } catch (pollErr) {
            // If polling fails (timeout or error), fall back to synchronous generation
            console.debug('Async poll failed or timed out, falling back to synchronous generation:', pollErr);
            // Attempt a synchronous fallback to avoid leaving the user without images
            const base64List = await generateImage(customPrompt, artStyle, desiredCount);
            result = { files: [], file_urls: [] };
            if (Array.isArray(base64List) && base64List.length) {
                // convert returned base64 images to data URLs in file_urls for rendering
                result.file_urls = base64List.map(b64 => `data:image/png;base64,${b64}`);
            }
        }

        // If result has file_urls, render them as scenes
        const fileUrls = result?.file_urls || [];
        if (!fileUrls.length) throw new Error('No images available from async job or fallback.');

        // If a narration was already posted, attach the first image to that scene.
        if (state.pendingSceneId) {
            const targetId = state.pendingSceneId;
            const targetIndex = state.scenes.findIndex(s => s.id === targetId);
            if (targetIndex !== -1) {
                const updated = { ...state.scenes[targetIndex] };
                updated.imageUrl = fileUrls[0];
                updated.imagePrompt = customPrompt;
                updated.summaryPoint = state.currentSceneData?.summary_point || updated.summaryPoint;
                updated.narrative = state.currentSceneData?.narrative || updated.narrative;
                state.scenes[targetIndex] = updated;
            }
            state.pendingSceneId = null;
            state.currentSceneData = null;
            await saveStorySession();
            renderUIFromState();
        } else {
            for (let i = 0; i < fileUrls.length; i++) {
                showProgress(i + 1, fileUrls.length, `Rendering image ${i + 1} of ${fileUrls.length}...`);
                const imageUrl = fileUrls[i];
                state.sceneCounter++;
                const newScene = {
                    id: state.sceneCounter,
                    narrative: state.currentSceneData.narrative,
                    imagePrompt: customPrompt,
                    imageUrl: imageUrl,
                    summaryPoint: state.currentSceneData.summary_point,
                    artStyle: artStyle,
                };

                state.storyHistory.push(newScene.narrative);
                state.summaryBullets.push(newScene.summaryPoint);
                state.scenes.unshift(newScene);
                renderScene(newScene);
            }

            state.currentSceneData = null;
            await saveStorySession();
            renderUIFromState();
        }

    } catch (error) {
        showModal('error-modal', `Image generation failed. ${error.message}`);
    } finally {
        setLoading(false);
        stagingArea.classList.add('hidden');
        storyControls.classList.remove('hidden');
        renderStoryControls();
        hideProgress();
    }
}

// Generate an image for a specific scene (used when we already showed the narrative)
async function generateImageForScene(sceneId, prompt, artStyle) {
    setLoading(true, 'Generating image...');
    try {
        const base64List = await generateImage(prompt, artStyle, 1);
        const imageUrl = `data:image/png;base64,${base64List[0]}`;

        // Update state
        const scene = state.scenes.find(s => s.id === sceneId);
        if (scene) {
            scene.imageUrl = imageUrl;
            scene.pending = false;
        }
        updateSceneImage(sceneId, imageUrl);
    } catch (err) {
        showModal('error-modal', `Image generation failed: ${err.message}`);
    } finally {
        setLoading(false);
    }
}

// Generate an image directly from the user's initial idea without calling the LLM.
// This satisfies the use-case: "image on the basis of user idea" where the
// user wants a visual generated straight from their input.
async function handleGenerateImageFromIdea() {
    if (state.isGenerating) return;

    const idea = startPromptInput.value.trim();
    const artStyle = artStyleSelect.value;

    if (!idea) {
        showModal('error-modal', 'Please enter an idea in the input box to generate an image.');
        return;
    }

    setLoading(true, 'Generating image from your idea...');
    showProgress(1,1,'Generating image from idea...');

    try {
        // First, ask the LLM to craft a narrative + visual prompt from the raw idea.
        // This ensures the displayed story text matches the generated image.
        const storyData = await generateStoryData(`Generate a story from this idea: ${idea}`, artStyle);
        const narrative = storyData?.narrative || `Image generated from idea: ${idea}`;
        const imagePrompt = storyData?.image_prompt || `${idea}, in the style of ${artStyle}`;
        const summaryPoint = storyData?.summary_point || `Visualized idea: ${idea}`;

        // Then, generate the image using the refined visual prompt.
        const base64List = await generateImage(imagePrompt, artStyle, 1);
        const imageUrl = `data:image/png;base64,${base64List[0]}`;

        // Build the scene with the LLM narrative and refined prompt.
        state.sceneCounter++;
        const newScene = {
            id: state.sceneCounter,
            narrative: narrative,
            imagePrompt: imagePrompt,
            imageUrl: imageUrl,
            summaryPoint: summaryPoint,
            artStyle: artStyle,
        };

        // Update State
        state.storyHistory.push(newScene.narrative);
        state.summaryBullets.push(newScene.summaryPoint);
        state.scenes.unshift(newScene);

        // Save and render
        await saveStorySession();
        renderUIFromState();

    } catch (error) {
        showModal('error-modal', `Failed to generate image from idea: ${error.message}`);
    } finally {
        setLoading(false);
        hideProgress();
    }
}

// --- INITIALIZE EVENT LISTENERS ---
document.addEventListener('DOMContentLoaded', () => {
    // Attach top-level handlers to buttons that exist on page load
    const startBtn = document.getElementById('start-btn');
    if (startBtn) startBtn.onclick = handleInitialGeneration;
    
    if (generateImageBtn) generateImageBtn.onclick = handleImageGeneration;
    const genFromIdeaBtn = document.getElementById('generate-from-idea-btn');
    if (genFromIdeaBtn) genFromIdeaBtn.onclick = handleGenerateImageFromIdea;
    if (continueBtn) continueBtn.onclick = () => handleStoryGeneration(); // Continuation logic
    
    // Auth buttons
    document.getElementById('login-btn').onclick = handleLogin;
    document.getElementById('register-btn').onclick = handleRegister;
    
    // Google Sign-In button
    const googleSignInBtn = document.getElementById('google-signin-btn');
    if (googleSignInBtn && typeof window.startGoogleSignIn === 'function') {
        googleSignInBtn.onclick = window.startGoogleSignIn;
    }
    
    // Wire up the in-UI AUTO_GENERATE_IMAGE toggle (persists to localStorage)
    try {
        const autoToggle = document.getElementById('auto-gen-toggle');
        if (autoToggle) {
            // Initialize checked state from localStorage (default false)
            const val = localStorage.getItem('AUTO_GENERATE_IMAGE') === 'true';
            autoToggle.checked = !!val;
            autoToggle.addEventListener('change', (e) => {
                try {
                    localStorage.setItem('AUTO_GENERATE_IMAGE', e.target.checked ? 'true' : 'false');
                    // Move the thumb for the custom toggle UI
                    const thumb = document.getElementById('auto-gen-thumb');
                    if (thumb) thumb.style.left = e.target.checked ? '24px' : '4px';
                    const track = document.getElementById('auto-gen-track');
                    if (track) track.style.background = e.target.checked ? 'linear-gradient(90deg,var(--accent),#2de6a8)' : 'rgba(255,255,255,0.04)';
                    // Show a toast for subtle feedback
                    showToast(`Auto-generate ${e.target.checked ? 'enabled' : 'disabled'}`, 'info');
                } catch (err) {
                    console.debug('Failed to persist AUTO_GENERATE_IMAGE:', err);
                }
            });
        }
    } catch (err) {
        console.debug('AUTO_GENERATE_IMAGE UI wiring failed', err);
    }
    
    // no auto-generate toggle: generation is manual by default
    // Load provider banner info
    loadProviderBanner();
    // Wire cache admin button
    const cacheBtn = document.getElementById('cache-btn');
    if (cacheBtn) cacheBtn.onclick = showCacheModal;
});

// --- Toast helper ---
function showToast(message, level = 'info', timeout = 3000) {
    try {
        let container = document.getElementById('toast-container');
        if (!container) {
            container = document.createElement('div');
            container.id = 'toast-container';
            container.style.position = 'fixed';
            container.style.right = '20px';
            container.style.bottom = '24px';
            container.style.display = 'flex';
            container.style.flexDirection = 'column';
            container.style.gap = '10px';
            container.style.zIndex = 9999;
            document.body.appendChild(container);
        }

        const toast = document.createElement('div');
        toast.textContent = message;
    toast.style.padding = '12px 16px';
    toast.style.borderRadius = '12px';
    toast.style.minWidth = '220px';
    toast.style.boxShadow = '0 18px 50px rgba(2,6,10,0.6)';
    toast.style.color = '#081418';
    toast.style.fontWeight = '600';
    toast.style.background = level === 'error' ? 'linear-gradient(90deg,#ff9c9c,#ff6b6b)' : 'linear-gradient(90deg,var(--accent),var(--accent-2))';
        toast.style.opacity = '0';
        toast.style.transform = 'translateY(8px)';
        toast.style.transition = 'opacity .18s ease, transform .18s ease';

        container.appendChild(toast);
        // animate in
        requestAnimationFrame(() => {
            toast.style.opacity = '1';
            toast.style.transform = 'translateY(0)';
        });

        setTimeout(() => {
            toast.style.opacity = '0';
            toast.style.transform = 'translateY(8px)';
            setTimeout(() => { toast.remove(); }, 250);
        }, timeout);
    } catch (e) {
        console.debug('showToast failed', e);
    }
}

// --- Cache Admin UI ---
function showCacheModal() {
    const cacheModal = document.getElementById('cache-modal');
    if (!cacheModal) return;
    cacheModal.classList.remove('hidden');
    modalContainer.classList.remove('hidden');
    loadCacheList();
}

function hideCacheModal() {
    const cacheModal = document.getElementById('cache-modal');
    if (!cacheModal) return;
    cacheModal.classList.add('hidden');
    modalContainer.classList.add('hidden');
}

async function loadCacheList() {
    try {
        const resp = await fetchWithRetry(`${API_BASE_URL}/ai/cache/list`, { method: 'GET' });
        const listDiv = document.getElementById('cache-list');
        if (!listDiv) return;
        const entries = resp?.entries || [];
        if (entries.length === 0) {
            listDiv.innerHTML = '<div class="text-sm text-green-300">No cache entries found.</div>';
            return;
        }
        const html = entries.map(e => {
            const ts = e.ts ? new Date(e.ts * 1000).toLocaleString() : 'n/a';
            const filesHtml = (e.files || []).map(f => `<a class="text-xs text-cyan-200" href="/static/uploads/${f}" target="_blank">${f}</a>`).join('<br>');
            return `
                <div class="mb-4 p-3 rounded border border-cyan-800" style="background:rgba(0,0,0,0.35)">
                    <div class="flex items-center justify-between">
                        <div>
                            <div class="text-sm text-cyan-100 font-semibold">Key: ${e.key}</div>
                            <div class="text-xs text-green-300">Prompt: ${escapeHtml(e.prompt || '')}</div>
                            <div class="text-xs text-green-500">ts: ${ts}</div>
                        </div>
                        <div style="display:flex; flex-direction:column; gap:.4rem; align-items:flex-end">
                            <button class="terminal-button-secondary" onclick="invalidateCacheKey('${e.key}')">Delete</button>
                        </div>
                    </div>
                    <div style="margin-top:.6rem" class="text-xs">${filesHtml}</div>
                </div>
            `;
        }).join('');
        listDiv.innerHTML = html;
    } catch (err) {
        showModal('error-modal', `Failed to load cache list: ${err.message}`);
    }
}

async function invalidateCacheKey(key) {
    if (!confirm('Delete cache entry and files for key ' + key + '?')) return;
    try {
        const resp = await fetchWithRetry(`${API_BASE_URL}/ai/cache/invalidate`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ key })
        });
        if (resp && resp.success) {
            showToast('Cache entry removed', 'info');
            loadCacheList();
        } else {
            showModal('error-modal', `Failed to remove cache entry: ${JSON.stringify(resp || {})}`);
        }
    } catch (err) {
        showModal('error-modal', `Failed to remove cache entry: ${err.message}`);
    }
}

// Expose functions to window for inline event handlers
window.handleLogout = handleLogout;
window.invalidateCacheKey = invalidateCacheKey;