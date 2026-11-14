const form = document.querySelector("#chat-form");
const input = document.querySelector("#message-input");
const stream = document.querySelector("#message-stream");
const newChat = document.querySelector("#new-chat");
const conversationList = document.querySelector("#conversation-list");
let conversationId = null;

function normalizeMarkdown(text) {
  return String(text || "")
    .replace(/\\r\\n/g, "\n")
    .replace(/\\n/g, "\n")
    .replace(/\s+(?=#{1,6}\s)/g, "\n\n")
    .replace(/\s+(?=[*+-]\s+(?:\*\*|__))/g, "\n")
    .replace(/\n{3,}/g, "\n\n");
}

function renderMarkdown(text) {
  const html = marked.parse(normalizeMarkdown(text), {
    gfm: true,
    breaks: true,
  });
  return DOMPurify.sanitize(html);
}

function addMessage(text, role, label) {
  const message = document.createElement("div");
  message.className = `message ${role}`;

  const bubble = document.createElement("div");
  bubble.className = "message-bubble";

  if (label) {
    const meta = document.createElement("div");
    meta.className = "message-meta";
    meta.textContent = label;
    bubble.append(meta);
  }

  const content = document.createElement("div");
  content.className = "markdown-content markdown-body";
  content.innerHTML = renderMarkdown(text || "");

  bubble.append(content);
  message.append(bubble);
  stream.append(message);
  message.scrollIntoView({ behavior: "smooth", block: "nearest" });
}

async function sendMessage(message) {
  addMessage(message, "user", "You");
  input.value = "";
  input.style.height = "auto";
  const pending = document.createElement("div");
  pending.className = "message assistant";
  pending.innerHTML =
    '<div class="message-bubble"><div class="message-meta">Lance assistant</div><div>Thinking...</div></div>';
  stream.append(pending);

  try {
    const response = await fetch("/api/chat", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ message, conversation_id: conversationId }),
    });
    if (!response.ok) throw new Error("Request failed");
    const data = await response.json();
    conversationId = data.conversation_id;
    pending.remove();
    addMessage(data.reply, "assistant", "Lance assistant");
    loadConversations().catch((error) =>
      console.error("Could not refresh conversations after chat:", error),
    );
  } catch (error) {
    console.error("Chat request failed:", error);
    pending.remove();
    addMessage(
      "I could not reach the assistant service. Please try again.",
      "assistant",
      "Connection issue",
    );
  }

}

async function loadConversations() {
  const response = await fetch("/api/chats");
  if (!response.ok) throw new Error("Could not load conversations");
  const conversations = await response.json();
  if (!Array.isArray(conversations)) {
    throw new Error("Conversation list response was not an array");
  }
  conversationList.replaceChildren();
  conversations.forEach((conversation) => {
    const button = document.createElement("button");
    button.className = `conversation${
      conversation.conversation_id === conversationId ? " active" : ""
    }`;
    button.dataset.conversationId = conversation.conversation_id;
    button.innerHTML =
      '<span class="status-dot"></span><span class="conversation-title"></span>';
    button.querySelector(".conversation-title").textContent = conversation.title;
    button.addEventListener("click", () =>
      selectConversation(conversation.conversation_id),
    );
    conversationList.append(button);
  });
}

async function selectConversation(id) {
  try {
    const response = await fetch(`/api/chats/${encodeURIComponent(id)}`);
    if (!response.ok) throw new Error(`Conversation request failed: ${response.status}`);
    const conversation = await response.json();
    conversationId = conversation.conversation_id;
    stream.replaceChildren();
    conversation.messages.forEach((message) => {
      addMessage(
        message.content,
        message.role === "human" || message.role === "user" ? "user" : "assistant",
        message.role === "human" || message.role === "user"
          ? "You"
          : "Lance assistant",
      );
    });
    await loadConversations();
  } catch (error) {
    console.error("Could not switch conversation:", error);
  }
}

form.addEventListener("submit", (event) => {
  event.preventDefault();
  const message = input.value.trim();
  if (message) sendMessage(message);
});

input.addEventListener("keydown", (event) => {
  if (event.key === "Enter" && !event.shiftKey) {
    event.preventDefault();
    form.requestSubmit();
  }
});

input.addEventListener("input", () => {
  input.style.height = "auto";
  input.style.height = `${Math.min(input.scrollHeight, 110)}px`;
});

document.querySelectorAll(".suggestion").forEach((button) => {
  button.addEventListener("click", () => {
    input.value = button.dataset.prompt;
    input.focus();
    input.dispatchEvent(new Event("input"));
  });
});

newChat.addEventListener("click", async () => {
  stream.replaceChildren();
  input.value = "";
  conversationId = null;
  try {
    const response = await fetch("/api/chat/new", { method: "POST" });
    if (!response.ok) throw new Error("Could not start a new chat");
    const data = await response.json();
    conversationId = data.conversation_id;
    loadConversations().catch((error) =>
      console.error("Could not refresh conversations after new chat:", error),
    );
  } catch (error) {
    console.error("Could not start a new chat:", error);
    addMessage(
      "I could not start a new conversation. Please try again.",
      "assistant",
      "Connection issue",
    );
  }
  input.focus();
});

loadConversations().catch((error) => {
  console.error("Could not load conversations:", error);
  addMessage(
    "I could not load the conversation list.",
    "assistant",
    "Connection issue",
  );
});
