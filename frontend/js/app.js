/**
 * AI Advisor Agent - Frontend Application
 */

class ChatApp {
    constructor() {
        this.messages = [];
        this.isStreaming = false;
        this.apiEndpoint = '/api/chat';
        
        this.initElements();
        this.initEventListeners();
        this.initMarkdown();
    }
    
    initElements() {
        this.sidebar = document.getElementById('sidebar');
        this.menuBtn = document.getElementById('menuBtn');
        this.newChatBtn = document.getElementById('newChatBtn');
        this.chatContainer = document.getElementById('chatContainer');
        this.messagesList = document.getElementById('messagesList');
        this.welcomeScreen = document.getElementById('welcomeScreen');
        this.messageInput = document.getElementById('messageInput');
        this.sendBtn = document.getElementById('sendBtn');
    }
    
    initEventListeners() {
        // 菜单按钮
        this.menuBtn.addEventListener('click', () => {
            this.sidebar.classList.toggle('visible');
        });
        
        // 新对话按钮
        this.newChatBtn.addEventListener('click', () => {
            this.clearChat();
        });
        
        // 输入框
        this.messageInput.addEventListener('input', () => {
            this.autoResize();
            this.updateSendButton();
        });
        
        this.messageInput.addEventListener('keydown', (e) => {
            if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault();
                this.sendMessage();
            }
        });
        
        // 发送按钮
        this.sendBtn.addEventListener('click', () => {
            this.sendMessage();
        });
        
        // 快捷操作
        document.querySelectorAll('.quick-action').forEach(btn => {
            btn.addEventListener('click', () => {
                const prompt = btn.dataset.prompt;
                this.messageInput.value = prompt;
                this.updateSendButton();
                this.sendMessage();
            });
        });
        
