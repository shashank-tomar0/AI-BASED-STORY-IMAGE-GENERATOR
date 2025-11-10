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
    storyHistory: [],
    sceneCounter: 0,
    scenes: [],
    summaryBullets: [],
    initialPrompt: '',
    artStyle: 'photorealistic cinematic',
    currentSceneData: null, // Holds LLM output while user edits prompt
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
            const response = await fetch(url, options);
            
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
                    errorMsg = json.error || errorMsg;
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
    state.token = null;
    state.userId = null;
    state.username = null;
    
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
        authInfo.innerHTML = `
            <span class="text-green-500 mr-4">User: ${state.username}</span>
            <button onclick="handleLogout()" class="terminal-button-secondary py-1 px-2 text-sm">Sign Out</button>
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
    updateHeader();
    if (state.token) {
        authScreen.classList.add('hidden');
        storyControls.classList.remove('hidden');
        loadStorySession();
    } else {
        authScreen.classList.remove('hidden');
        storyControls.classList.add('hidden');
    }
}

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
    const systemPrompt = `You are a creative narrative generator. Your task is to continue the story based on the context provided. The output MUST be a single, valid JSON object.
        1. 'narrative': A new paragraph continuing the story. Keep it focused on a single scene or moment.
        2. 'image_prompt': A single, highly detailed, descriptive visual prompt suitable for a text-to-image model (like Midjourney or Imagen) that captures the main action and atmosphere of the 'narrative' paragraph. The style should be included in the prompt, focusing on '${artStyle}'.
        3. 'summary_point': A single, concise, new bullet point summarizing the key event of the new 'narrative'.`;

    const contents = [{ 
        role: "user", 
        parts: [{ 
            text: `Story context (last ${state.storyHistory.length} scenes): ${JSON.stringify(state.storyHistory)}\n\nContinue the story from this point, focusing on the next action or setting change. Prompt: ${prompt}`
        }] 
    }];

    const aiPayload = {
        contents: contents,
        systemInstruction: { parts: [{ text: systemPrompt }] },
        generationConfig: {
            responseMimeType: "application/json",
            responseSchema: {
                type: "OBJECT",
                properties: {
                    "narrative": { "type": "STRING" },
                    "image_prompt": { "type": "STRING" },
                    "summary_point": { "type": "STRING" }
                }
            }
        }
    };
    
    const response = await fetchWithRetry(`${API_BASE_URL}/ai/generate-prompt`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ payload: aiPayload })
    });

    // The backend returns the full Gemini API response body
    const jsonString = response?.candidates?.[0]?.content?.parts?.[0]?.text;
    if (!jsonString) {
        throw new Error("LLM returned an empty or invalid content part.");
    }
    return JSON.parse(jsonString);
}

async function generateImage(prompt, artStyle) {
    // Imagen API Payload
    const aiPayload = {
        instances: [{ prompt: `${prompt}, in the style of ${artStyle}` }],
        parameters: { 
            sampleCount: 1,
            aspectRatio: "16:9" 
        }
    };

    const response = await fetchWithRetry(`${API_BASE_URL}/ai/generate-image`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ payload: aiPayload })
    });

    const base64Data = response?.predictions?.[0]?.bytesBase64Encoded;

    if (!base64Data) {
        // FALLBACK: If the model fails silently (e.g., content filtering or technical error), we use the fallback prompt
        console.warn("Image model failed to return image data. Generating safe fallback image.");
        const fallbackPrompt = "A serene, abstract landscape with geometric shapes and neon colors, digital art, 16:9 aspect ratio.";
        
        const fallbackPayload = {
            instances: [{ prompt: fallbackPrompt }],
            parameters: { 
                sampleCount: 1,
                aspectRatio: "16:9" 
            }
        };

        const fallbackResponse = await fetchWithRetry(`${API_BASE_URL}/ai/generate-image`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ payload: fallbackPayload })
        });

        const fallbackBase64 = fallbackResponse?.predictions?.[0]?.bytesBase64Encoded;
        if (!fallbackBase64) {
            throw new Error("Image generation failed twice (main and fallback).");
        }
        
        console.warn("Successfully generated fallback image.");
        return fallbackBase64;
    }

    return base64Data;
}

// --- SCENE RENDERING ---

function renderScene(scene) {
    const sceneHtml = `
        <div id="scene-${scene.id}" class="scene-card">
            <h3 class="text-xl font-bold text-cyan-400 mb-3">Scene ${scene.id}: ${scene.artStyle}</h3>
            
            <div class="mb-4">
                <img id="scene-img-${scene.id}" src="${scene.imageUrl}" alt="Scene ${scene.id} Visual" class="w-full rounded-lg shadow-xl border border-cyan-500/50 object-cover aspect-16-9">
            </div>

            <p class="text-green-200 mb-2">${scene.narrative}</p>
            <div class="text-sm mt-3 border-t border-green-500/30 pt-3">
                <p class="prompt-label">VISUAL PROMPT USED:</p>
                <code class="block text-xs bg-gray-700 p-2 rounded">${scene.imagePrompt}</code>
                <div class="mt-2">
                    <button class="terminal-button-secondary py-1 px-2 text-sm" onclick="downloadImage(${scene.id})">Download Image</button>
                </div>
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
    summaryList.innerHTML = state.summaryBullets
        .map(point => `<li class="text-green-300 before:content-['>'] before:text-green-500 before:mr-2">${point}</li>`)
        .join('');
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
    // Clear current content, except the main heading
    storyboard.innerHTML = `<h2 class="text-xl font-bold border-b border-green-500/50 pb-2 mb-4 text-green-500">Scene History</h2>`;
    
    // Render all loaded scenes
    state.scenes.forEach(renderScene);
    renderSummary();
    renderStoryControls();
    
    // Set input values
    document.getElementById('start-prompt').value = state.initialPrompt;
    document.getElementById('art-style').value = state.artStyle;
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
    await handleStoryGeneration(`Start a new story about: ${state.initialPrompt}`);
}


