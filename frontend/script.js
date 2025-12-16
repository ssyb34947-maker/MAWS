let socket = null;
let gameId = null;

const startButton = document.getElementById('startButton');
const statusBox = document.getElementById('statusBox');
const chatMessages = document.getElementById('chatMessages');

startButton.addEventListener('click', () => {
    if (startButton.textContent === '启动游戏') {
        startGame();
    }
});

function startGame() {
    startButton.disabled = true;
    statusBox.textContent = '状态：正在启动游戏...';
    
    // 连接WebSocket
    socket = new WebSocket('ws://localhost:8000/ws');
    
    socket.onopen = () => {
        console.log('Connected to server');
        socket.send(JSON.stringify({type: 'start_game'}));
    };
    
    socket.onmessage = (event) => {
        const data = JSON.parse(event.data);
        handleServerMessage(data);
    };
    
    socket.onclose = () => {
        console.log('Disconnected from server');
        statusBox.textContent = '状态：连接已断开';
        startButton.disabled = false;
    };
    
    socket.onerror = (error) => {
        console.error('WebSocket error:', error);
        statusBox.textContent = '状态：连接出错';
        startButton.disabled = false;
    };
}

function handleServerMessage(data) {
    switch (data.type) {
        case 'game_started':
            statusBox.textContent = `状态：游戏已启动 (ID: ${data.game_id})`;
            gameId = data.game_id;
            startButton.textContent = '重新开始';
            startButton.disabled = false;
            break;
            
        case 'role_assigned':
            assignRole(data.player_id, data.role);
            break;
            
        case 'status_update':
            statusBox.textContent = `状态：${data.message}`;
            break;
            
        case 'chat_message':
            addChatMessage(data.sender, data.content);
            break;
            
        case 'speech_update':
            updateSpeechBubble(data.player_id, data.content);
            break;
            
        case 'game_log':
            // 处理游戏日志
            if (data.log_type === 'system') {
                // 系统消息，显示在状态框或聊天框
                if (data.phase === 'end' && typeof data.content === 'string' && data.content.includes('Winner')) {
                    statusBox.textContent = `状态：${data.content}`;
                } else {
                    addChatMessage('系统', data.content);
                }
            } else if (data.log_type === 'speech' && data.agent_id) {
                // Agent发言，显示在对应角色的发言气泡中
                updateSpeechBubble(data.agent_id, data.content);
                addChatMessage(`玩家${data.agent_id}`, data.content);
            } else if (data.log_type === 'agent_speech' && data.agent_id) {
                // Agent发言（另一种格式），显示在对应角色的发言气泡中
                updateSpeechBubble(data.agent_id, data.content);
                addChatMessage(`玩家${data.agent_id}`, data.content);
            } else if (data.log_type === 'action') {
                // Agent行动，显示在聊天框
                const actionType = data.content.type;
                let actionText = '';
                
                switch(actionType) {
                    case 'night_kill':
                        actionText = `夜间决定击杀玩家${data.content.target}`;
                        break;
                    case 'seer_check':
                        actionText = `查验了玩家${data.content.target}的身份`;
                        break;
                    case 'witch_save':
                        actionText = `使用解药救了玩家${data.content.target}`;
                        break;
                    case 'witch_poison':
                        actionText = `使用毒药毒杀了玩家${data.content.target}`;
                        break;
                    case 'vote':
                        actionText = `投票淘汰玩家${data.content.target}`;
                        break;
                    default:
                        actionText = `执行了${actionType}操作`;
                }
                
                addChatMessage(`玩家${data.agent_id}`, actionText);
            }
            break;
    }
}

function assignRole(playerId, role) {
    const roleBox = document.querySelector(`.role-box[data-player="${playerId}"]`);
    if (roleBox) {
        // 设置角色身份
        const roleName = roleBox.querySelector('.role-name');
        roleName.textContent = `${playerId}号\n${role}`;
        
        // 确保角色框可见
        roleBox.style.display = 'flex';
    }
}

function addChatMessage(sender, content) {
    const messageDiv = document.createElement('div');
    messageDiv.className = 'message';
    messageDiv.textContent = `[${sender}] ${content}`;
    chatMessages.appendChild(messageDiv);
    chatMessages.scrollTop = chatMessages.scrollHeight;
}

function updateSpeechBubble(playerId, content) {
    const roleBox = document.querySelector(`.role-box[data-player="${playerId}"]`);
    if (roleBox) {
        const bubble = roleBox.querySelector('.speech-bubble');
        if (content.trim() === '') {
            bubble.style.display = 'none';
        } else {
            bubble.textContent = content;
            bubble.style.display = 'block';
        }
    }
}