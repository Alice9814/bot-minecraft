# Android build — ProtoBot

O APK usa o mesmo aplicativo Python e os mesmos arquivos HTML/CSS/JavaScript usados no desktop. A interface é carregada diretamente de `interface/index.html` pelo Qt WebView; não existe servidor HTTP local.

## Tecnologia

- PySide6 6.11 ou superior.
- Qt WebView: usa o Android System WebView no Android.
- ProtoBot e Gemma executados localmente.
- ARM64 (`arm64-v8a`) como arquitetura inicial.

O Qt WebView também usa WebView2/Qt WebEngine no Windows e Qt WebEngine no Linux, conforme os backends disponíveis da plataforma. Consulte a documentação do Qt WebView antes de atualizar a versão do Qt.

## Estado atual

O ponto de entrada `main.py` já chama a mesma interface do desktop. O worker pode ser executado em uma thread no Android e recebe um sinal de encerramento pelo arquivo de controle.

O APK ainda não está pronto para distribuição. O principal bloqueio técnico é compilar e empacotar as dependências nativas para Android ARM64, especialmente `llama-cpp-python`/llama.cpp e qualquer dependência nativa exigida pelo ProtoBot. Não basta copiar os wheels de Windows ou Linux.

## Ferramenta de empacotamento

O Qt for Python disponibiliza `pyside6-android-deploy`, que gera APK/AAB e usa python-for-android. A ferramenta deve ser executada em Linux ou macOS, com JDK 17+, Android SDK/NDK e os wheels Android correspondentes de PySide6/Shiboken6.

Documentação oficial:
https://doc.qt.io/qtforpython-6/deployment/deployment-pyside6-android-deploy.html

## Próxima etapa técnica

1. Preparar um build ARM64 de teste do PySide6/Qt WebView.
2. Confirmar a abertura de `interface/index.html` dentro do APK.
3. Validar ProtoBot e suas dependências no Python Android.
4. Compilar llama.cpp para Android ARM64 e integrar o runtime local.
5. Testar conexão, execução em segundo plano e encerramento no aparelho.