        // 点击外部关闭侧边栏
        document.addEventListener('click', (e) => {
            if (this.sidebar.classList.contains('visible') && 
                !this.sidebar.contains(e.target) && 
                e.target !== this.menuBtn) {
                this.sidebar.classList.remove('visible');
            }
        });
    }
    
    initMarkdown() {
        if (typeof marked !== 'undefined') {
            marked.setOptions({
                breaks: true,
                gfm: true,
                headerIds: false,
                mangle: false
            });
        }
    }
    
    autoResize() {
        this.messageInput.style.height = 'auto';
        this.messageInput.style.height = Math.min(this.messageInput.scrollHeight, 200) + 'px';
    }
    
    updateSendButton() {
        const hasContent = this.messageInput.value.trim().length > 0;
        this.sendBtn.disabled = !hasContent || this.isStreaming;
    }
    
    async sendMessage() {
        const content = this.messageInput.value.trim();
        if (!content || this.isStreaming) return;
        
        // 隐藏欢迎界面
        this.welcomeScreen.style.display = 'none';
        
        // 添加用户消息
        this.addMessage('user', content);
        
        // 清空输入框
        this.messageInput.value = '';
        this.autoResize();
        this.updateSendButton();
        
        // 显示加载状态
        this.isStreaming = true;
        const assistantMessage = this.addMessage('assistant', '', true);
        
        try {
            // 调用API
            await this.streamResponse(content, assistantMessage);
        } catch (error) {
            console.error('API Error:', error);
            this.updateMessageContent(assistantMessage, '抱歉，发生了错误。请稍后重试。');
            this.addErrorToMessage(assistantMessage, error.message);
        } finally {
            this.isStreaming = false;
            this.updateSendButton();
            this.removeLoadingIndicator(assistantMessage);
        }
    }
    
    async streamResponse(prompt, messageElement) {
        try {
            const response = await fetch(this.apiEndpoint, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    message: prompt,
                    stream: true
                })
            });
            
            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }
            
            const reader = response.body.getReader();
            const decoder = new TextDecoder();
            let fullContent = '';
            
            while (true) {
                const { done, value } = await reader.read();
                if (done) break;
                
                const chunk = decoder.decode(value);
                const lines = chunk.split('\n');
                
                for (const line of lines) {
                    if (line.startsWith('data: ')) {
                        try {
                            const data = JSON.parse(line.slice(6));
                            if (data.content) {
                                fullContent += data.content;
                                this.updateMessageContent(messageElement, fullContent, true);
                            }
                            if (data.done) {
                                this.removeTypingCursor(messageElement);
                            }
                        } catch (e) {
                            // 忽略解析错误
                        }
                    }
                }
            }
            
            this.removeTypingCursor(messageElement);
            
        } catch (error) {
            // 如果流式API不可用，使用普通API
            const response = await fetch(this.apiEndpoint, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    message: prompt,
                    stream: false
                })
            });
            
            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }
            
            const data = await response.json();
            this.updateMessageContent(messageElement, data.response || data.content || '无响应');
        }
    }
    
    addMessage(role, content, isLoading = false) {
        const messageDiv = document.createElement('div');
        messageDiv.className = `message ${role}`;
        
        const contentDiv = document.createElement('div');
        contentDiv.className = 'message-content';
        
        const bubbleDiv = document.createElement('div');
        bubbleDiv.className = 'message-bubble';
        
        if (isLoading) {
            bubbleDiv.innerHTML = this.createLoadingIndicator();
        } else if (role === 'assistant') {
            bubbleDiv.innerHTML = this.renderMarkdown(content);
        } else {
            bubbleDiv.textContent = content;
        }
        
        contentDiv.appendChild(bubbleDiv);
        
        // 添加操作按钮（仅AI消息）
        if (role === 'assistant' && !isLoading) {
            const actionsDiv = document.createElement('div');
            actionsDiv.className = 'message-actions';
            actionsDiv.innerHTML = `
                <button class="action-btn" onclick="app.copyMessage(this)">
                    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                        <rect x="9" y="9" width="13" height="13" rx="2" ry="2"/>
                        <path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"/>
                    </svg>
                    复制
                </button>
                <button class="action-btn" onclick="app.regenerateMessage(this)">
                    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                        <path d="M23 4v6h-6M1 20v-6h6"/>
                        <path d="M3.51 9a9 9 0 0 1 14.85-3.36L23 10M1 14l4.64 4.36A9 9 0 0 0 20.49 15"/>
                    </svg>
                    重新生成
                </button>
            `;
            contentDiv.appendChild(actionsDiv);
        }
        
        messageDiv.appendChild(contentDiv);
        this.messagesList.appendChild(messageDiv);
        
        // 滚动到底部
        this.scrollToBottom();
        
        // 保存消息
        this.messages.push({ role, content });
        
        return bubbleDiv;
    }
    
    updateMessageContent(messageElement, content, append = false) {
        if (append) {
            messageElement.innerHTML = this.renderMarkdown(content) + '<span class="typing-cursor"></span>';
        } else {
            messageElement.innerHTML = this.renderMarkdown(content);
        }
        this.scrollToBottom();
    }
    
    removeTypingCursor(messageElement) {
        const cursor = messageElement.querySelector('.typing-cursor');
        if (cursor) {
            cursor.remove();
        }
    }
    
    removeLoadingIndicator(messageElement) {
        const loader = messageElement.querySelector('.loading-indicator');
        if (loader) {
            loader.remove();
        }
    }
    
    createLoadingIndicator() {
        return `
            <div class="loading-indicator">
                <div class="loading-dot"></div>
                <div class="loading-dot"></div>
                <div class="loading-dot"></div>
            </div>
        `;
    }
    
    addErrorToMessage(messageElement, error) {
        const errorDiv = document.createElement('div');
        errorDiv.className = 'error-message';
        errorDiv.textContent = error;
        messageElement.parentElement.appendChild(errorDiv);
    }
    
    renderMarkdown(text) {
        if (!text) return '';
        
        if (typeof marked !== 'undefined') {
            try {
                return marked.parse(text);
            } catch (e) {
                return this.escapeHtml(text);
            }
        }
        
        return this.escapeHtml(text).replace(/\n/g, '<br>');
    }
    
    escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }
    
    scrollToBottom() {
        requestAnimationFrame(() => {
            this.chatContainer.scrollTop = this.chatContainer.scrollHeight;
        });
    }
    
    copyMessage(button) {
        const messageBubble = button.closest('.message-content').querySelector('.message-bubble');
        const text = messageBubble.innerText;
        
        navigator.clipboard.writeText(text).then(() => {
            const originalText = button.innerHTML;
            button.innerHTML = `
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                    <path d="M20 6L9 17l-5-5"/>
                </svg>
                已复制
            `;
            setTimeout(() => {
                button.innerHTML = originalText;
            }, 2000);
        });
    }
    
    regenerateMessage(button) {
        // 找到上一条用户消息
        const messages = Array.from(this.messagesList.querySelectorAll('.message'));
        const currentMessage = button.closest('.message');
        const currentIndex = messages.indexOf(currentMessage);
        
        let lastUserMessage = '';
        for (let i = currentIndex - 1; i >= 0; i--) {
            if (messages[i].classList.contains('user')) {
                lastUserMessage = messages[i].querySelector('.message-bubble').textContent;
                break;
            }
        }
        
        if (lastUserMessage) {
            // 删除当前AI回复
            currentMessage.remove();
            this.messages.pop();
            
            // 重新发送
            this.messageInput.value = lastUserMessage;
            this.sendMessage();
        }
    }
    
    clearChat() {
        this.messages = [];
        this.messagesList.innerHTML = '';
        this.welcomeScreen.style.display = 'flex';
        this.sidebar.classList.remove('visible');
    }
}

// 初始化应用
const app = new ChatApp();
