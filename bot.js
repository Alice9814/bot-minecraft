const fs = require('fs');
const net = require('net');
const mineflayer = require('mineflayer');
const { pathfinder, Movements, goals } = require('mineflayer-pathfinder');

const config = JSON.parse(fs.readFileSync('./config.json', 'utf8'));
const mc = config.minecraft;
const bridgeConfig = config.bridge;

let bot = null;
let defaultMovements = null;
const clients = new Set();

function log(...args) {
  console.log(new Date().toLocaleTimeString(), ...args);
}

function broadcast(message) {
  const line = JSON.stringify(message) + '\n';
  for (const client of clients) {
    if (!client.destroyed && client.writable) client.write(line);
  }
}

function getState() {
  if (!bot || !bot.entity) {
    return { connected: false };
  }

  const p = bot.entity.position;
  const players = Object.entries(bot.players)
    .filter(([name, player]) => name !== bot.username && player.entity)
    .map(([name, player]) => ({
      name,
      position: {
        x: Number(player.entity.position.x.toFixed(1)),
        y: Number(player.entity.position.y.toFixed(1)),
        z: Number(player.entity.position.z.toFixed(1))
      },
      distance: Number(player.entity.position.distanceTo(p).toFixed(1))
    }));

  const nearbyEntities = Object.values(bot.entities)
    .filter(entity => entity !== bot.entity && entity.position && entity.isValid)
    .slice(0, 12)
    .map(entity => ({
      type: entity.type,
      name: entity.name || entity.username || 'desconhecido',
      position: {
        x: Number(entity.position.x.toFixed(1)),
        y: Number(entity.position.y.toFixed(1)),
        z: Number(entity.position.z.toFixed(1))
      },
      distance: Number(entity.position.distanceTo(p).toFixed(1))
    }));

  return {
    connected: true,
    username: bot.username,
    dimension: bot.game.dimension,
    position: {
      x: Number(p.x.toFixed(1)),
      y: Number(p.y.toFixed(1)),
      z: Number(p.z.toFixed(1))
    },
    health: bot.health,
    food: bot.food,
    players,
    nearbyEntities,
    timeOfDay: bot.time.timeOfDay
  };
}

function sendChat(text) {
  if (!bot || !bot.player) throw new Error('O bot ainda não entrou no servidor.');
  const max = Number(config.behavior.max_chat_length || 180);
  const clean = String(text || '').replace(/[\r\n]/g, ' ').trim().slice(0, max);
  if (clean) bot.chat(clean);
}

async function executeAction(action) {
  if (!bot || !bot.entity) throw new Error('O bot não está conectado.');

  switch (action.type) {
    case 'chat':
      sendChat(action.text);
      return 'Mensagem enviada.';

    case 'move_to': {
      const x = Number(action.x);
      const y = Number(action.y);
      const z = Number(action.z);
      if (![x, y, z].every(Number.isFinite)) throw new Error('Coordenadas inválidas.');
      if (Math.abs(x - bot.entity.position.x) > 100 ||
          Math.abs(y - bot.entity.position.y) > 50 ||
          Math.abs(z - bot.entity.position.z) > 100) {
        throw new Error('Destino muito distante; escolha um local mais próximo.');
      }
      bot.pathfinder.setMovements(defaultMovements);
      bot.pathfinder.setGoal(new goals.GoalBlock(Math.floor(x), Math.floor(y), Math.floor(z)));
      return 'Indo até as coordenadas solicitadas.';
    }

    case 'follow': {
      const name = String(action.player || '');
      const player = bot.players[name];
      if (!player || !player.entity) throw new Error('Não consigo ver esse jogador.');
      const p = player.entity.position;
      bot.pathfinder.setMovements(defaultMovements);
      bot.pathfinder.setGoal(new goals.GoalFollow(player.entity, 2), true);
      return 'Seguindo ' + name + '.';
    }

    case 'stop':
      bot.pathfinder.setGoal(null);
      bot.clearControlStates();
      return 'Movimento interrompido.';

    case 'jump':
      bot.setControlState('jump', true);
      setTimeout(() => {
        if (bot) bot.setControlState('jump', false);
      }, 350);
      return 'Pulo executado.';

    case 'look': {
      const yaw = Number(action.yaw);
      const pitch = Number(action.pitch);
      if (!Number.isFinite(yaw) || !Number.isFinite(pitch)) {
        throw new Error('Ângulos inválidos.');
      }
      await bot.look(yaw, Math.max(-Math.PI / 2, Math.min(Math.PI / 2, pitch)), true);
      return 'Direção ajustada.';
    }

    default:
      throw new Error('Ação não permitida: ' + String(action.type));
  }
}

