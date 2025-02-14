document.addEventListener("DOMContentLoaded", function () {
    const chatForm = document.querySelector(".chat-form");
    const chatInput = document.querySelector(".chat-input");
    const chatMessages = document.querySelector(".chat-messages");

    chatForm.addEventListener("submit", async function (event) {
        event.preventDefault();
        const userMessage = chatInput.value.trim();
        if (!userMessage) return;

        // User Message Show Karna
        addMessage("You", userMessage, "user-message");

        // Django API Call
        try {
            const response = await fetch("/chatbot/", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ message: userMessage }),
            });

            const data = await response.json();

            if (data.response) {
                addMessage("UnaniAI", data.response, "ai-message");
            } else {
                addMessage("UnaniAI", "Sorry, I couldn't understand that.", "ai-message");
            }
        } catch (error) {
            addMessage("UnaniAI", "Error connecting to AI server.", "ai-message");
        }

        chatInput.value = "";
    });

    function addMessage(sender, text, className) {
        const messageDiv = document.createElement("div");
        messageDiv.classList.add("message", className);
        messageDiv.innerHTML = `
            <div class="message-avatar">${sender[0]}</div>
            <div class="message-content glass">
                <div class="message-header">
                    <span class="sender">${sender}</span>
                </div>
                <p>${text}</p>
            </div>
        `;
        chatMessages.appendChild(messageDiv);
        chatMessages.scrollTop = chatMessages.scrollHeight;
    }
});
