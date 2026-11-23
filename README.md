# Companion PC

Painel de dados pessoais e atalhos do PC (Windows 11), acessado pelo navegador
de qualquer aparelho da rede local — celular, tablet ou outro computador.
Mostra o sistema (CPU, memória, GPU, discos, rede), o que está tocando, jogos e
tempo jogado, notificações, e controla o PC: botões estilo Stream Deck, mouse e
teclado, tela ao vivo, arquivos, área de transferência e energia.

Não precisa instalar nada no aparelho: abra no navegador e, no celular, use
"Adicionar à tela inicial" (é um PWA). Funciona em pé e deitado.

```
Aparelho (navegador/PWA) ──rede local (Wi-Fi/cabo)──  http://<IP do PC>:8770
Celular Android          ──cabo USB (adb reverse)───  http://localhost:8770
```

**Preparar o PC (uma vez):** `windows\setup-network.ps1`
(libera a porta 8770 no firewall em redes Privadas e instala o adb, usado só no modo cabo).

- **Rede local:** abra o painel (ícone na bandeja) e escaneie o QR code com a câmera
  do celular — o link já leva o token. Ou abra `http://<IP do PC>:8770` e cole o token.
- **Cabo (opcional, Android):** no celular ative *Opções do desenvolvedor → Depuração USB*, ligue no
  PC e aceite a permissão. O servidor faz o `adb reverse` sozinho; abra
  `http://localhost:8770` no Chrome (o botão "Abrir app no celular (cabo)" do
  painel abre já com o token). Pelo cabo dá para instalar como app de verdade;
  "manter a tela ligada", notificações e "Compartilhar com Companion PC" só
  funcionam assim.

### Abas

Seis temas: **Fallout** (terminal de fósforo verde, âmbar ou ciano), **Synthwave**, **Minimal**
(escuro ou claro), **Cockpit**, **LCD 8-bit** e **Papel**. Troque em **PC › Ajustes › Visual** ou no editor
do PC. Cinco seções na barra (padrão); cada uma tem sub-abas no topo.
Em tablet deitado (≥ 1000 px de largura) as sub-abas de uma seção aparecem lado a lado.

| Seção | Sub-abas e o que tem |
|---|---|
| **Status** | *Sistema*: CPU, memória, GPU (consumo, ventoinha) e rede com gráfico do último minuto, processos, discos, **bateria** do mouse, teclado, fone e controle; temperatura da CPU e ventoinhas se o LibreHardwareMonitor estiver rodando. *Jogos*: jogo aberto, tempo jogado, recentes e biblioteca. *Tempo*: tempo de tela por app e categoria (hoje, semana, mês). Com um jogo aberto aparece *Jogando*; numa chamada do Meet, *Reunião*. |
| **Rádio** | *Tocando*: capa, faixa, progresso (arraste para pular), volume e saída de áudio (toque para alternar). *Mixer*: volume e mudo por aplicativo e escolha da saída (fone, caixa, monitor). |
| **Controle** | *Mouse e teclado*: touchpad (toque = clique; 2 dedos: toque = direito, arrastar = rolar; toque duplo e arraste = segurar), teclas especiais e o teclado do Android digitando no PC. *Tela do PC*: a tela ao vivo; toque = clique, segurar = botão direito, pinça = zoom, faixa da direita = rolar. |
| **Botões** | Páginas de botões estilo Stream Deck. **Editar** cria/edita botões (atalho de teclado, texto, ação pronta ou programa do config.json), com ícone, cor e confirmação. Ficam salvos em `deck.json` no PC. |
| **PC** | *Arquivos*: texto/link para a área de transferência do PC (ou já colar), fotos e arquivos para `Downloads\Companion PC`, e "Pegar o que está copiado no PC". *Energia*: bloquear, monitor, suspender, reiniciar, desligar. *Ajustes*: alertas (download concluído, GPU/CPU quente, memória cheia), cor do terminal e ajustes do aparelho. |

**Novidades da 1.8**

- **Personalizar pelo PC:** ícone da bandeja › *Personalizar* abre `http://localhost:8770/editor`.
  Escolha o tema, arraste as abas entre as seções do menu (ou esconda), renomeie e reordene as seções,
  e em **Telas** arrume o que aparece dentro de cada aba (Sistema, Jogando, Reunião, Jogos, Tempo, Tocando, Mixer, Mouse,
  Arquivos, Energia, Voz, Ajustes): ordem, mostrar/esconder e largura inteira. Também reordena os botões e as páginas.
  Em pé e deitado têm layouts separados. Fica salvo em `layout.json` e muda na hora em todos os aparelhos
  (as prévias do editor são o próprio app).