function startBridge() {
  const server = net.createServer(socket => {
    socket.setEncoding('utf8');
    clients.add(socket);
    log('Controlador Python conectado.');

    let buffer = '';
    socket.on('data', chunk => {
      buffer += chunk;
      let newline;
      while ((newline = buffer.indexOf('\n')) !== -1) {
        const line = buffer.slice(0, newline).trim();
        buffer = buffer.slice(newline + 1);
        if (!line) continue;

        let message;
        try {
          message = JSON.parse(line);
        } catch {
          socket.write(JSON.stringify({ type: 'error', error: 'JSON inválido.' }) + '\n');
          continue;
        }

        if (message.type === 'observe') {
          socket.write(JSON.stringify({ type: 'state', state: getState() }) + '\n');
        } else if (message.type === 'action') {
          executeAction(message.action || {})
            .then(result => socket.write(JSON.stringify({ type: 'action_result', result }) + '\n'))
            .catch(error => socket.write(JSON.stringify({
              type: 'action_result',
              error: error.message
            }) + '\n'));
        }
      }
    });

    socket.on('close', () => clients.delete(socket));
    socket.on('error', error => log('Erro na ponte TCP:', error.message));
    socket.write(JSON.stringify({ type: 'bridge_ready', state: getState() }) + '\n');
  });

  server.on('error', error => {
    log('Não foi possível iniciar a ponte TCP:', error.message);
    process.exit(1);
  });

  server.listen(Number(bridgeConfig.port), bridgeConfig.host, () => {
    log('Ponte local ativa em ' + bridgeConfig.host + ':' + bridgeConfig.port);
  });

  setInterval(() => broadcast({ type: 'state', state: getState() }), 5000);
}

function startMinecraftBot() {
  const options = {
    host: mc.host,
    port: Number(mc.port),
    username: mc.username,
    auth: mc.auth || 'offline'
  };
  if (mc.version) options.version = mc.version;

  log('Conectando em ' + options.host + ':' + options.port + ' como ' + options.username);
  bot = mineflayer.createBot(options);
  bot.loadPlugin(pathfinder);

  bot.once('spawn', () => {
    defaultMovements = new Movements(bot);
    log('Minecraft conectado. Versão:', bot.version);
    broadcast({ type: 'state', state: getState() });
  });

  bot.on('chat', (username, message) => {
    if (username === bot.username) return;
    log('<' + username + '> ' + message);
    broadcast({ type: 'chat', username, message });
  });

  bot.on('whisper', (username, message) => {
    if (username === bot.username) return;
    broadcast({ type: 'whisper', username, message });
  });

  bot.on('health', () => broadcast({ type: 'state', state: getState() }));
  bot.on('kicked', reason => log('Expulso do servidor:', reason));
  bot.on('error', error => log('Erro Mineflayer:', error.message));
  bot.on('end', () => {
    log('Conexão Minecraft encerrada.');
    broadcast({ type: 'disconnected' });
  });
}

startBridge();
startMinecraftBot();

process.on('SIGINT', () => {
  log('Encerrando...');
  if (bot) bot.quit();
  for (const client of clients) client.destroy();
  process.exit(0);
});
