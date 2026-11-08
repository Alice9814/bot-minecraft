# Minecraft AI Bot — aplicativo desktop

Aplicativo desktop em Python com Mineflayer e Ollama. A interface oferece configuração do servidor, configuração da IA, console e controle do bot pela bandeja do sistema.

## Compatibilidade Minecraft

- Minecraft Java 26.2: suporte de protocolo incluído pela distribuição compatível do Mineflayer (@wp2508/mineflayer) e seus pacotes Prismarine correspondentes.
- Versões anteriores suportadas pela mesma distribuição continuam disponíveis.
- A conexão automática detecta a versão do servidor. Normalmente, deixe o campo version do config.json como false para usar a detecção automática.
- A compatibilidade de navegação/pathfinding ainda precisa ser validada em servidor 26.2; a conexão e as funções básicas usam o stack de protocolo e dados incluído no build.

## Bandeja do sistema

- Fechar a janela minimiza o aplicativo para a bandeja, sem encerrar o bot.
- O menu do ícone permite abrir a janela, pausar/retomar e encerrar o bot.
- No Windows, o ícone aparece na área de notificação perto do relógio (pode estar dentro da seta ^).
- No Linux, aparece na bandeja/área de notificação quando o ambiente gráfico e um serviço de StatusNotifier/AppIndicator oferecem suporte.

## Execução para desenvolvimento

Requisitos atuais: Python 3.10+, Node.js 22+, Ollama instalado e servidor Minecraft acessível.

```bash
python -m pip install -r requirements.txt
npm install "mineflayer@npm:@wp2508/mineflayer@4.42.7" "minecraft-data@npm:@wp2508/minecraft-data@3.111.7" mineflayer-pathfinder
ollama pull gemma3:270m
python desktop_app.py
```

A janela permite configurar host, porta, nome, autenticação, modelo, URL da API e temperatura. O arquivo config.json é salvo ao clicar em "Salvar configurações" ou "Iniciar bot".

## Gerar os aplicativos

O workflow .github/workflows/build.yml compila automaticamente uma pasta executável para Windows e Linux. Ele instala e verifica os dados do protocolo 26.2 antes de empacotar o aplicativo.

Para executar manualmente, instale os requisitos e rode:

```bash
pyinstaller --noconfirm --clean --onedir --windowed --name MinecraftAIBot --add-data "config.json:." --collect-all javascript --collect-all PySide6 desktop_app.py
```

No Windows, o separador de --add-data é ponto e vírgula (config.json;.); no Linux, dois-pontos (config.json:.).

## Limitação importante desta versão desktop

O workflow de compilação inclui o runtime do Node.js e os pacotes Mineflayer dentro da pasta do aplicativo. O Ollama e os pesos do modelo Gemma ainda não estão incluídos: esta versão requer o Ollama instalado e o modelo baixado (ollama pull gemma3:270m). A etapa seguinte para torná-lo totalmente portátil é incorporar uma distribuição redistribuível do Ollama e os pesos do modelo, respeitando suas licenças e validando o pacote em cada sistema operacional.

Drivers de GPU e componentes específicos do sistema também podem continuar sendo necessários para aceleração por hardware.

## Segurança e compatibilidade

- Não publique senhas, tokens ou credenciais.
- Mineflayer é voltado a servidores Minecraft Java.
- O modelo gemma3:270m é compacto; sua capacidade de planejamento pode ser limitada.
- A bandeja do Linux depende do ambiente gráfico. Algumas sessões Wayland/GNOME não exibem ícones de bandeja sem extensão compatível.
