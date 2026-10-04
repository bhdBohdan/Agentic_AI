const form = document.querySelector("#chat-form");
const input = document.querySelector("#message-input");
const stream = document.querySelector("#message-stream");
const newChat = document.querySelector("#new-chat");

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
      body: JSON.stringify({ message }),
    });
    if (!response.ok) throw new Error("Request failed");
    const data = await response.json();
    pending.remove();
    addMessage(data.reply, "assistant", "Lance assistant");
  } catch (error) {
    pending.remove();
    addMessage(
      "I could not reach the assistant service. Please try again.",
      "assistant",
      "Connection issue",
    );
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

newChat.addEventListener("click", () => {
  stream.replaceChildren();
  input.value = "";
  input.focus();
});
