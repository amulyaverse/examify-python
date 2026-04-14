document.addEventListener('DOMContentLoaded', () => {
    // Navbar scroll effect
    const navbar = document.getElementById('navbar');
    if (navbar) {
        window.addEventListener('scroll', () => {
            if (window.scrollY > 50) {
                navbar.classList.add('scrolled');
            } else {
                navbar.classList.remove('scrolled');
            }
        });
    }

    // Theme toggle
    const themeToggle = document.getElementById('theme-toggle');
    const prefersDarkScheme = window.matchMedia('(prefers-color-scheme: dark)');
    
    // Check saved theme or fallback to system preference
    const currentTheme = localStorage.getItem('theme') || 
                         (prefersDarkScheme.matches ? 'dark' : 'light');
    
    if (currentTheme === 'dark') {
        document.body.setAttribute('data-theme', 'dark');
        if(themeToggle) themeToggle.innerText = '☀️';
    }

    if(themeToggle) {
        themeToggle.addEventListener('click', () => {
            let theme = document.body.getAttribute('data-theme');
            if (theme === 'dark') {
                document.body.removeAttribute('data-theme');
                localStorage.setItem('theme', 'light');
                themeToggle.innerText = '🌙';
            } else {
                document.body.setAttribute('data-theme', 'dark');
                localStorage.setItem('theme', 'dark');
                themeToggle.innerText = '☀️';
            }
        });
    }

    // Auto-dismiss flashing messages
    const alerts = document.querySelectorAll('.alert');
    if (alerts.length > 0) {
        setTimeout(() => {
            alerts.forEach(alert => {
                alert.style.opacity = '0';
                setTimeout(() => alert.remove(), 300);
            });
        }, 5000);
    }

    // Chatbot functionality
    const chatbotToggle = document.getElementById('chatbot-toggle');
    const chatbotClose = document.getElementById('chatbot-close');
    const chatbotContainer = document.getElementById('chatbot-container');
    const chatbotInput = document.getElementById('chatbot-input');
    const chatbotSend = document.getElementById('chatbot-send');
    const chatbotMessages = document.getElementById('chatbot-messages');
    
    let chatHistory = [];

    if (chatbotToggle && chatbotContainer) {
        chatbotToggle.addEventListener('click', () => {
            chatbotContainer.classList.toggle('hidden');
            if (!chatbotContainer.classList.contains('hidden')) {
                chatbotInput.focus();
            }
        });

        chatbotClose.addEventListener('click', () => {
            chatbotContainer.classList.add('hidden');
        });

        const appendMessage = (text, sender) => {
            const msgDiv = document.createElement('div');
            msgDiv.className = `chat-message ${sender}`;
            msgDiv.innerText = text;
            chatbotMessages.appendChild(msgDiv);
            chatbotMessages.scrollTop = chatbotMessages.scrollHeight;
        };

        const sendMessage = async () => {
            const text = chatbotInput.value.trim();
            if (!text) return;

            // Optimistically append user message
            appendMessage(text, 'user');
            chatbotInput.value = '';
            chatbotInput.disabled = true;
            chatbotSend.disabled = true;
            
            // Add thinking indicator optionally (could just be a message)
            const thinkingId = 'thinking-' + Date.now();
            const thinkingDiv = document.createElement('div');
            thinkingDiv.className = `chat-message ai`;
            thinkingDiv.id = thinkingId;
            thinkingDiv.innerText = 'Thinking...';
            chatbotMessages.appendChild(thinkingDiv);
            chatbotMessages.scrollTop = chatbotMessages.scrollHeight;

            try {
                const response = await fetch('/api/chat', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                    },
                    body: JSON.stringify({
                        message: text,
                        history: chatHistory
                    })
                });

                const data = await response.json();
                
                // Remove thinking indicator
                const tid = document.getElementById(thinkingId);
                if (tid) tid.remove();
                
                if (response.ok && data.response) {
                    appendMessage(data.response, 'ai');
                    chatHistory.push({ role: 'user', text: text });
                    chatHistory.push({ role: 'model', text: data.response });
                } else {
                    appendMessage("Sorry, I encountered an error. Please try again.", 'ai');
                }
            } catch (error) {
                console.error("Chat error:", error);
                const tid = document.getElementById(thinkingId);
                if (tid) tid.remove();
                appendMessage("Network error. Please try again later.", 'ai');
            } finally {
                chatbotInput.disabled = false;
                chatbotSend.disabled = false;
                chatbotInput.focus();
            }
        };

        chatbotSend.addEventListener('click', sendMessage);
        
        chatbotInput.addEventListener('keypress', (e) => {
            if (e.key === 'Enter') {
                sendMessage();
            }
        });
    }
});