async function handleStoryGeneration(prompt = 'Continue the story.') {
    if (state.isGenerating) return;
    setLoading(true, '1/2. Generating narrative and visual prompt...');
    showProgress(1,2,'Generating narrative and visual prompt...');
    
    try {
        const result = await generateStoryData(prompt, state.artStyle);
        
        // --- PAUSE POINT 1: Prompt Staging ---
        state.currentSceneData = result;
        
        // Show staging area and populate prompt
        promptEditor.value = result.image_prompt;
        document.getElementById('staging-narrative').textContent = result.narrative;
        
        storyControls.classList.add('hidden');
        stagingArea.classList.remove('hidden');

        // Ensure user explicitly triggers image generation. Show the staging area
        // and focus the Generate button so they can review the prompt and click.
        const genBtn = document.getElementById('generate-image-btn');
        if (genBtn) {
            genBtn.disabled = false;
            try { genBtn.focus(); } catch(e) {}
        }

        // AUTO-GENERATE: For a faster, single-click UX, automatically trigger
        // image generation immediately after the LLM produces the visual prompt.
        // This mirrors the previous behavior where a single "INITIATE STORY"
        // created both the narrative and its image. We add a short timeout to
        // allow the staging UI to render and for users to briefly see the
        // generated narrative before image generation starts.
        // If you prefer manual review, comment out the next line.
        setTimeout(() => { handleImageGeneration(); }, 250);

    } catch (error) {
        showModal('error-modal', `An error occurred during narrative generation: ${error.message}`);
        // Re-enable controls if generation fails
        renderStoryControls();
    } finally {
        setLoading(false);
        hideProgress();
    }
}


async function handleImageGeneration() {
    if (state.isGenerating || !state.currentSceneData) return;
    setLoading(true, '2/2. Generating image (this may take 10-20 seconds)...');
    showProgress(2,2,'Generating image...');
    
    const customPrompt = promptEditor.value.trim();
    const artStyle = artStyleSelect.value;
    
    if (!customPrompt) {
        showModal('error-modal', 'The Visual Prompt cannot be empty. Please edit it or go back.');
        setLoading(false);
        return;
    }

    try {
        const base64Data = await generateImage(customPrompt, artStyle);
        const imageUrl = `data:image/png;base64,${base64Data}`;
        
        // --- FINAL SCENE ASSEMBLY ---
        state.sceneCounter++;
        const newScene = {
            id: state.sceneCounter,
            narrative: state.currentSceneData.narrative,
            imagePrompt: customPrompt,
            imageUrl: imageUrl,
            summaryPoint: state.currentSceneData.summary_point,
            artStyle: artStyle,
        };
        
        // Update State
        state.storyHistory.push(newScene.narrative);
        state.summaryBullets.push(newScene.summaryPoint);
        state.scenes.unshift(newScene); // Add to the start for a reverse-chronological view
        state.currentSceneData = null; // Clear staging data

        // Save and Render
        await saveStorySession();
        renderUIFromState();
        
    } catch (error) {
        showModal('error-modal', `Image generation failed. Please revise the Visual Prompt and try again. Error: ${error.message}`);
    } finally {
        // Reset controls for the next step (story continuation)
        setLoading(false);
        stagingArea.classList.add('hidden');
        storyControls.classList.remove('hidden');
        renderStoryControls();
        hideProgress();
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
        const base64Data = await generateImage(idea, artStyle);
        const imageUrl = `data:image/png;base64,${base64Data}`;

        // Create a simple narrative for this scene referencing the idea.
        state.sceneCounter++;
        const newScene = {
            id: state.sceneCounter,
            narrative: `Image generated from idea: ${idea}`,
            imagePrompt: idea,
            imageUrl: imageUrl,
            summaryPoint: `Visualized idea: ${idea}`,
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
    
    // no auto-generate toggle: generation is manual by default
    // Load provider banner info
    loadProviderBanner();
});