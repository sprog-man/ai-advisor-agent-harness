/**
 * AI Advisor Agent - Frontend Application (with Streaming & Knowledge Base)
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
        this.uploadBtn = document.getElementById('uploadBtn');
        this.knowledgeModal = document.getElementById('knowledgeModal');
        this.closeModalBtn = document.getElementById('closeModalBtn');
        this.knowledgeList = document.getElementById('knowledgeList');
        this.uploadArea = document.getElementById('uploadArea');
        this.modalFileInput = document.getElementById('modalFileInput');
    }
    
    initEventListeners() {
        this.menuBtn.addEventListener('click', () => {
            this.sidebar.classList.toggle('visible');
        });
        
        this.newChatBtn.addEventListener('click', () => {
            this.clearChat();
        });
        
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
        
        this.sendBtn.addEventListener('click', () => {
            this.sendMessage();
        });
        
        document.querySelectorAll('.quick-action').forEach(btn => {
            btn.addEventListener('click', () => {
                const prompt = btn.dataset.prompt;
                this.messageInput.value = prompt;
                this.updateSendButton();
                this.sendMessage();
            });
        });
        
        if (this.uploadBtn) {
            this.uploadBtn.addEventListener('click', () => {
                this.knowledgeModal.classList.add('visible');
                this.loadKnowledgeList();
            });
        }
        
        if (this.closeModalBtn) {
            this.closeModalBtn.addEventListener('click', () => {
                this.knowledgeModal.classList.remove('visible');
            });
        }
        
        if (this.uploadArea) {
            this.uploadArea.addEventListener('click', () => {
                this.modalFileInput.click();
            });
            
            this.uploadArea.addEventListener('dragover', (e) => {
                e.preventDefault();
                this.uploadArea.classList.add('drag-over');
            });
            
            this.uploadArea.addEventListener('dragleave', () => {
                this.uploadArea.classList.remove('drag-over');
            });
            
            this.uploadArea.addEventListener('drop', (e) => {
                e.preventDefault();
                this.uploadArea.classList.remove('drag-over');
                const files = e.dataTransfer.files;
                if (files.length > 0) {
                    this.uploadFile(files[0]);
                }
            });
        }
        
        if (this.modalFileInput) {
            this.modalFileInput.addEventListener('change', (e) => {
                if (e.target.files.length > 0) {
                    this.uploadFile(e.target.files[0]);
                }
            });
        }
        
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
        
        this.welcomeScreen.style.display = 'none';
        this.addMessage('user', content);
        
        this.messageInput.value = '';
        this.autoResize();
        this.updateSendButton();
        
        this.isStreaming = true;
        const assistantMessage = this.addMessage('assistant', '', true);
        
        try {
            await this.streamResponse(content, assistantMessage);
        } catch (error) {
            console.error('API Error:', error);
            this.updateMessageContent(assistantMessage, '抱歉，发生了错误。请稍后重试。');
        } finally {
            this.isStreaming = false;
            this.updateSendButton();
            this.removeLoadingIndicator(assistantMessage);
        }
    }
    
    async streamResponse(prompt, messageElement) {
        const response = await fetch(this.apiEndpoint, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ message: prompt, stream: true })
        });
        
        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }
        
        const reader = response.body.getReader();
        const decoder = new TextDecoder();
        let fullContent = '';
        let metadata = null;
        
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
                        if (data.done && data.metadata) {
                            metadata = data.metadata;
                        }
                        if (data.done) {
                            this.removeTypingCursor(messageElement);
                        }
                    } catch (e) {}
                }
            }
        }
        
        if (metadata && metadata.knowledge_used) {
            const sourceInfo = document.createElement('div');
            sourceInfo.className = 'knowledge-source';
            sourceInfo.innerHTML = `
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                    <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/>
                    <polyline points="14 2 14 8 20 8"/>
                </svg>
                <span>参考了知识库${metadata.knowledge_sources.length > 0 ? ': ' + metadata.knowledge_sources.join(', ') : ''}</span>
            `;
            messageElement.parentElement.appendChild(sourceInfo);
        }
        
        this.removeTypingCursor(messageElement);
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
            `;
            contentDiv.appendChild(actionsDiv);
        }
        
        messageDiv.appendChild(contentDiv);
        this.messagesList.appendChild(messageDiv);
        this.scrollToBottom();
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
        if (cursor) cursor.remove();
    }
    
    removeLoadingIndicator(messageElement) {
        const loader = messageElement.querySelector('.loading-indicator');
        if (loader) loader.remove();
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
    
    clearChat() {
        this.messages = [];
        this.messagesList.innerHTML = '';
        this.welcomeScreen.style.display = 'flex';
        this.sidebar.classList.remove('visible');
    }
    
    async uploadFile(file) {
        if (!file) return;
        
        const formData = new FormData();
        formData.append('file', file);
        
        try {
            const response = await fetch('/api/knowledge/upload', {
                method: 'POST',
                body: formData
            });
            
            if (response.ok) {
                const result = await response.json();
                alert(`文件上传成功: ${result.filename}`);
                this.loadKnowledgeList();
            } else {
                alert('上传失败');
            }
        } catch (error) {
            alert('上传错误: ' + error.message);
        }
        
        if (this.modalFileInput) {
            this.modalFileInput.value = '';
        }
    }
    
    async loadKnowledgeList() {
        try {
            const response = await fetch('/api/knowledge/list');
            const data = await response.json();
            
            if (this.knowledgeList) {
                this.knowledgeList.innerHTML = data.files.map(f => `
                    <div class="knowledge-item">
                        <span class="file-name">${f.name}</span>
                        <span class="file-size">${(f.size / 1024).toFixed(1)} KB</span>
                    </div>
                `).join('') || '<p class="no-files">暂无知识库文件</p>';
            }
        } catch (error) {
            console.error('加载知识库列表失败:', error);
        }
    }
}

const app = new ChatApp();
