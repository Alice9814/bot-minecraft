# Minecraft AI Bot — aplicativo desktop

Aplicativo desktop em Python com Mineflayer e Ollama. A interface oferece configuração do servidor, configuração da IA, console e controle do bot pela bandeja do sistema.

## Bandeja do sistema

- Fechar a janela minimiza o aplicativo para a bandeja, sem encerrar o bot.
- O menu do ícone permite abrir a janela, pausar/retomar e encerrar o bot.
- No Windows, o ícone aparece na área de notificação perto do relógio (pode estar dentro da seta `^`).
- No Linux, aparece na bandeja/área de notificação quando o ambiente gráfico e um serviço de StatusNotifier/AppIndicator oferecem suporte.

## Execução para desenvolvimento

Requisitos atuais: Python 3.10+, Node.js compatível com o pacote `javascript`, Ollama instalado e servidor Minecraft acessível.

```bash
python -m pip install -r requirements.txt
ollama pull gemma3:270m
python desktop_app.py
```

A janela permite configurar host, porta, nome, autenticação, modelo, URL da API e temperatura. O arquivo `config.json` é salvo ao clicar em "Salvar configurações" ou "Iniciar bot".

## Gerar os aplicativos

O workflow `.github/workflows/build.yml` compila automaticamente uma pasta executável para Windows e Linux. Para executar manualmente, instale os requisitos e rode:

```bash
pyinstaller --noconfirm --clean --onedir --name MinecraftAIBot --add-data "config.json:." --collect-all javascript --collect-all PySide6 desktop_app.py
```

No Windows, o separador de `--add-data` é ponto e vírgula (`config.json;.`); no Linux, dois-pontos (`config.json:.`).

## Limitação importante desta primeira versão desktop

O workflow de compilação inclui o runtime do Node.js e os pacotes Mineflayer dentro da pasta do aplicativo. O Ollama e os pesos do modelo Gemma ainda não estão incluídos: esta versão requer o Ollama instalado e o modelo baixado (`ollama pull gemma3:270m`). A etapa seguinte para torná-lo totalmente portátil é incorporar uma distribuição redistribuível do Ollama e os pesos do modelo, respeitando suas licenças e validando o pacote em cada sistema operacional.

Drivers de GPU e componentes específicos do sistema também podem continuar sendo necessários para aceleração por hardware.

## Segurança e compatibilidade

- Não publique senhas, tokens ou credenciais.
- Mineflayer é voltado a servidores Minecraft Java.
- O modelo `gemma3:270m` é compacto; sua capacidade de planejamento pode ser limitada.
- A bandeja do Linux depende do ambiente gráfico. Algumas sessões Wayland/GNOME não exibem ícones de bandeja sem extensão compatível.