- **Bateria:** mouse Attack Shark X11 (receptor 1d57:fa60, o mouse avisa sozinho a cada ~2 s enquanto
  está acordado), teclado AULA F75 no 2.4G (receptor 3554:fa09, perguntado a cada 5 min), fones e outros
  aparelhos Bluetooth (o que o Windows informa) e controles XInput (8BitDo no modo X; só 4 níveis).
  Toque no cartão para atualizar. Precisa do pacote `hidapi` (o instalador já põe).
- **Tempo de tela:** soma o programa em foco; para depois de 2 min sem mexer em mouse/teclado, a não ser
  que haja jogo, tela cheia ou mídia tocando. Categorias automáticas; troque a de um app tocando nela
  (fica em `"screentime": {"categories": {...}}` do config.json). Dados em `screentime.db`.
- **Reunião (Google Meet no Edge):** carregue a extensão uma vez: `edge://extensions` › *Modo de
  desenvolvedor* › *Carregar sem compactação* › `%USERPROFILE%\companion-pc\edge-extension`. Durante a
  chamada o app abre a aba *Reunião*: microfone, câmera, mão, legendas, chat, compartilhar tela (o Meet
  vem para a frente e o Edge abre a escolha da tela no PC) e sair (segure). Funciona com a aba em segundo
  plano. O servidor só aceita a extensão vinda do próprio PC.
- **Jogando:** ao abrir um jogo, o app muda para *Jogando*: tempo de sessão, horas, FPS, GPU/CPU,
  ping e atalhos (MIC, Discord, print F12). **CS2** e **Dota 2** mostram a partida (placar, vida, colete,
  dinheiro, munição, KDA / herói, ouro, GPM, itens) pelo *Game State Integration* da Valve: o servidor
  instala sozinho o arquivo `gamestate_integration_companionpc.cfg` na pasta do jogo (porta 8772).
  No **Dota 2** falta um passo: Steam › Dota 2 › Propriedades › Opções de inicialização:
  `-gamestateintegration`.

**Extras**

- **Botões que seguem o programa:** cada página pode ter uma lista de programas (`code.exe`,
  `spotify.exe`...; `@jogo` = qualquer jogo detectado). Quando um deles entra em foco no PC, a página
  abre sozinha. Já vêm páginas para navegador, VS Code, Terminal, Discord, Spotify, WhatsApp e jogos.
  Edite em **Botões › Editar** tocando no nome da página.
- **Microfone do PC:** o indicador `MIC` no topo coloca no mudo o microfone padrão e o de comunicação
  (vale para qualquer programa). Também existe como ação de botão.
- **Timer de energia:** em **PC › Energia**, desligar, suspender ou desligar o monitor daqui a
  15 min a 2 h. A contagem aparece no topo; toque para cancelar.
- **Modo base:** depois de alguns minutos sem tocar (ajuste em **PC › Ajustes**), o celular mostra
  um relógio grande com CPU/GPU, música e jogo. A posição muda um pouco a cada minuto para não marcar a tela.
- **Jogos:** em **Status › Jogos** ficam a biblioteca (Steam, Epic e GOG; toque para abrir o jogo),
  as horas jogadas por dia na semana e os jogos mais jogados.
- **Ping:** a latência da internet aparece no card Rede; o alerta "Internet caiu" avisa quando cai e volta.
- **Sons de terminal:** bipes curtos ao tocar, conectar e em avisos (**PC › Ajustes › Visual**).
- **Macros:** botão do tipo *Sequência*, um passo por linha: `teclas ctrl+t`, `texto olá`,
  `esperar 500` (ms) ou `esperar 2s`, `abrir vscode` (id ou nome do programa do config.json),
  `acao media.next`. No máximo 40 passos e 60 s de espera.
- **Notificações do PC:** o que aparece na Central de notificações do Windows (WhatsApp, Discord,
  e-mail...) chega no celular. Se estiver bloqueado: Configurações do Windows › Privacidade ›
  Notificações. Para ignorar apps, `"notif_ignore": ["Microsoft Edge"]` no config.json.
- **FPS do jogo:** com o PresentMon Console (`winget install Intel.PresentMon.Console`). O Windows só
  deixa medir FPS sem admin para quem está no grupo *Usuários de log de desempenho*; rode uma vez
  num PowerShell como Administrador e depois saia e entre na conta:
  `Add-LocalGroupMember -SID S-1-5-32-559 -Member $env:USERNAME`
- Programas do `config.json` aceitam `"appx": "<AppID>"` para apps da Microsoft Store
  (veja com `Get-StartApps` no PowerShell).

