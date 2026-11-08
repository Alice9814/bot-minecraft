# Minecraft AI Bot — aplicativo desktop

Aplicativo desktop para Minecraft Java com interface PySide6, protocolo implementado pelo ProtoBot e inteligência artificial local Gemma 3 270M. O usuário não precisa instalar Node.js, Mineflayer ou Ollama.

## O que está incluído

- Conexão Minecraft Java por ProtoBot, com suporte declarado para 26.2.
- Modo offline e autenticação Microsoft (fluxo de código de dispositivo).
- Modelo Gemma 3 270M Instruct em GGUF Q4_K_M, executado localmente por llama.cpp via llama-cpp-python.
- Download automático do modelo na primeira inicialização (aproximadamente 253 MB); depois de baixado, a inferência funciona sem internet.
- Temperatura configurável, console integrado e controles para iniciar, pausar e encerrar.
- Bandeja do sistema. Fechar a janela minimiza o aplicativo quando a bandeja está disponível.

## Primeira execução

Na primeira inicialização, o aplicativo baixa o arquivo do modelo para a pasta de dados do usuário, dentro de `models`. É necessário ter internet durante esse primeiro download. O modelo não é baixado novamente se o arquivo local estiver íntegro.

A inferência é executada no próprio processo do worker, sem servidor Ollama e sem enviar as mensagens do jogo para um serviço de IA externo. O modelo GGUF é a versão quantizada Q4_K_M do Gemma 3 270M Instruct; portanto, pertence à mesma família/modelo que usávamos, mas não é o mesmo arquivo binário do pacote Ollama.

O modelo Gemma é distribuído sob os termos de uso do Google Gemma. Consulte os termos oficiais antes de redistribuir pesos ou criar uma distribuição modificada.

## Compatibilidade Minecraft

ProtoBot declara suporte ao protocolo Minecraft Java 26.2 e outras versões recentes. A integração foi feita usando sua API assíncrona: eventos de chat, envio de mensagens, estado do jogador e navegação. Isso não substitui testes de conexão e movimento em servidores reais; servidores com plugins, proxies ou anti-cheat podem se comportar de forma diferente.

O campo de versão padrão está definido para 26.2. A autenticação offline funciona em servidores que permitem jogadores offline. Para servidores online-mode, selecione Microsoft e conclua a autorização pelo endereço e código exibidos no console integrado.

## Bandeja e janelas de terminal

- Fechar a janela minimiza para a bandeja, quando disponível.
- No Windows, o processo auxiliar é iniciado com `CREATE_NO_WINDOW` para não abrir CMD/terminal.
- No Linux, o aplicativo continua sendo compilado como janela gráfica (`--windowed`).

## Execução para desenvolvimento

Requisitos: Python 3.12+. O runtime de inferência e o cliente de protocolo são instalados pelo arquivo requirements.

```bash
python -m pip install -r requirements.txt
python desktop_app.py
```

A primeira execução baixa o modelo GGUF automaticamente. Não instale Ollama nem Node.js.

## Gerar os aplicativos

O workflow `.github/workflows/build.yml` compila pastas executáveis para Windows e Linux. O pacote inclui ProtoBot, llama-cpp-python e as bibliotecas do PySide6. Os pesos do modelo são baixados na primeira execução para manter o artefato menor.

Para executar manualmente o PyInstaller:

Windows:
```powershell
pyinstaller --noconfirm --clean --onedir --windowed --name MinecraftAIBot --add-data "config.json;." --collect-all protobot --collect-all llama_cpp --collect-all PySide6 desktop_app.py
```

Linux:
```bash
pyinstaller --noconfirm --clean --onedir --windowed --name MinecraftAIBot --add-data "config.json:." --collect-all protobot --collect-all llama_cpp --collect-all PySide6 desktop_app.py
```

## Limitações conhecidas

- A IA é reativa: analisa mensagens recebidas no chat; não fica executando raciocínio contínuo em segundo plano.
- Gemma 3 270M é um modelo compacto. Pode interpretar mal instruções complexas ou produzir JSON inválido ocasionalmente.
- A primeira execução exige internet para baixar os pesos. O runtime llama.cpp já faz parte do pacote do aplicativo.
- A compatibilidade de protocolo anunciada pelo ProtoBot ainda precisa ser validada em cada tipo de servidor, proxy e configuração.
- A bandeja do Linux depende do ambiente gráfico. Algumas sessões Wayland/GNOME podem exigir suporte adicional a AppIndicator.

## Segurança

- A sessão Microsoft é mantida na pasta de dados local do usuário; não compartilhe o arquivo de sessão.
- Não publique tokens, credenciais ou arquivos de configuração que contenham dados privados.
- O bot não deve receber permissões administrativas em servidores públicos sem avaliação cuidadosa.
