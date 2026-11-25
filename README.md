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
  painel abre já com o token). Pelo cabo (ou pelo HTTPS do Tailscale, abaixo) dá para instalar
  como app de verdade; "manter a tela ligada", notificações e "Compartilhar com Companion PC" só
  funcionam assim.
- **Tailscale (recomendado):** HTTPS de verdade, em casa e fora, Android e iPhone. Veja
  [HTTPS e acesso fora de casa](#https-e-acesso-fora-de-casa-tailscale).

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
| **Botões** | Páginas de botões estilo Stream Deck. **Editar** cria/edita botões (atalho de teclado, texto, ação pronta ou programa do config.json), com ícone, cor e confirmação. Ficam salvos em `deck.json` no PC. Tipo **Tocar som**: escolha um áudio no celular e ele sai no microfone (Discord etc.); veja *Sons no microfone*. |
| **PC** | *Arquivos*: texto/link para a área de transferência do PC (ou já colar), fotos e arquivos para `Downloads\Companion PC`, e "Pegar o que está copiado no PC". *Energia*: bloquear, monitor, suspender, reiniciar, desligar. *Ajustes*: alertas (download concluído, GPU/CPU quente, memória cheia), cor do terminal e ajustes do aparelho. |

**Depois da 1.9**

- **Fim de partida:** quando uma partida de CS2 ou Dota 2 termina, o celular avisa e mostra seus números
  comparados com a sua média naquele mapa/herói (ou geral), sequência de vitórias e % de vitórias. Fica em Jogos e
  em Jogando por 30 min.
- **Steam (Status › Jogos):** downloads e atualizações com progresso, velocidade e tempo restante (lidos dos
  `appmanifest` do PC), chip *STEAM %* no topo e aviso quando termina. Amigos online e jogando o quê, com aviso quando
  alguém começa um jogo: precisa de uma chave grátis de steamcommunity.com/dev/apikey em Personalizar › *Steam*.
- **Reunião automática:** 1 minuto antes de um compromisso com link do Meet o celular mostra *Reunião em 1 min* com
  botão Entrar e o PC aplica o perfil de áudio escolhido (e, se marcado, já abre a reunião). Em Personalizar › *Hoje*.
- **Seu dia (Status › Hoje):** tempo de tela (e a diferença da média), foco, horas jogando, partidas ganhas/perdidas,
  reuniões e app mais usado. Depois das 21h o modo base mostra o resumo.
- **Temas novos:** Portátil (4 tons), Código (cores de sintaxe), Fantasia (pedra e ouro), Tático (mapa de missão),
  Japão (sakura de dia, Tóquio à noite) e Executivo (marinho, marfim ou preto); variações Fallout azul/branco,
  Synthwave pôr do sol/gelo, Minimal AMOLED e Cockpit aviônica. **Troca automática** por horário e pelo jogo aberto
  (Dota 2 / CS2) em Personalizar › Tema.
- **Dota 2: draft e build** (Jogos, e Jogando com o Dota aberto; precisa da chave grátis do STRATZ em
  Personalizar › *Dota 2*). *Draft*: escolha sua posição, marque os heróis inimigos (e aliados, se quiser) e veja os
  heróis da posição ordenados por vantagem contra eles + sinergia + força no meta, com o número contra cada inimigo e
  quantas partidas você tem com cada um (*Só os que eu jogo*). O GSI do jogador não mostra o time inimigo, por isso
  é marcado à mão. *Build*: abre sozinha com o herói que você pegou — itens iniciais, botas, primeiros itens, itens
  principais com o minuto médio, situacionais, ordem das skills e talentos mais escolhidos, na sua posição e faixa
  de rank (o rank vem do seu perfil público no STRATZ). *Fila*: antes da partida escolha a posição e até 6 heróis preferidos;
  o draft e a build já abrem com isso, aparecem os seus preferidos na posição e quem banir contra eles, e o plano
  zera quando a partida termina (fica no PC, igual em todos os aparelhos). Botão *Turbo*: meta e winrates do Turbo
  (última semana); itens, skills e talentos vêm das partidas normais (o STRATZ não separa builds por modo) com os
  minutos multiplicados por 0,53, fator medido em partidas Turbo reais (`TURBO_TIME` em `dota_draft.py`).
- **Dota 2 por fase (Jogando):** a tela muda com a fase que o GSI informa: *Fila* (menu), *Draft* (escolha de heróis),
  *Estratégia* (itens iniciais para comprar, marcados quando já estão no inventário, e o primeiro ponto de skill) e
  *Partida* (painel compacto + card *Agora*: próximo item da build com o ouro que falta e se está no tempo, próximo
  ponto de skill e talento; aviso quando dá para comprar). Nomes de itens, habilidades e talentos em português, do
  datafeed oficial do dota2.com. Com um jogo aberto o modo base não troca de tela e a tela fica acesa; os avisos dos
  timers tocam em qualquer aba. Em tela larga, Jogando fica larga com uma aba ao lado. Estatísticas em cache em `dota-cache\` por horas.
- Aba nova (como *Hoje*) entra sozinha em menus já salvos; clima usa wttr.in quando o Open-Meteo falha.

**Novidades da 1.9**

- **Dota 2 (aba Jogando):** timers pelo relógio da partida (runas de recompensa, poder, água e sabedoria, lótus,
  itens neutros, stack em x:53, dia/noite, Tormentor), Roshan e Aegis com um toque em *Roshan morreu* ou sozinhos
  quando o jogo manda o evento. Avisos com bipe e vibração (escolha quais pelo círculo de cada linha): timers 15 s antes,
  ultimate e BKB prontas, buyback disponível, vida baixa. Gráficos de last hits (com meta de 7/min) e GPM/XPM.
  Os tempos são do patch 7.3x e ficam em `DOTA_TIMERS` no `web/js/jogos.js`.
- **CS2 (aba Jogando):** contagem da bomba plantada (e se dá para desarmar com ou sem kit), economia (dinheiro,
  equipamento, bônus de derrota, quanto terá se perder ou ganhar e sugestão de compra), rounds ganhos e perdidos
  com o motivo, seus abates/HS/dano por round, HS% e ADR. Depois de morrer continua mostrando os seus números.
- **Histórico:** cada partida de CS2 e Dota 2 que termina fica em `matches.db`; em **Status › Jogos › Partidas**
  aparecem vitórias e médias por mapa/herói e as últimas partidas.
- **Clipe 30 s:** botão em Jogando que aperta Win+Alt+G (Xbox Game Bar). Ative em Configurações do Windows ›
  Jogos › Capturas › *Gravar o que aconteceu*.
- **Hoje (Status › Hoje):** clima (Open-Meteo) e agenda do Google (endereço secreto iCal; reuniões recorrentes
  também) com botão *Entrar* que abre o Meet no Edge do PC e lembrete 5 min antes. Configure em
  Personalizar › *Hoje*. Também aparecem no card Sistema e no modo base.
- **Foco:** cronômetro de 25/50/90 min; as notificações do PC não chegam no celular enquanto dura. Fica no topo
  (FOCO) e conta o tempo de foco do dia.
- **Perfis de áudio (Rádio › Mixer):** salva saída, volume, microfone e volume dos apps; um toque aplica.
- **Bateria fraca:** aviso quando mouse, teclado, fone ou controle ficam abaixo de 15% (ajuste em PC › Ajustes).

**Novidades da 1.8**

- **Personalizar pelo PC:** ícone da bandeja › *Personalizar* abre `http://localhost:8770/editor`.
  Escolha o tema, arraste as abas entre as seções do menu (ou esconda), renomeie e reordene as seções,
  e em **Telas** arrume o que aparece dentro de cada aba (Sistema, Jogando, Reunião, Jogos, Tempo, Tocando, Mixer, Mouse,
  Arquivos, Energia, Voz, Ajustes): ordem, mostrar/esconder e largura inteira. Também reordena os botões e as páginas.
  Em pé e deitado têm layouts separados. Fica salvo em `layout.json` e muda na hora em todos os aparelhos
  (as prévias do editor são o próprio app).
- **Bateria:** mouse Attack Shark X11 (receptor 1d57:fa60, o mouse avisa sozinho a cada ~2 s enquanto
  está acordado), teclado AULA F75 no 2.4G (receptor 3554:fa09, perguntado a cada 5 min), fones, mouses,
  teclados e outros aparelhos Bluetooth, clássicos e BLE (o que o Windows informa), e controles: % exata pelo
  Windows.Gaming.Input quando o controle informa (Xbox sem fio e afins), senão XInput (8BitDo no modo X; só 4 níveis).
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

- **Sons no microfone (soundboard):** botões do tipo **Tocar som** no deck. O celular converte o
  áudio (MP3, OGG, WAV, M4A…, até 20 s) para WAV, corta o silêncio das pontas e iguala o volume; o PC guarda
  em `sons/`. No editor do PC (bandeja › editor, seção Botões) dá para arrastar vários arquivos de uma vez
  e editar nome, ícone, cor, volume e trocar o áudio de cada botão de som. Tocar de novo no botão para o som; **Parar sons** para todos. Para sair no microfone é preciso
  um cabo virtual: instale o **VB-CABLE** (grátis, vb-audio.com/Cable) e reinicie o PC. O servidor toca no
  `CABLE Input` o seu microfone de verdade misturado com os sons, e no Discord o dispositivo de entrada
  vira `CABLE Output` (supressão de ruído em Nenhuma/Padrão; o Krisp corta música). O botão **Som** escolhe o
  microfone que vai junto, os volumes, "um som por vez" e se você também ouve. Sem cabo, os sons tocam só no PC.
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
| `windows/server/companion_server.py` | Servidor (WebSocket na porta 8770), ações permitidas, voz, reunião, foco |
| `windows/server/web_static.py` | Entrega os arquivos de `web/` (só os de dentro da pasta) e os links de download |
| `windows/server/https_cert.py` | HTTPS: certificado do Tailscale (renova sozinho) ou cert/key do config |
| `windows/server/win_input.py` | Teclado e mouse virtuais e a janela em foco (Win32) |
| `windows/server/web/index.html` | App web (PWA): só a marcação; o estilo e o código ficam em `css/` e `js/` |
| `windows/server/web/css/` | `base` (fontes e cores), `temas`, `moldura` (barra, cartões, diálogos, deitado) e `telas` |
| `windows/server/web/js/` | Um arquivo por parte do app (`core` = conexão, `layout`, `jogos`, `mixer`, `hoje`…), carregados em ordem pelo `index.html`; `main.js` por último |
| `windows/server/tests/` | Testes (dentro de `windows/server`: `py -3 -m unittest`) |
| `windows/server/tray.py` | Ícone na bandeja + painel de status com QR code |
| `windows/server/pc_info.py` | Mídia tocando (GSMTC), volume, mixer e saída de áudio (pycaw), GPU (nvidia-smi), sensores (LHM) |
| `windows/server/extras.py` | Deck, área de transferência, arquivos, tela do PC, vigia de downloads |
| `windows/server/games.py` | Jogo aberto, biblioteca (Steam/Epic/GOG) e histórico de horas |
| `windows/server/watchers.py` | Ping, notificações do Windows, FPS (PresentMon) |
| `windows/server/devices.py` | Bateria: Attack Shark X11, AULA F75, Bluetooth, XInput |
| `windows/server/screentime.py` | Tempo de tela por app (SQLite) |
| `windows/server/gsi.py` | Game State Integration de CS2 e Dota 2 |
| `windows/server/dota_stats.py` | Relatório do Dota depois da partida (STRATZ / OpenDota) |
| `windows/server/dota_draft.py` | Draft (counters) e builds do Dota com as estatísticas do STRATZ |
| `windows/server/matches.py` | Acompanha rounds/minutos das partidas e guarda o histórico |
| `windows/server/soundboard.py` | Sons no microfone: mistura os sons do deck com o microfone no cabo virtual |
| `windows/server/daily.py` | Clima (Open-Meteo) e agenda (iCal) |
| `windows/server/steam.py` | Steam: downloads (appmanifest) e amigos (Web API com a chave do usuário) |
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

**Mexendo no código:** os arquivos de `web/js/` dividem o mesmo escopo global (não são módulos) e
rodam na ordem do `index.html`; código que roda ao carregar só pode chamar funções de arquivos
anteriores. Cada arquivo começa com `"use strict";`. Antes de instalar, rode os testes em
`windows/server`: `py -3 -m unittest`.

## Atualizações

O servidor confere a cada 6 h o `release.json` deste repositório. Se a versão publicada for maior que a
instalada, o app mostra um aviso e **Ajustes › Atualização › Atualizar**; a bandeja ganha
**Atualizar para a versão X** (e tem **Procurar atualização**). Atualizar baixa o zip da tag `vX`, roda o
`install-server.ps1` dele e reinicia o servidor; `config.json`, `deck.json`, sons e histórico ficam.
O que o instalador escreveu vai para `update.log`. Para desligar: `"update": {"check": false}` no `config.json`.

Para publicar (na `main`, sem mudanças pendentes): `tools/release.sh 1.10 "o que mudou"`. Ele roda os testes,
troca o `VERSION`, grava o `release.json`, cria a tag e manda tudo para o GitHub.

## HTTPS e acesso fora de casa (Tailscale)

Com HTTPS o navegador trata o app como seguro também sem cabo: instala como app (inclusive no iPhone),
notificações, tela sempre ligada, "Compartilhar com Companion PC" e o app abre mesmo com o PC
desligado (mostra "sem conexão" e reconecta sozinho quando o PC volta).

1. Instale o [Tailscale](https://tailscale.com/download) no PC e no celular, com a mesma conta.
2. No painel do Tailscale (*login.tailscale.com › DNS*) ative **MagicDNS** e **HTTPS Certificates**.
3. Rode de novo `windows\setup-network.ps1`: libera a porta **8771** só para aparelhos do Tailscale.
4. Reinicie o servidor. O painel da bandeja mostra *Seguro (Tailscale)* e o QR passa a abrir
   `https://<pc>.<tailnet>.ts.net:8771`. Quem já usa pelo Wi-Fi acha **Versão segura** em
   *PC › Ajustes › Conexão* (leva o token junto).

O certificado (Let's Encrypt, 90 dias) fica em `certs\` e o servidor pede a renovação todo dia.
O endereço `http://<IP>:8770` continua funcionando para quem não tem o Tailscale.
Sem Tailscale, dá para usar outro certificado (ex.: [mkcert](https://github.com/FiloSottile/mkcert),
com a CA instalada no celular) em `config.json`:
`"https": {"enabled": true, "port": 8771, "cert_file": "C:\\caminho\\pc.pem", "key_file": "C:\\caminho\\pc-key.pem", "host": "192.168.0.10"}`
(`"enabled": false` desliga o HTTPS).

## Segurança

- O servidor escuta na porta 8770 (rede local + cabo) e exige o token do `config.json`.
  O tráfego no Wi-Fi (porta 8770) não é criptografado: use em rede doméstica de confiança (o firewall
  só libera redes Privadas), ou o HTTPS do Tailscale (porta 8771, criptografado e só para aparelhos
  da sua conta). Texto digitado ou copiado pelo celular não vai para o log.
- Quem tem o token controla o PC (teclado, mouse, tela). Botões criados pelo
  celular só podem apertar teclas, digitar, usar ações prontas ou abrir programas
  já listados no `config.json` — caminhos novos de programas só pelo PC.
- Arquivos do PC só ficam acessíveis ao aparelho quando você os copia e toca em
  "Pegar o que está copiado", por um link aleatório que expira em 15 min.
- Só executa ações de uma lista fechada (`ACTIONS` no servidor); programas
  só abrem se estiverem em `"shortcuts"` do `config.json` ou no Menu Iniciar do Windows
  (a voz acha apps da Microsoft Store, como o Spotify, por lá). Não há execução
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
