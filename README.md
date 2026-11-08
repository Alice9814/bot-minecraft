# ProtoBot — Minecraft AI

Aplicativo multiplataforma para controlar um bot Minecraft Java com ProtoBot e inteligência artificial local Gemma 3 1B.

## Interface multiplataforma

A interface visual é escrita uma única vez em HTML, CSS e JavaScript, dentro de `interface/`. Os arquivos são carregados diretamente do armazenamento local por Qt WebView. Não existe servidor HTTP local, endereço localhost para a interface ou navegador externo.

O Qt WebView utiliza os componentes nativos disponíveis na plataforma: Android System WebView no Android e WebView2/Qt WebEngine no Windows; no Linux, utiliza Qt WebEngine. A comunicação entre JavaScript e Python é feita por uma fila local de comandos, sem WebSocket ou servidor web.

## O que está incluído

- Conexão Minecraft Java por ProtoBot, com suporte declarado para 26.2.
- Modo offline e autenticação Microsoft (fluxo de código de dispositivo).
- Modelo Gemma 3 1B Instruct em GGUF Q4_K_M, executado localmente por llama.cpp via llama-cpp-python.
- Download automático do modelo na primeira inicialização (aproximadamente 806 MB); depois de baixado, a inferência funciona sem internet.
- Configuração do servidor, controles de iniciar/pausar/encerrar e console em tempo real.
- Bandeja do sistema no desktop.

## Primeira execução

Na primeira inicialização, o aplicativo baixa o arquivo do modelo para a pasta de dados do usuário, dentro de `models`. É necessário ter internet durante esse primeiro download. O modelo não é baixado novamente se o arquivo local estiver íntegro.

A inferência é executada localmente, sem servidor Ollama e sem enviar as mensagens do jogo para um serviço de IA externo. O modelo Gemma é distribuído sob os termos de uso do Google Gemma. Consulte os termos oficiais antes de redistribuir pesos ou criar uma distribuição modificada.

## Compatibilidade Minecraft

O ProtoBot se conecta usando o protocolo Minecraft Java. Para permitir que jogadores Bedrock joguem no mesmo servidor, o administrador pode configurar um servidor Java com Geyser. O bot continua sendo um cliente Java e não se conecta diretamente a servidores Bedrock.

O campo de versão padrão está definido para 26.2. A autenticação offline funciona em servidores que permitem jogadores offline. Para servidores online-mode, selecione Microsoft e conclua a autorização pelo endereço e código exibidos no console integrado.

## Desenvolvimento desktop

Requisitos: Python 3.12+. Instale as dependências:

```bash
python -m pip install -r requirements.txt
python desktop_app.py
```

O aplicativo usa PySide6 6.11+, Qt WebView e Qt Widgets. Não é necessário instalar Node.js, Mineflayer ou Ollama.

## Gerar os aplicativos desktop

O workflow `.github/workflows/build.yml` compila executáveis únicos para Windows e Linux usando PyInstaller em modo `onefile`. As dependências Python, Qt, ProtoBot, llama.cpp e os arquivos da interface são incorporados ao executável. Na inicialização, o PyInstaller extrai os componentes em uma pasta temporária; não é necessário distribuir `_internal` nem a pasta `interface` ao lado do executável. Os pesos do modelo permanecem na pasta de dados do usuário e são baixados na primeira execução.

Windows:
```powershell
pyinstaller --noconfirm --clean --onefile --windowed --name ProtoBot --add-data "interface;interface" --collect-all protobot --collect-all llama_cpp --collect-all cryptography --collect-all PySide6 desktop_app.py
```

Linux:
```bash
pyinstaller --noconfirm --clean --onefile --windowed --name ProtoBot --add-data "interface:interface" --collect-all protobot --collect-all llama_cpp --collect-all cryptography --collect-all PySide6 desktop_app.py
```

## Android

O ponto de entrada Android é `main.py`, que abre a mesma interface e o mesmo backend Python. O worker pode rodar em uma thread no Android, sem iniciar um processo Python separado. O Qt WebView usa o Android System WebView e carrega os arquivos locais.

O APK ainda não está pronto para distribuição. É necessário compilar e integrar as dependências nativas para ARM64, principalmente llama.cpp/llama-cpp-python. Consulte `android/README.md` para o estado e o procedimento de preparação.

## Limitações conhecidas

- A IA é reativa: analisa mensagens recebidas no chat; não fica executando raciocínio contínuo em segundo plano.
- Gemma 3 1B é um modelo compacto e pode interpretar mal instruções complexas ou produzir JSON inválido ocasionalmente.
- A primeira execução exige internet para baixar os pesos.
- A compatibilidade do protocolo deve ser validada em cada versão, servidor, proxy e configuração.
- Servidores com anti-cheat podem restringir clientes automatizados.

## Segurança

- A sessão Microsoft é mantida na pasta de dados local do usuário; não compartilhe o arquivo de sessão.
- Não publique tokens, credenciais ou arquivos de configuração que contenham dados privados.
- O bot não deve receber permissões administrativas em servidores públicos sem avaliação cuidadosa.
