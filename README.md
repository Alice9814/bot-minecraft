# Minecraft AI Bot — Mineflayer + Ollama

Bot de Minecraft controlado por um modelo local do Ollama. O Mineflayer roda em Node.js e cuida da conexão/jogabilidade; o Python conversa com o Ollama e envia ações ao Mineflayer por uma conexão TCP local.

Modelo padrão: `gemma3:270m`.

## Requisitos

- Node.js 18 ou superior
- Python 3.10 ou superior
- Ollama instalado e em execução
- Um servidor Minecraft Java acessível pela máquina onde o bot será executado

## Instalação

1. Baixe/clique em **Code → Download ZIP** ou clone este repositório.
2. Abra um terminal dentro da pasta do projeto.
3. Instale as dependências:

```bash
npm install
python -m pip install -r requirements.txt
ollama pull gemma3:270m
```

4. Edite `config.json` e informe o endereço do servidor Minecraft.

## Configuração

O arquivo `config.json` contém host, porta, nome do bot, autenticação, versão do Minecraft, modelo Ollama e endereço da API.

- Para servidores offline/cracked, use `"auth": "offline"`.
- Para conta Microsoft, use `"auth": "microsoft"` e siga o login solicitado no terminal.
- Deixe `"version": false` para o Mineflayer detectar a versão automaticamente.
- O servidor TCP interno fica em `127.0.0.1:8765`. Mantenha-o local; não exponha essa porta à internet.

## Como iniciar

Abra dois terminais na pasta do projeto.

Terminal 1 — Mineflayer:

```bash
npm start
```

Terminal 2 — IA Python:

```bash
python bot.py
```

O bot responde a mensagens no chat e também recebe atualizações periódicas do estado do mundo. A IA pode conversar, andar até coordenadas, seguir jogadores visíveis, olhar para uma direção, pular e parar.

## Exemplos no chat

- `Bot, oi!`
- `Bot, venha até mim`
- `Bot, me siga`
- `Bot, pare`

O modelo decide quando responder; mencionar o nome do bot ajuda a chamar sua atenção.

## Segurança e limitações

- A IA só pode executar as ações explicitamente permitidas em `bot.js`.
- Não coloque senhas ou tokens em repositórios públicos.
- O bot precisa estar conectado a um servidor compatível com Mineflayer (Minecraft Java).
- Modelos muito pequenos podem interpretar instruções de forma limitada. Se o bot agir de maneira incoerente, tente um modelo maior no Ollama e altere `ollama_model` em `config.json`.

## Estrutura

- `bot.js`: conexão Minecraft, pathfinding e ponte TCP local.
- `bot.py`: integração com Ollama e seleção de ações.
- `config.json`: configurações.
- `package.json`: dependências Node.js.
- `requirements.txt`: dependências Python (nenhuma biblioteca externa é necessária atualmente).
