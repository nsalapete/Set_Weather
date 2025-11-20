const init = window.SET_WEAVER_INIT || {};

const state = {
    threads: init.threads || [],
    activeThreadId: init.activeThreadId,
    isGenerating: false,
};

const promptInput = document.getElementById("promptInput");
const sendButton = document.getElementById("sendButton");
const threadList = document.getElementById("threadList");
const messageContainer = document.getElementById("messageContainer");
const emptyState = document.getElementById("emptyState");
const suggestionsContainer = document.getElementById("suggestions");
const typingIndicator = document.getElementById("typingIndicator");
const activeTitle = document.getElementById("activeThreadTitle");

if (promptInput) {
    promptInput.addEventListener("input", handleInput);
    promptInput.addEventListener("keydown", handleKeydown);
}

document.getElementById("newThreadBtn").addEventListener("click", createNewThread);
document.getElementById("promptForm").addEventListener("submit", handleSubmit);
threadList.addEventListener("click", handleThreadClick);

renderSuggestionChips(init.suggestions || []);
renderThreads();
if (!state.activeThreadId) {
    createNewThread();
} else {
    loadThread(state.activeThreadId);
}

function handleInput() {
    autoResizeTextarea();
    updateSendState();
}

function handleKeydown(event) {
    if (event.key === "Enter" && !event.shiftKey) {
        event.preventDefault();
        if (!state.isGenerating && promptInput.value.trim()) {
            handleSubmit(event);
        }
    }
}

function autoResizeTextarea() {
    promptInput.style.height = "auto";
    promptInput.style.height = `${promptInput.scrollHeight}px`;
}

function updateSendState() {
    const text = promptInput.value.trim();
    const hasThread = Boolean(state.activeThreadId);
    sendButton.disabled = !text || state.isGenerating || !hasThread;
}

function renderSuggestionChips(suggestions) {
    suggestionsContainer.innerHTML = "";
    suggestions.forEach((text) => {
        const chip = document.createElement("button");
        chip.className = "suggestion";
        chip.type = "button";
        chip.textContent = text;
        chip.addEventListener("click", () => {
            promptInput.value = text;
            handleInput();
            promptInput.focus();
        });
        suggestionsContainer.appendChild(chip);
    });
}

function renderThreads() {
    threadList.innerHTML = "";
    state.threads.forEach((thread) => {
        const article = document.createElement("article");
        article.className = "thread";
        article.dataset.threadId = thread.thread_id;

        article.innerHTML = `
            <div>
                <p class="thread-title">${escapeHtml(thread.title)}</p>
                <small class="thread-timestamp">${escapeHtml(thread.created_at)}</small>
            </div>
            <div class="thread-actions">
                <button class="ghost-btn rename-btn">✏️</button>
                <button class="ghost-btn delete-btn">🗑️</button>
            </div>
        `;

        if (state.activeThreadId === thread.thread_id) {
            article.classList.add("active");
        }

        threadList.appendChild(article);
    });
}

function handleThreadClick(event) {
    const article = event.target.closest(".thread");
    if (!article) return;
    const threadId = Number(article.dataset.threadId);
    if (event.target.closest(".rename-btn")) {
        renameThread(threadId);
        return;
    }
    if (event.target.closest(".delete-btn")) {
        deleteThread(threadId);
        return;
    }
    setActiveThread(threadId);
}

