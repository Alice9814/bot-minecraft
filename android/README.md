# Android build — ProtoBot

O APK usa a mesma interface HTML/CSS/JavaScript do desktop. Os três arquivos são incorporados ao módulo Python `interface_bundle.py`; no primeiro início, o aplicativo os extrai para a pasta gravável de dados do ProtoBot. Isso evita depender de `interface/index.html` em um caminho que o empacotador Android não copia.

## Tecnologia

- PySide6 e Qt WebView.
- Interface HTML servida por HTTP local em loopback.
- ProtoBot e Gemma executados no processo Python do aplicativo.
- ARM64 (`arm64-v8a`) como arquitetura inicial.

## Segundo plano no Android

Ao fechar a janela de controle, o aplicativo esconde a interface e descarrega a página HTML, mas não envia o sinal de encerramento ao worker do bot. O usuário pode voltar ao ProtoBot pela tela de aplicativos recentes; ao reabrir, a interface é carregada novamente e o bot continua conectado enquanto o processo permanecer vivo.

**Limitação importante:** isso mantém o worker ativo em segundo plano em condições normais, mas ainda não equivale a um Android Foreground Service nativo. O Android pode suspender ou encerrar o processo para economizar bateria/memória. Para garantir execução prolongada com notificação persistente, será necessário integrar um serviço Java/Kotlin declarado no manifesto Android e solicitar a permissão de foreground service adequada à versão do Android. Essa integração nativa ainda precisa ser implementada e testada em aparelho real.

## Estado do APK

O APK continua experimental. A compilação de PySide6/Qt WebView é apenas uma etapa; as dependências nativas de `llama-cpp-python`/llama.cpp e quaisquer dependências nativas do ProtoBot precisam ser compiladas e testadas separadamente para Android ARM64.

## Ferramenta de empacotamento

O Qt for Python disponibiliza `pyside6-android-deploy`, que gera APK/AAB e usa python-for-android. A ferramenta deve ser executada em Linux ou macOS, com JDK 17+, Android SDK/NDK e wheels Android correspondentes de PySide6/Shiboken6.

Documentação oficial:
https://doc.qt.io/qtforpython-6/deployment/deployment-pyside6-android-deploy.html

## Próximas validações

1. Confirmar que a interface incorporada é extraída e aberta no APK.
2. Confirmar que fechar a janela não encerra o worker.
3. Testar retorno pela tela de aplicativos recentes.
4. Implementar e testar o Foreground Service nativo.
5. Validar conexão, alimentação, defesa e inferência local no aparelho.
