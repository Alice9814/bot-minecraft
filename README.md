# ProtoBot — Minecraft AI

Aplicativo multiplataforma para controlar um bot Minecraft Java com ProtoBot e inteligência artificial local Gemma 3 1B.

## Interface multiplataforma

A interface visual é escrita uma única vez em HTML, CSS e JavaScript, dentro de \`interface/\`. O desktop carrega os arquivos locais com Qt WebEngine e comunica a interface com o backend Python por Qt WebChannel. Não existe servidor HTTP local, endereço localhost para a interface ou navegador externo.

O Android usará os mesmos arquivos HTML/CSS/JS em uma WebView nativa, com uma ponte JavaScript nativa para o backend Python. O hospedeiro Android ainda está em desenvolvimento; a interface compartilhada e o hospedeiro desktop foram adicionados primeiro.

## O que está incluído

- Conexão Minecraft Java por ProtoBot, com suporte declarado para 26.2.
- Modo offline e autenticação Microsoft (fluxo de código de dispositivo).
- Modelo Gemma 3 1B Instruct em GGUF Q4_K_M, executado localmente por llama.cpp via llama-cpp-python.
- Download automático do modelo na primeira inicialização (aproximadamente 806 MB); depois de baixado, a inferência funciona sem internet.
- Configuração do servidor, controles de iniciar/pausar/encerrar e console em tempo real.
- Bandeja do sistema no desktop.

## Primeira execução

Na primeira inicialização, o aplicativo baixa o arquivo do modelo para a pasta de dados do usuário, dentro de \`models\`. É necessário ter internet durante esse primeiro download. O modelo não é baixado novamente se o arquivo local estiver íntegro.

A inferência é executada localmente, sem servidor Ollama e sem enviar as mensagens do jogo para um serviço de IA externo. O modelo Gemma é distribuído sob os termos de uso do Google Gemma. Consulte os termos oficiais antes de redistribuir pesos ou criar uma distribuição modificada.

## Compatibilidade Minecraft

O ProtoBot se conecta usando o protocolo Minecraft Java. Para permitir que jogadores Bedrock joguem no mesmo servidor, o administrador pode configurar um servidor Java com Geyser. O bot continua sendo um cliente Java e não se conecta diretamente a servidores Bedrock.

O campo de versão padrão está definido para 26.2. A autenticação offline funciona em servidores que permitem jogadores offline. Para servidores online-mode, selecione Microsoft e conclua a autorização pelo endereço e código exibidos no console integrado.

## Desenvolvimento desktop

Requisitos: Python 3.12+. Instale as dependências:

\`\`\`bash
python -m pip install -r requirements.txt
python desktop_app.py
\`\`\`

O aplicativo usa PySide6, Qt WebEngine e Qt WebChannel para exibir a interface local e conectar o JavaScript ao Python. Não é necessário instalar Node.js, Mineflayer ou Ollama.

## Gerar os aplicativos desktop

O workflow \`.github/workflows/build.yml\` compila pastas executáveis para Windows e Linux. Ele inclui os arquivos HTML e o runtime do ProtoBot/llama.cpp. Os pesos do modelo são baixados na primeira execução para manter o artefato menor.

Windows:
\`\`\`powershell
pyinstaller --noconfirm --clean --onedir --windowed --name ProtoBot --add-data "config.json;." --add-data "interface;interface" --collect-all protobot --collect-all llama_cpp --collect-all cryptography --collect-all PySide6 desktop_app.py
\`\`\`

Linux:
\`\`\`bash
pyinstaller --noconfirm --clean --onedir --windowed --name ProtoBot --add-data "config.json:." --add-data "interface:interface" --collect-all protobot --collect-all llama_cpp --collect-all cryptography --collect-all PySide6 desktop_app.py
\`\`\`

## Android

O objetivo é um APK independente: bot, conexão Minecraft e IA executados no próprio aparelho. A interface Android reutilizará os arquivos de \`interface/\`, sem servidor web local. A camada Android precisa integrar o runtime Python e compilar/fornecer as dependências nativas ARM64, especialmente llama.cpp. O APK ainda não está pronto.

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