async function renameThread(threadId) {
    const current = state.threads.find((t) => t.thread_id === threadId);
    const title = prompt("New title", current?.title || "New Thread");
    if (!title) return;
    await fetch(`/threads/${threadId}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ title }),
    });
    const thread = state.threads.find((t) => t.thread_id === threadId);
    if (thread) {
        thread.title = title;
    }
    renderThreads();
}

async function deleteThread(threadId) {
    if (!confirm("Delete this thread?")) return;
    await fetch(`/threads/${threadId}`, { method: "DELETE" });
    state.threads = state.threads.filter((t) => t.thread_id !== threadId);
    if (state.activeThreadId === threadId) {
        state.activeThreadId = null;
        messageContainer.innerHTML = "";
        if (state.threads.length) {
            await setActiveThread(state.threads[0].thread_id);
        } else {
            await createNewThread();
        }
    }
    renderThreads();
}

async function setActiveThread(threadId) {
    state.activeThreadId = threadId;
    state.threads = state.threads.map((thread) =>
        thread.thread_id === threadId ? { ...thread } : thread
    );
    renderThreads();
    const thread = state.threads.find((t) => t.thread_id === threadId);
    if (thread) {
        activeTitle.textContent = thread.title;
    }
    await loadThread(threadId);
}

async function createNewThread() {
    const response = await fetch("/threads", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ title: "New Session" }),
    });
    const payload = await response.json();
    state.threads.unshift(payload.thread);
    state.activeThreadId = payload.thread.thread_id;
    activeTitle.textContent = payload.thread.title;
    renderThreads();
    await loadThread(payload.thread.thread_id);
}

async function ensureActiveThread() {
    if (state.activeThreadId) {
        return state.activeThreadId;
    }

    if (state.threads.length) {
        await setActiveThread(state.threads[0].thread_id);
        return state.activeThreadId;
    }

    await createNewThread();
    return state.activeThreadId;
}

async function loadThread(threadId) {
    showTyping(false);
    messageContainer.innerHTML = "";
    const response = await fetch(`/thread/${threadId}/messages`);
    if (!response.ok) return;
    const payload = await response.json();
    renderMessages(payload.messages);
}

function renderMessages(messages) {
    console.log("renderMessages called with:", messages);
    messageContainer.innerHTML = "";
    if (!messages.length) {
        emptyState.style.display = "block";
        return;
    }
    emptyState.style.display = "none";
    messages.forEach((message, idx) => {
        console.log(`Rendering message ${idx}:`, message.sender, message.content.substring(0, 100));
        const container = document.createElement("div");
        container.className = `message-item ${message.sender}`;
        const bubble = document.createElement("div");
        bubble.className = "message-bubble";
        
        // Render HTML for assistant messages, escape for user messages
        if (message.sender === "assistant") {
            console.log("Rendering as HTML for assistant");
            bubble.innerHTML = message.content;
        } else {
            console.log("Escaping HTML for user");
            bubble.innerHTML = escapeHtml(message.content);
        }
        
        container.appendChild(bubble);
        messageContainer.appendChild(container);
    });
    messageContainer.scrollTop = messageContainer.scrollHeight;
    console.log("Messages rendered, container children:", messageContainer.children.length);
}

async function handleSubmit(event) {
    event.preventDefault();
    if (state.isGenerating) return;
    const text = promptInput.value.trim();
    if (!text) return;
    await ensureActiveThread();
    if (!state.activeThreadId) {
        console.error("Unable to create or select a conversation thread.");
        return;
    }
    state.isGenerating = true;
    updateSendState();
    startThinkingAnimation();
    promptInput.value = "";
    autoResizeTextarea();
    emptyState.style.display = "none";
    const pendingBubble = appendMessageBubble({ sender: "user", content: text }, { temporary: true });
    try {
        const response = await fetch(`/thread/${state.activeThreadId}/messages`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ content: text }),
        });
        if (!response.ok) {
            const errText = await response.text();
            throw new Error(errText || `Request failed (${response.status})`);
        }
        const payload = await response.json();
        console.log("Received payload:", payload);
        if (payload.messages) {
            console.log("Rendering messages:", payload.messages.length);
            renderMessages(payload.messages);
        } else {
            throw new Error("No messages returned in payload");
        }
    } catch (error) {
        console.error("Error in handleSubmit:", error);
        markBubbleAsError(pendingBubble, error?.message || "Unable to send message");
    } finally {
        state.isGenerating = false;
        updateSendState();
        stopThinkingAnimation();
    }
}

let thinkingInterval = null;
let thinkingIndex = 0;
const thinkingStates = [
    "Analyzing your request...",
    "Searching music library...",
    "Filtering by genre and BPM...",
    "Evaluating harmonic compatibility...",
    "Planning track transitions...",
    "Calculating mix timing...",
    "Generating DJ instructions...",
    "Finalizing your setlist..."
];

function startThinkingAnimation() {
    thinkingIndex = 0;
    typingIndicator.textContent = thinkingStates[0];
    typingIndicator.classList.add("active");
    
    thinkingInterval = setInterval(() => {
        thinkingIndex = (thinkingIndex + 1) % thinkingStates.length;
        typingIndicator.textContent = thinkingStates[thinkingIndex];
    }, 2000);
}

function stopThinkingAnimation() {
    if (thinkingInterval) {
        clearInterval(thinkingInterval);
        thinkingInterval = null;
    }
    typingIndicator.classList.remove("active");
    typingIndicator.textContent = "· · ·";
}

function showTyping(active) {
    typingIndicator.classList.toggle("active", active);
}

function appendMessageBubble(message, options = {}) {
    const { temporary = false } = options;
    const container = document.createElement("div");
    container.className = `message-item ${message.sender}`;
    if (temporary) {
        container.classList.add("pending");
    }

    const bubble = document.createElement("div");
    bubble.className = "message-bubble";
    if (message.sender === "assistant") {
        bubble.innerHTML = message.content;
    } else {
        bubble.innerHTML = escapeHtml(message.content);
    }

    container.appendChild(bubble);
    messageContainer.appendChild(container);
    messageContainer.scrollTop = messageContainer.scrollHeight;
    return container;
}

function markBubbleAsError(container, errorText) {
    if (!container) return;
    container.classList.remove("pending");
    container.classList.add("error");
    const bubble = container.querySelector(".message-bubble");
    if (bubble) {
        bubble.textContent = errorText;
    }
}

function escapeHtml(str) {
    const div = document.createElement("div");
    div.textContent = str;
    return div.innerHTML;
}
