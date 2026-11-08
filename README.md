# Minecraft AI Bot — Python + Mineflayer + Ollama

Bot de Minecraft escrito em Python. A conexão e o controle do Minecraft usam Mineflayer carregado pelo pacote Python javascript; não há arquivo .js no projeto.

## Requisitos

- Python 3.10 ou superior
- Node.js 18 ou superior (usado internamente pelo pacote javascript)
- Ollama instalado e em execução
- Servidor Minecraft Java acessível pela máquina onde o bot será executado

## Instalação

Na pasta do projeto, execute:

```bash
python -m pip install -r requirements.txt
ollama pull gemma3:270m
```

O pacote javascript permite importar bibliotecas Node diretamente do Python e gerencia o carregamento das dependências Mineflayer, mineflayer-pathfinder e minecraft-data.

## Configuração

Edite config.json:

- minecraft.host: endereço do servidor.
- minecraft.port: porta do servidor.
- minecraft.username: nome do bot.
- minecraft.auth: offline para servidores offline ou microsoft para autenticação Microsoft.
- minecraft.version: false para detectar automaticamente.
- ollama.url: endereço da API do Ollama.
- ollama.model: modelo utilizado, por padrão gemma3:270m.
- behavior.respond_only_when_mentioned: se true, só processa mensagens que mencionem o nome configurado.

Não coloque senhas ou tokens neste repositório público.

## Executar

Com o servidor Minecraft e o Ollama em execução:

```bash
python bot.py
```

O bot entra no servidor e usa o Ollama para interpretar mensagens do chat. Ele pode conversar, seguir jogadores visíveis, andar até coordenadas conhecidas, olhar em uma direção, pular e parar.

## Observações

- O bot funciona em servidores Minecraft Java compatíveis com Mineflayer.
- O modelo recebe o estado do mundo junto com as mensagens para escolher uma ação.
- Modelos pequenos podem interpretar pedidos de forma limitada.
- Node.js continua sendo um requisito interno do Mineflayer, mas você não precisa criar, editar ou executar arquivos JavaScript.