**Temperatura da CPU / ventoinhas (opcional):** o Windows não fornece isso sem
driver. Se o LibreHardwareMonitor estiver rodando com *Options → Remote Web Server → Run*,
o servidor lê de `http://127.0.0.1:8085` e mostra no Painel. Neste PC a versão
0.9.6 travou ao abrir (sem o driver PawnIO), então ficou sem — a GPU (temperatura,
ventoinha, consumo) vem do `nvidia-smi` e funciona sem nada extra.

Para aceitar só o cabo, use `"web": {"host": "127.0.0.1"}` no `config.json`;
para mudar a porta, `"web": {"port": 8770}`. Pastas: `"upload_dir"` (onde chegam
os arquivos do celular) e `"downloads_dir"` (a pasta vigiada para o alerta de download).

## Estrutura

| Caminho | O que é |
|---|---|
| `windows/server/companion_server.py` | Servidor (HTTP + WebSocket na porta 8770) |
| `windows/server/web/` | App web (HTML/JS, PWA) |
| `windows/server/tray.py` | Ícone na bandeja + painel de status com QR code |
| `windows/server/pc_info.py` | Mídia tocando (GSMTC), volume, mixer e saída de áudio (pycaw), GPU (nvidia-smi), sensores (LHM) |
| `windows/server/extras.py` | Deck, área de transferência, arquivos, tela do PC, vigia de downloads |
| `windows/server/games.py` | Jogo aberto, biblioteca (Steam/Epic/GOG) e histórico de horas |
| `windows/server/watchers.py` | Ping, notificações do Windows, FPS (PresentMon) |
| `windows/server/devices.py` | Bateria: Attack Shark X11, AULA F75, Bluetooth, XInput |
| `windows/server/screentime.py` | Tempo de tela por app (SQLite) |
| `windows/server/gsi.py` | Game State Integration de CS2 e Dota 2 |
| `windows/server/web/editor.html` | Editor de tema e layout (abra pela bandeja) |
| `windows/edge-extension/` | Extensão do Edge para o Google Meet |
| `windows/install-server.ps1` | Instala dependências e inicia o servidor com o Windows |
| `windows/setup-network.ps1` | Firewall da porta 8770 + adb (uma vez; pede admin só para o firewall) |

## Instalação

1. `powershell -ExecutionPolicy Bypass -File windows\install-server.ps1`
2. Uma vez: `windows\setup-network.ps1`
3. O token fica em `%USERPROFILE%\companion-pc\server\config.json`
   (quem tinha a instalação antiga em `r36s-companion` tem o token, deck e histórico migrados).

O servidor roda em segundo plano (pythonw), só com um ícone na bandeja:
verde = aparelho conectado, amarelo = aguardando conexão, cinza = porta indisponível.
Duplo clique no ícone (ou abrir "Companion PC" no Menu Iniciar) mostra o
painel com status, QR code, jogo atual e log; o menu tem Reiniciar e Sair. Só roda uma
instância — abrir de novo apenas mostra o painel. Para depurar no terminal:
`py -3 companion_server.py --console`.

## Segurança

- O servidor escuta na porta 8770 (rede local + cabo) e exige o token do `config.json`.
  O tráfego no Wi-Fi não é criptografado: use em rede doméstica de confiança
  (o firewall só libera redes Privadas). Texto digitado ou copiado pelo celular não vai para o log.
- Quem tem o token controla o PC (teclado, mouse, tela). Botões criados pelo
  celular só podem apertar teclas, digitar, usar ações prontas ou abrir programas
  já listados no `config.json` — caminhos novos de programas só pelo PC.
- Arquivos do PC só ficam acessíveis ao aparelho quando você os copia e toca em
  "Pegar o que está copiado", por um link aleatório que expira em 15 min.
- Só executa ações de uma lista fechada (`ACTIONS` no servidor); programas
  só abrem se estiverem em `"shortcuts"` do `config.json`. Não há execução
  de comandos arbitrários.
- Desligar/reiniciar usam atraso de 30 s (`shutdown_delay_s`) e podem ser
  cancelados em **PC › Energia**. `"allow_power": false` desativa a energia.
- Ao desconectar, o servidor solta Alt e o botão do mouse se estavam presos.

## Personalizar atalhos

Em `config.json` do servidor:
```json
{"id": "spotify", "name": "Spotify", "open": "spotify:"},
{"id": "proj", "name": "Projetos", "open": "D:\\Projetos"},
{"id": "obs", "name": "OBS", "open": "C:\\Program Files\\obs-studio\\bin\\64bit\\obs64.exe"}
```
Reinicie o servidor após editar.
